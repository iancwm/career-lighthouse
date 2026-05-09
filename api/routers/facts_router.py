"""Structured-facts query endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query

from dependencies import require_admin_key
from models_facts import FactGroupResponse, FactQueryResponse
from services.fact_store import group_facts, list_facts

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])


def _fact_filters_payload(
    type: str | None,
    employer: str | None,
    school: str | None,
    graduation_year: int | None,
    confidence__gte: int | None,
    source: str | None,
    include_deleted: bool,
    lifecycle: str | None,
    trace_id: str | None,
    source_type: str | None,
    source_label: str | None,
    has_audit_url: bool | None,
) -> dict[str, Any]:
    """Build the filters_applied echo dict for a fact query response."""
    payload: dict[str, Any] = {"include_deleted": include_deleted}
    for key, value in {
        "type": type,
        "employer": employer,
        "school": school,
        "graduation_year": graduation_year,
        "confidence__gte": confidence__gte,
        "source": source,
        "lifecycle": lifecycle,
        "trace_id": trace_id,
        "source_type": source_type,
        "source_label": source_label,
        "has_audit_url": has_audit_url,
    }.items():
        if value is not None:
            payload[key] = value
    return payload


@router.get("/facts", response_model=FactQueryResponse)
def list_facts_endpoint(
    type: str | None = Query(None, alias="type"),
    employer: str | None = Query(None),
    school: str | None = Query(None),
    graduation_year: int | None = Query(None),
    confidence__gte: int | None = Query(None, ge=0, le=100),
    source: str | None = Query(None),
    include_deleted: bool = Query(False),
    lifecycle: str | None = Query(None),
    trace_id: str | None = Query(None),
    source_type: str | None = Query(None),
    source_label: str | None = Query(None),
    has_audit_url: bool | None = Query(None),
):
    """List structured facts from employers and career profiles."""
    facts = list_facts(
        type=type,
        employer=employer,
        school=school,
        graduation_year=graduation_year,
        confidence__gte=confidence__gte,
        source=source,
        include_deleted=include_deleted,
        lifecycle=lifecycle,
        trace_id=trace_id,
        source_type=source_type,
        source_label=source_label,
        has_audit_url=has_audit_url,
    )
    return FactQueryResponse(
        facts=facts,
        total=len(facts),
        filters_applied=_fact_filters_payload(
            type,
            employer,
            school,
            graduation_year,
            confidence__gte,
            source,
            include_deleted,
            lifecycle,
            trace_id,
            source_type,
            source_label,
            has_audit_url,
        ),
    )


@router.get("/facts/grouped", response_model=FactGroupResponse)
def list_grouped_facts_endpoint(
    by: Literal["employer", "type"] = Query("employer"),
    type: str | None = Query(None, alias="type"),
    employer: str | None = Query(None),
    school: str | None = Query(None),
    graduation_year: int | None = Query(None),
    confidence__gte: int | None = Query(None, ge=0, le=100),
    source: str | None = Query(None),
    include_deleted: bool = Query(False),
    lifecycle: str | None = Query(None),
    trace_id: str | None = Query(None),
    source_type: str | None = Query(None),
    source_label: str | None = Query(None),
    has_audit_url: bool | None = Query(None),
):
    """Group structured facts by employer slug or fact type."""
    facts = list_facts(
        type=type,
        employer=employer,
        school=school,
        graduation_year=graduation_year,
        confidence__gte=confidence__gte,
        source=source,
        include_deleted=include_deleted,
        lifecycle=lifecycle,
        trace_id=trace_id,
        source_type=source_type,
        source_label=source_label,
        has_audit_url=has_audit_url,
    )
    grouped = group_facts(facts, by=by)
    return FactGroupResponse(
        by=by,
        groups=grouped,
        total=len(facts),
        filters_applied=_fact_filters_payload(
            type,
            employer,
            school,
            graduation_year,
            confidence__gte,
            source,
            include_deleted,
            lifecycle,
            trace_id,
            source_type,
            source_label,
            has_audit_url,
        ),
    )
