"""
JalDrishti Database V1 API Routes.

Provides:
- Database Health Check endpoint (/health/db)
- Database Summary endpoint (/db/summary)
- Database Watershed Catalog and Lookup endpoints (/db/watersheds, /db/watersheds/{mws_id})
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging

from ...db.session import check_db_connection, get_db
from ...db.models import MicroWatershed, RiskHistory, IoTReading, Intervention, Alert

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Database V1"])


@router.get("/health/db")
def get_db_health() -> Dict[str, Any]:
    """
    Returns non-blocking diagnostic health status of the PostgreSQL + PostGIS database.
    Includes connection latency, PostGIS extension status, and table record counts.
    """
    return check_db_connection()


@router.get("/db/summary")
def get_db_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns summary statistics of entities currently persisted in the PostgreSQL database.
    """
    try:
        mws_count = db.query(MicroWatershed).count()
        risk_count = db.query(RiskHistory).count()
        iot_count = db.query(IoTReading).count()
        intervention_count = db.query(Intervention).count()
        alert_count = db.query(Alert).count()
        return {
            "status": "connected",
            "micro_watersheds": mws_count,
            "risk_history_records": risk_count,
            "iot_readings": iot_count,
            "interventions": intervention_count,
            "alerts": alert_count,
        }
    except Exception as e:
        logger.debug(f"DB summary query failed: {e}")
        return {
            "status": "unavailable",
            "error": str(e),
            "message": "Database is offline, uninitialized, or unreachable."
        }


@router.get("/db/watersheds")
def list_db_watersheds(
    risk_category: Optional[str] = Query(None, description="Filter by risk category (CRITICAL, HIGH, MODERATE, LOW)"),
    priority: Optional[str] = Query(None, description="Filter by intervention priority"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Queries micro-watersheds persisted in PostgreSQL with optional risk/intervention filters.
    """
    try:
        query = db.query(MicroWatershed)
        if risk_category:
            query = query.filter(MicroWatershed.current_risk_category == risk_category.upper())
        if priority:
            query = query.filter(MicroWatershed.intervention_priority == priority.upper())
        results = query.limit(limit).all()
        return {
            "count": len(results),
            "watersheds": [w.to_dict() for w in results]
        }
    except Exception as e:
        logger.error(f"Failed to query database watersheds: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database query failed (server may be offline): {e}"
        )


@router.get("/db/watersheds/{mws_id}")
def get_db_watershed_detail(
    mws_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieves full detail of a specific micro-watershed from PostgreSQL by canonical ID or display code.
    """
    try:
        mws = db.query(MicroWatershed).filter(
            (MicroWatershed.mws_id == mws_id) | (MicroWatershed.display_code == mws_id)
        ).first()
        if not mws:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Micro-watershed '{mws_id}' not found in database."
            )
        data = mws.to_dict()
        data["recent_risk_history"] = [r.to_dict() for r in mws.risk_history[:12]]
        data["interventions"] = [i.to_dict() for i in mws.interventions]
        data["active_alerts"] = [a.to_dict() for a in mws.alerts if a.is_active]
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query watershed '{mws_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database query failed: {e}"
        )
