from fastapi import APIRouter, Request, HTTPException, Response
from typing import Optional
import logging

from ..schemas import MwsReport, BasinReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])

@router.get("/basin", response_model=BasinReport, summary="Get comprehensive 66-MWS basin decision report")
def get_basin_report(request: Request):
    """
    Returns full basin-level decision-support report summarizing the official 66
    micro-watersheds, risk distribution, dominant drivers, LULC breakdown, and monitoring status.
    """
    reports_adapter = request.app.state.adapters["reports"]
    return reports_adapter.get_basin_report()

@router.get("/basin/csv", summary="Export 66-MWS basin tabular report as CSV")
def export_basin_report_csv(request: Request):
    """
    Streams a downloadable CSV containing all 66 micro-watersheds and their
    integrated metrics across GIS, Risk, LULC, Water Quality, and Sensors.
    """
    reports_adapter = request.app.state.adapters["reports"]
    csv_data = reports_adapter.export_basin_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="shiggaon_basin_report.csv"'}
    )

@router.get("/mws/{id}", response_model=MwsReport, summary="Get individual micro-watershed decision report")
def get_mws_report(id: str, request: Request):
    """
    Returns full decision-support report for a single micro-watershed by canonical
    id (e.g. g_mws.240575) or display code (e.g. 4D4F2m3). Returns 404 if MWS not in GIS catalog.
    """
    reports_adapter = request.app.state.adapters["reports"]
    report = reports_adapter.get_mws_report(id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Micro-watershed '{id}' not found in official GIS catalog."
        )
    return report

@router.get("/mws/{id}/csv", summary="Export individual micro-watershed report as CSV")
def export_mws_report_csv(id: str, request: Request):
    """
    Streams a downloadable tabular CSV containing decision metrics for the specified micro-watershed.
    """
    reports_adapter = request.app.state.adapters["reports"]
    csv_data = reports_adapter.export_mws_csv(id)
    if not csv_data:
        raise HTTPException(
            status_code=404,
            detail=f"Micro-watershed '{id}' not found in official GIS catalog."
        )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="watershed_report_{id}.csv"'}
    )
