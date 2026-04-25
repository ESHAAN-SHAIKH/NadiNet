"""
Reports API — /api/v1/reports/monthly
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.database import get_db
from app.services.reporting import gather_monthly_stats, generate_pdf, generate_csv

router = APIRouter()


@router.get("/reports/monthly")
async def get_monthly_report(
    year: int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month),
    format: str = Query(default="pdf", pattern="^(pdf|csv)$"),
    db: AsyncSession = Depends(get_db),
):
    """Generate monthly funder report as PDF or CSV."""
    stats = await gather_monthly_stats(db, year, month)

    if format == "csv":
        content = generate_csv(stats)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=nadinet_{year}_{month:02d}.csv"},
        )
    else:
        content = generate_pdf(stats)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=nadinet_{year}_{month:02d}.pdf"},
        )
