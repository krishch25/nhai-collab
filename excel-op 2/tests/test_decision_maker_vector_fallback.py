import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agents.agents import DecisionMakerAgent
from app.db.models import Base, RawData, TaxonomyRule


def make_in_memory_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_decision_maker_uses_vector_when_no_rules(monkeypatch):
    session = make_in_memory_session()

    # No rules in DB, so vector path should be used
    raw = RawData(
        batch_id="b1",
        file_name="f.xlsx",
        row_index=0,
        raw_text="ROD COPPER",
        raw_payload={"material_description": "ROD COPPER"},
    )
    session.add(raw)
    session.commit()
    session.refresh(raw)

    # Stub ChromaDB calls to avoid real vector store
    monkeypatch.setattr(
        "app.agents.agents.upsert_raw_material",
        lambda record_id, document, metadata=None: None,
    )
    monkeypatch.setattr(
        "app.db.vector_store.query_raw_materials",
        lambda query_text, n_results=5, where=None: {
            "ids": [["1"]],
            "distances": [[0.1]],
            "metadatas": [[{}]],
            "documents": [["ROD COPPER"]],
        },
    )

    # Stub LLM to return deterministic JSON (used by DecisionMaker + QC agent)
    class DummyLLM:
        def invoke(self, prompt: str):
            class R:
                content = json.dumps(
                    {
                        "l0": "Direct Spend",
                        "l1": "Direct Raw Material",
                        "l2": "Commodities",
                        "confidence": 0.9,
                        "vector_match_id": "1",
                    }
                )

            return R()

    monkeypatch.setattr("app.agents.agents.get_chat_llm", lambda temperature=0.0: DummyLLM())

    agent = DecisionMakerAgent()
    classified = agent.classify_row(session, raw)

    # Vector path: no rule match, so rule_id is None; taxonomy from LLM
    assert classified.rule_id is None
    assert classified.l0 == "Direct Spend"
    assert classified.l1 == "Direct Raw Material"
    assert classified.l2 == "Commodities"
    assert classified.confidence == 0.9

