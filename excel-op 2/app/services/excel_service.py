from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Iterable, Mapping, Sequence, Union

import pandas as pd

ExcelInput = Union[str, Path, IO[bytes]]

# Default column expectations – adjust to your domain as needed
TRAINING_TAXONOMY_COLS: tuple[str, str, str] = ("l0", "l1", "l2")
DEFAULT_TRAINING_RAW_COLS: tuple[str, str] = ("material_code", "material_description")


class SchemaValidationError(Exception):
    """Raised when an Excel sheet does not match the expected schema."""

    def __init__(
        self,
        message: str,
        *,
        missing_columns: Sequence[str] | None = None,
        unexpected_columns: Sequence[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.missing_columns = list(missing_columns or [])
        self.unexpected_columns = list(unexpected_columns or [])


def _normalise_columns(columns: Iterable[Any]) -> list[str]:
    """Convert Excel headers to snake_case and normalised spacing."""
    normalised: list[str] = []
    for col in columns:
        if col is None:
            normalised.append("")
            continue
        name = str(col).strip().replace("\n", " ").replace("\r", " ")
        name = "_".join(part for part in name.split(" ") if part)
        normalised.append(name.lower())
    return normalised


def _validate_schema(
    df: pd.DataFrame,
    *,
    required_columns: Sequence[str],
    optional_columns: Sequence[str] | None = None,
) -> None:
    """
    Validate that a DataFrame contains the required columns and no obviously wrong extras.

    Raises SchemaValidationError with detailed info if validation fails.
    """
    present = set(df.columns)
    required = set(required_columns)
    optional = set(optional_columns or [])

    missing = sorted(required - present)
    # "Unexpected" here just means "not in required or optional". We don't fail on them yet,
    # but we expose them for logging / debugging.
    unexpected = sorted(present - required - optional)

    if missing:
        raise SchemaValidationError(
            f"Excel schema validation failed. Missing required columns: {missing}",
            missing_columns=missing,
            unexpected_columns=unexpected,
        )


def read_training_excel(
    source: ExcelInput,
    sheet_name: str | int | None = 0,
    *,
    required_raw_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """
    Read a training Excel file containing raw material fields AND taxonomy labels (L0/L1/L2).

    - Normalises column names.
    - Validates presence of:
      - L0/L1/L2 taxonomy columns.
      - Domain raw columns (configurable via `required_raw_columns`).
    - Applies basic cleaning and trimming.
    """
    df = pd.read_excel(source, sheet_name=sheet_name, engine="openpyxl")
    df.columns = _normalise_columns(df.columns)
    
    # Check for our typical input names and map them if necessary
    rename_map = {}
    if "l0" not in df.columns and "direct_indirect" in df.columns:
        rename_map["direct_indirect"] = "l0"
    if "material_description" not in df.columns and "m_desc" in df.columns:
        rename_map["m_desc"] = "material_description"
    if "material_code" not in df.columns and "m_code" in df.columns:
        rename_map["m_code"] = "material_code"
        
    if rename_map:
        df = df.rename(columns=rename_map)

    raw_required = list(required_raw_columns or DEFAULT_TRAINING_RAW_COLS)
    required = list(TRAINING_TAXONOMY_COLS) + raw_required

    _validate_schema(
        df,
        required_columns=required,
        optional_columns=[],
    )

    return _clean_dataframe(df)


def read_inference_excel(
    source: ExcelInput,
    sheet_name: str | int | None = 0,
    *,
    required_raw_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """
    Read an inference Excel file containing only raw material fields (no taxonomy labels).

    - Normalises column names.
    - Validates presence of domain raw columns (configurable via `required_raw_columns`).
    - Applies basic cleaning and trimming.
    """
    df = pd.read_excel(source, sheet_name=sheet_name, engine="openpyxl")
    df.columns = _normalise_columns(df.columns)

    raw_required = list(required_raw_columns or DEFAULT_TRAINING_RAW_COLS)
    _validate_schema(df, required_columns=raw_required, optional_columns=[])

    return _clean_dataframe(df)


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to Excel bytes."""
    from io import BytesIO
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def split_training_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split training DF into raw_df and labels_df (l0/l1/l2)."""
    taxonomy_cols = list(TRAINING_TAXONOMY_COLS)
    
    # ensure columns are lowercase for matching
    df_cols_lower = [str(c).lower() for c in df.columns]
    
    label_cols_present = [c for c in df.columns if str(c).lower() in taxonomy_cols]
    
    if len(label_cols_present) != len(taxonomy_cols):
        raise ValueError(f"Expected {taxonomy_cols}, found {label_cols_present} out of {list(df.columns)}")
        
    labels_df = df[label_cols_present].copy()
    raw_df = df.drop(columns=label_cols_present).copy()
    
    # Rename labels back to standard lowercase for downstream
    labels_df.columns = [str(c).lower() for c in labels_df.columns]
    
    return raw_df, labels_df


def write_classified_excel(df: pd.DataFrame, path: ExcelInput | None = None) -> bytes | None:
    """
    Write a classified DataFrame (including L0/L1/L2, confidence, remarks) to Excel.

    - If `path` is provided, writes the file to disk and returns None.
    - If `path` is None, returns Excel bytes suitable for HTTP responses.
    """
    if path is None:
        return dataframe_to_excel_bytes(df)

    df.to_excel(path, index=False, engine="openpyxl")
    return None


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Basic cleaning and type coercion:
    - Strip whitespace from string columns.
    - Normalise obvious NA-like string values to real NaN.
    """
    cleaned = df.copy()

    na_like = {"", "na", "n/a", "none", "null", "nan"}

    for col in cleaned.columns:
        if pd.api.types.is_string_dtype(cleaned[col]) or cleaned[col].dtype == object:
            cleaned[col] = (
                cleaned[col]
                .astype(str)
                .str.strip()
                .replace({v: pd.NA for v in na_like})
            )

    return cleaned


