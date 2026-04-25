"""
Reporting Service — PDF and CSV funder reports.
Uses ReportLab for PDF generation with ASCII bar charts to avoid matplotlib.
"""
import csv
import io
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.need import Need
from app.models.task import Task
from app.models.debrief import Debrief
from app.models.volunteer import Volunteer
from app.models.signal import Signal
from app.config import settings

logger = logging.getLogger(__name__)


async def gather_monthly_stats(db: AsyncSession, year: int, month: int) -> dict:
    """Gather all stats for the monthly report."""
    from calendar import monthrange
    import datetime as dt

    start = dt.datetime(year, month, 1, tzinfo=timezone.utc)
    end_day = monthrange(year, month)[1]
    end = dt.datetime(year, month, end_day, 23, 59, 59, tzinfo=timezone.utc)

    # Needs stats
    stmt_needs = select(func.count()).select_from(Need).where(
        and_(Need.created_at >= start, Need.created_at <= end)
    )
    total_needs = (await db.execute(stmt_needs)).scalar() or 0

    stmt_resolved = select(func.count()).select_from(Need).where(
        and_(Need.status == "resolved", Need.updated_at >= start, Need.updated_at <= end)
    )
    resolved_needs = (await db.execute(stmt_resolved)).scalar() or 0

    # Tasks stats
    stmt_tasks = select(func.count()).select_from(Task).where(
        and_(Task.dispatched_at >= start, Task.dispatched_at <= end)
    )
    total_tasks = (await db.execute(stmt_tasks)).scalar() or 0

    stmt_complete = select(func.count()).select_from(Task).where(
        and_(Task.status == "complete", Task.completed_at >= start, Task.completed_at <= end)
    )
    completed_tasks = (await db.execute(stmt_complete)).scalar() or 0

    # Debriefs
    stmt_debrief = select(func.count()).select_from(Debrief).where(
        and_(Debrief.submitted_at >= start, Debrief.submitted_at <= end)
    )
    total_debriefs = (await db.execute(stmt_debrief)).scalar() or 0

    stmt_people = select(func.sum(Debrief.people_helped)).where(
        and_(Debrief.submitted_at >= start, Debrief.submitted_at <= end)
    )
    people_helped = (await db.execute(stmt_people)).scalar() or 0

    # Top 5 needs by priority
    stmt_top_needs = select(Need).where(
        and_(Need.status == "active")
    ).order_by(Need.priority_score.desc()).limit(5)
    top_needs_result = await db.execute(stmt_top_needs)
    top_needs = top_needs_result.scalars().all()

    # Active volunteers
    stmt_vols = select(func.count()).select_from(Volunteer).where(Volunteer.is_available == True)
    active_vols = (await db.execute(stmt_vols)).scalar() or 0

    return {
        "year": year,
        "month": month,
        "ngo_name": settings.NGO_NAME,
        "total_needs": total_needs,
        "resolved_needs": resolved_needs,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "total_debriefs": total_debriefs,
        "people_helped": people_helped,
        "active_volunteers": active_vols,
        "top_needs": [
            {
                "zone": n.zone_id,
                "category": n.need_category,
                "score": n.priority_score,
                "status": n.status,
            }
            for n in top_needs
        ],
    }


def _ascii_bar(value: int, max_value: int, width: int = 20) -> str:
    """Generate ASCII progress bar."""
    if max_value == 0:
        filled = 0
    else:
        filled = int((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)


def generate_csv(stats: dict) -> bytes:
    """Generate CSV report from stats dict."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["NadiNet Monthly Report", f"{stats['month']:02d}/{stats['year']}"])
    writer.writerow(["Organization", stats["ngo_name"]])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Needs Identified", stats["total_needs"]])
    writer.writerow(["Needs Resolved", stats["resolved_needs"]])
    writer.writerow(["Tasks Dispatched", stats["total_tasks"]])
    writer.writerow(["Tasks Completed", stats["completed_tasks"]])
    writer.writerow(["Debriefs Received", stats["total_debriefs"]])
    writer.writerow(["People Helped", stats["people_helped"]])
    writer.writerow(["Active Volunteers", stats["active_volunteers"]])
    writer.writerow([])
    writer.writerow(["Top Active Needs"])
    writer.writerow(["Zone", "Category", "Priority Score", "Status"])
    for n in stats["top_needs"]:
        writer.writerow([n["zone"], n["category"], n["score"], n["status"]])

    return output.getvalue().encode("utf-8")


def generate_pdf(stats: dict) -> bytes:
    """Generate PDF report using ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import calendar

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        month_name = calendar.month_name[stats["month"]]

        # Cover page
        title_style = ParagraphStyle("Title", fontSize=24, spaceAfter=20, alignment=TA_CENTER)
        story.append(Paragraph(stats["ngo_name"], title_style))
        story.append(Paragraph(f"Monthly Report — {month_name} {stats['year']}", styles["Heading2"]))
        story.append(Spacer(1, 1 * cm))

        # Summary metrics table
        summary_data = [
            ["Metric", "Value"],
            ["Total Needs Identified", str(stats["total_needs"])],
            ["Needs Resolved", str(stats["resolved_needs"])],
            ["Tasks Dispatched", str(stats["total_tasks"])],
            ["Tasks Completed", str(stats["completed_tasks"])],
            ["Debriefs Received", str(stats["total_debriefs"])],
            ["People Helped (Est.)", str(stats["people_helped"])],
            ["Active Volunteers", str(stats["active_volunteers"])],
        ]
        summary_table = Table(summary_data, colWidths=[10 * cm, 6 * cm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 1 * cm))

        # ASCII Response time chart
        story.append(Paragraph("Completion Rate", styles["Heading2"]))
        max_val = max(stats["total_tasks"], 1)
        bar_text = (
            f"Dispatched: {_ascii_bar(stats['total_tasks'], max_val)} {stats['total_tasks']}\n"
            f"Completed:  {_ascii_bar(stats['completed_tasks'], max_val)} {stats['completed_tasks']}\n"
            f"Debriefed:  {_ascii_bar(stats['total_debriefs'], max_val)} {stats['total_debriefs']}"
        )
        story.append(Paragraph(f"<font face='Courier' size='9'><pre>{bar_text}</pre></font>", styles["Normal"]))
        story.append(Spacer(1, 1 * cm))

        # Top 5 needs
        story.append(Paragraph("Top 5 Active Needs", styles["Heading2"]))
        needs_data = [["Zone", "Category", "Priority Score", "Status"]]
        for n in stats["top_needs"]:
            needs_data.append([n["zone"], n["category"].replace("_", " ").title(), str(n["score"]), n["status"].title()])
        needs_table = Table(needs_data, colWidths=[4 * cm, 5 * cm, 4 * cm, 4 * cm])
        needs_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(needs_table)

        doc.build(story)
        return buffer.getvalue()

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        # Fallback: return CSV as PDF-named bytes
        return generate_csv(stats)
