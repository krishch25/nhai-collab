"""DB initialization: create tables and optionally seed sample data for dev."""

import os

from app.db.models import Base
from app.db.session import engine, SessionLocal


def create_tables() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """Drop all tables. Use with caution."""
    Base.metadata.drop_all(bind=engine)


def seed_sample_data() -> None:
    """Seed minimal sample data for local development."""
    from app.db.models import RawData, TaxonomyRule

    db = SessionLocal()
    try:
        # Skip if data already exists
        if db.query(TaxonomyRule).first() is not None:
            return

        # Sample taxonomy rules
        rules = [
            TaxonomyRule(
                name="rule_copper_raw",
                description="Match copper raw materials",
                condition_expression="material_description CONTAINS 'copper' OR material_code LIKE '28%'",
                condition_payload={"type": "contains", "field": "material_description", "value": "copper"},
                l0="Direct Spend",
                l1="Direct Raw Material",
                l2="Commodities",
                source="agent",
                created_by="system",
                confidence=0.95,
                is_active=True,
            ),
            TaxonomyRule(
                name="rule_solar_panel",
                description="Match solar panel materials",
                condition_expression="material_description CONTAINS 'solar' OR material_description CONTAINS 'SPV'",
                condition_payload={"type": "contains", "field": "material_description", "value": "solar"},
                l0="Direct Spend",
                l1="FG/Assemblies",
                l2="Solar",
                source="agent",
                created_by="system",
                confidence=0.92,
                is_active=True,
            ),
        ]
        for r in rules:
            db.add(r)

        # Sample raw data (optional, for testing)
        raw = RawData(
            batch_id="dev-seed-batch",
            file_name="sample_training.xlsx",
            row_index=0,
            raw_text="ROD COPPER EC GRADE 8mm ROUND",
            raw_payload={"material_code": "286450", "description": "ROD COPPER EC GRADE 8mm ROUND"},
        )
        db.add(raw)
        db.commit()
    finally:
        db.close()


def init_db(seed: bool = False) -> None:
    """
    Initialize database: create tables and optionally seed sample data.
    Set SEED_DEV_DATA=1 to seed sample data.
    """
    create_tables()
    if seed or os.environ.get("SEED_DEV_DATA", "").lower() in ("1", "true", "yes"):
        seed_sample_data()
