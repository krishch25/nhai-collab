"""Endpoints for viewing and managing taxonomy rules."""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import TaxonomyRule
from app.db.session import get_db

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleUpdate(BaseModel):
    description: Optional[str] = None
    l0: Optional[str] = None
    l1: Optional[str] = None
    l2: Optional[str] = None
    confidence: Optional[float] = None
    is_active: Optional[bool] = None


@router.get("/", response_model=List[dict])
def list_rules(
    l0: Optional[str] = Query(None),
    l1: Optional[str] = Query(None),
    l2: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List taxonomy rules with optional filters."""
    q = db.query(TaxonomyRule)
    if l0 is not None:
        q = q.filter(TaxonomyRule.l0 == l0)
    if l1 is not None:
        q = q.filter(TaxonomyRule.l1 == l1)
    if l2 is not None:
        q = q.filter(TaxonomyRule.l2 == l2)
    if active is not None:
        q = q.filter(TaxonomyRule.is_active.is_(active))

    q = q.order_by(TaxonomyRule.id).offset(offset).limit(limit)
    rules = q.all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "condition_expression": r.condition_expression,
            "condition_payload": r.condition_payload,
            "l0": r.l0,
            "l1": r.l1,
            "l2": r.l2,
            "source": r.source,
            "created_by": r.created_by,
            "confidence": r.confidence,
            "is_active": r.is_active,
            "created_at": r.created_at,
        }
        for r in rules
    ]


@router.get("/{rule_id}", response_model=dict)
def get_rule(rule_id: int, db: Annotated[Session, Depends(get_db)] = None):
    """Fetch a single rule by ID."""
    rule = db.get(TaxonomyRule, rule_id)
    if rule is None:
        raise HTTPException(404, f"Rule {rule_id} not found")

    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "condition_expression": rule.condition_expression,
        "condition_payload": rule.condition_payload,
        "l0": rule.l0,
        "l1": rule.l1,
        "l2": rule.l2,
        "source": rule.source,
        "created_by": rule.created_by,
        "confidence": rule.confidence,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
    }


@router.patch("/{rule_id}", response_model=dict)
def update_rule(
    rule_id: int,
    body: RuleUpdate,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Update selected fields on a rule (e.g. confidence, is_active)."""
    rule = db.get(TaxonomyRule, rule_id)
    if rule is None:
        raise HTTPException(404, f"Rule {rule_id} not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)

    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "condition_expression": rule.condition_expression,
        "condition_payload": rule.condition_payload,
        "l0": rule.l0,
        "l1": rule.l1,
        "l2": rule.l2,
        "source": rule.source,
        "created_by": rule.created_by,
        "confidence": rule.confidence,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
    }

