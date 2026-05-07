"""Rule engine for evaluating TaxonomyRule objects against RawData rows.

This module intentionally supports a small, explicit set of condition types
so that rule evaluation remains safe and predictable in production.
"""

from __future__ import annotations

from typing import Any, Dict

from app.db.models import RawData, TaxonomyRule


def _get_field(payload: Dict[str, Any], field: str) -> Any:
    """Safe helper to read a nested field from raw_payload using dot-notation."""
    parts = field.split(".")
    value: Any = payload
    for part in parts:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def evaluate_rule(rule: TaxonomyRule, raw: RawData) -> bool:
    """Return True if `rule` matches the given `raw` record, else False.

    Currently, only `condition_payload` is evaluated. Supported formats:

        {
          "type": "contains",
          "field": "material_description",
          "value": "copper",
          "case_insensitive": true
        }

        {
          "type": "equals",
          "field": "plant_code",
          "value": "1000"
        }

        {
          "type": "in_list",
          "field": "supplier_name",
          "values": ["ABC", "XYZ"]
        }

        {
          "type": "startswith" | "endswith",
          "field": "material_code",
          "value": "28"
        }

        {
          "type": "regex",
          "field": "material_description",
          "pattern": "copper.*rod"
        }

    Complex logical combinations (AND/OR) can be expressed by composing multiple
    simple rules; we keep the evaluator simple for robustness.
    """

    payload = rule.condition_payload or {}
    if not payload:
        # If no structured payload is present, we currently do not attempt to
        # interpret `condition_expression` for safety.
        return False

    ctype = (payload.get("type") or "").lower()
    field = payload.get("field") or ""
    if not ctype or not field:
        return False

    value = _get_field(raw.raw_payload or {}, field)

    # Normalise for string comparisons
    if isinstance(value, str):
        value_str = value
    elif value is None:
        value_str = ""
    else:
        value_str = str(value)

    if ctype == "contains":
        needle = str(payload.get("value") or "")
        if not needle:
            return False
        case_insensitive = bool(payload.get("case_insensitive", True))
        haystack = value_str.lower() if case_insensitive else value_str
        target = needle.lower() if case_insensitive else needle
        return target in haystack

    if ctype == "equals":
        target = payload.get("value")
        return value == target

    if ctype == "in_list":
        values = payload.get("values") or []
        return value in values

    if ctype == "startswith":
        prefix = str(payload.get("value") or "")
        return bool(prefix) and value_str.startswith(prefix)

    if ctype == "endswith":
        suffix = str(payload.get("value") or "")
        return bool(suffix) and value_str.endswith(suffix)

    if ctype == "regex":
        import re

        pattern = payload.get("pattern")
        if not pattern:
            return False
        flags = re.IGNORECASE if payload.get("case_insensitive", True) else 0
        return re.search(pattern, value_str, flags) is not None

    # Unknown type – conservative default is "no match"
    return False

