from app.db.models import RawData, TaxonomyRule
from app.services.rule_engine import evaluate_rule


def make_raw(payload: dict) -> RawData:
    return RawData(batch_id="b1", file_name="f.xlsx", row_index=0, raw_text="", raw_payload=payload)


def test_contains_rule_matches_case_insensitive():
    rule = TaxonomyRule(
        name="contains_copper",
        condition_payload={
            "type": "contains",
            "field": "material_description",
            "value": "copper",
            "case_insensitive": True,
        },
    )
    raw = make_raw({"material_description": "ROD COPPER EC GRADE"})

    assert evaluate_rule(rule, raw) is True


def test_equals_rule_exact_match():
    rule = TaxonomyRule(
        name="plant_1000",
        condition_payload={"type": "equals", "field": "plant_code", "value": "1000"},
    )
    raw = make_raw({"plant_code": "1000"})
    assert evaluate_rule(rule, raw) is True

    raw2 = make_raw({"plant_code": "1200"})
    assert evaluate_rule(rule, raw2) is False


def test_in_list_rule():
    rule = TaxonomyRule(
        name="preferred_supplier",
        condition_payload={
            "type": "in_list",
            "field": "supplier_name",
            "values": ["SUP1", "SUP2"],
        },
    )
    raw = make_raw({"supplier_name": "SUP2"})
    assert evaluate_rule(rule, raw) is True

