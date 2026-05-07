import io

import pandas as pd
import pytest

from app.services.excel_service import (
    DEFAULT_TRAINING_RAW_COLS,
    SchemaValidationError,
    read_inference_excel,
    read_training_excel,
    split_training_dataframe,
)


def _make_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def test_read_training_excel_happy_path(tmp_path):
    cols = list(DEFAULT_TRAINING_RAW_COLS) + ["l0", "l1", "l2"]
    df = pd.DataFrame([["286450", "ROD COPPER", "Direct", "Raw", "Copper"]], columns=cols)
    path = tmp_path / "training.xlsx"
    path.write_bytes(_make_excel_bytes(df))

    parsed = read_training_excel(str(path))

    assert set(parsed.columns) == set(["material_code", "material_description", "l0", "l1", "l2"])
    raw_df, labels_df = split_training_dataframe(parsed)
    assert list(labels_df.columns) == ["l0", "l1", "l2"]
    assert not raw_df.empty


def test_read_training_excel_missing_taxonomy_raises(tmp_path):
    cols = list(DEFAULT_TRAINING_RAW_COLS)  # no L0/L1/L2
    df = pd.DataFrame([["286450", "ROD COPPER"]], columns=cols)
    path = tmp_path / "bad_training.xlsx"
    path.write_bytes(_make_excel_bytes(df))

    with pytest.raises(SchemaValidationError):
        read_training_excel(str(path))


def test_read_inference_excel_requires_raw_columns(tmp_path):
    cols = list(DEFAULT_TRAINING_RAW_COLS)
    df = pd.DataFrame([["286450", "ROD COPPER"]], columns=cols)
    path = tmp_path / "inference.xlsx"
    path.write_bytes(_make_excel_bytes(df))

    parsed = read_inference_excel(str(path))
    assert set(parsed.columns) == set(["material_code", "material_description"])

