"""
WhatsApp Service — Twilio send/receive helper.
Manages 4 conversation flows via state machine stored in PostgreSQL.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models.conversation import Conversation
from app.models.reporter import Reporter
from app.models.volunteer import Volunteer
from app.models.task import Task
from app.models.need import Need
from app.services.nlp_classifier import classify_report, classify_update_text, extract_signals_from_debrief
from app.services.ingestion import ingest_whatsapp, get_or_create_reporter

logger = logging.getLogger(__name__)

CONVERSATION_TTL_HOURS = 2

SKILLS_MAP = {
    "1": "first_aid",
    "2": "transport",
    "3": "nutrition",
    "4": "elder_care",
    "5": "education",
    "6": "construction",
    "7": "counseling",
    "8": "general",
}


def send_whatsapp_message(to: str, body: str) -> bool:
    """
    Send a WhatsApp message via Twilio.
    If TWILIO_ACCOUNT_SID is not set, prints to stdout (local dev mode).
    """
    if not settings.TWILIO_ACCOUNT_SID.strip():
        # ── Local / offline mode ─────────────────────────────────────────────
        print(f"\n📱 [WhatsApp MOCK] To: {to}\n{body}\n{'─'*60}")
        logger.info(f"[MOCK] WhatsApp to {to}: {body[:80]}")
        return True

    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=body,
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{to}" if not to.startswith("whatsapp:") else to,
        )
        logger.info(f"Sent WhatsApp to {to}: SID={message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp to {to}: {e}")
        return False


async def get_or_create_conversation(db: AsyncSession, phone: str) -> Conversation:
    """Get or create conversation state for a phone number."""
    now = datetime.now(timezone.utc)
    stmt = select(Conversation).where(Conversation.phone == phone)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        conv = Conversation(
            phone=phone,
            state="IDLE",
            context={},
            expires_at=now + timedelta(hours=CONVERSATION_TTL_HOURS),
            updated_at=now,
        )
        db.add(conv)
        await db.flush()
        return conv

    # Check expiry
    if conv.expires_at.tzinfo is None:
        conv.expires_at = conv.expires_at.replace(tzinfo=timezone.utc)
    if now > conv.expires_at:
        conv.state = "IDLE"
        conv.context = {}

    conv.expires_at = now + timedelta(hours=CONVERSATION_TTL_HOURS)
    conv.updated_at = now
    return conv


async def handle_incoming_message(
    db: AsyncSession,
    from_phone: str,
    body: str,
) -> str:
    """
    Main dispatcher for incoming WhatsApp messages.
    Returns the reply text to send back.
    """
    body_clean = body.strip()
    conv = await get_or_create_conversation(db, from_phone)

    # Check if there's a known reporter
    stmt_reporter = select(Reporter).where(Reporter.phone == from_phone)
    result_r = await db.execute(stmt_reporter)
    reporter = result_r.scalar_one_or_none()

    # Check if there's a known volunteer
    stmt_vol = select(Volunteer).where(Volunteer.phone == from_phone)
    result_v = await db.execute(stmt_vol)
    volunteer = result_v.scalar_one_or_none()

    state = conv.state

    # ─── FLOW 3: Task acceptance/decline ───
    if state == "AWAITING_TASK":
        return await _handle_awaiting_task(db, conv, volunteer, body_clean)

    # ─── FLOW 4: Debrief ───
    if state.startswith("DEBRIEFING"):
        return await _handle_debriefing(db, conv, volunteer, body_clean)

    # ─── FLOW: Reverification ───
    if state == "AWAITING_REVERIFICATION":
        return await _handle_reverification(db, conv, body_clean)

    # ─── FLOW 2: Registration in progress ───
    if state.startswith("REGISTERING"):
        return await _handle_registration(db, conv, from_phone, body_clean)

    # ─── New number — start registration ───
    if not reporter and not volunteer:
        conv.state = "REGISTERING_1"
        conv.context = {}
        return (
            "Welcome to NadiNet! 🌟\n"
            "I'll help connect you with your community.\n\n"
            "What's your name?"
        )

    # ─── FLOW 1: Field reporting (known reporter or volunteer) ───
    return await _handle_field_report(db, conv, reporter or volunteer, from_phone, body_clean)


async def _handle_field_report(db, conv, reporter, phone: str, body: str) -> str:
    """Flow 1: Parse field report, classify, confirm."""
    if body in ["1", "YES", "yes", "y"]:
        # Confirmed
        conv.state = "IDLE"
        return "✅ Confirmed and logged. Thank you!"

    if body in ["2", "NO", "no", "n"]:
        conv.state = "IDLE"
        return "Okay, the report has been discarded. Please send a corrected message."

    if body in ["3", "EDIT", "edit"]:
        conv.state = "REPORTING"
        return "Please resend your corrected report:"

    if conv.state == "REPORTING":
        conv.state = "IDLE"
        # Re-classify
        pass

    # New report
    signal, classification = await ingest_whatsapp(db, phone, body)
    conv.context = {"last_signal_id": str(signal.id)}

    if classification.get("confidence", 0) >= 0.6:
        conv.state = "REPORTING"
        return (
            f"Got it. Logged: *{classification['need_category'].replace('_', ' ').title()}* "
            f"in {classification.get('zone_id', 'Unknown')} "
            f"(urgency {classification.get('urgency', '?')}/5).\n"
            f"Is this correct? Reply 1=Yes 2=No 3=Edit"
        )
    else:
        conv.state = "REPORTING"
        return (
            "Thanks. I wasn't sure how to categorize this. "
            "What type of issue is this?\n"
            "1=Medical 2=Nutrition 3=Water 4=Elderly care 5=Other"
        )


async def _handle_registration(db, conv, phone: str, body: str) -> str:
    """Flow 2: Multi-step volunteer registration."""
    state = conv.state
    ctx = conv.context

    if state == "REGISTERING_1":
        ctx["name"] = body
        conv.state = "REGISTERING_2"
        return (
            f"Nice to meet you, {body}! 👋\n\n"
            "What are your skills? Reply with numbers separated by spaces (e.g. 1 3 5):\n"
            "1=First aid  2=Transport  3=Nutrition  4=Elder care\n"
            "5=Education  6=Construction  7=Counseling  8=General"
        )

    elif state == "REGISTERING_2":
        skill_nums = body.strip().split()
        skills = [SKILLS_MAP[n] for n in skill_nums if n in SKILLS_MAP]
        ctx["skills"] = skills
        conv.state = "REGISTERING_3"
        return "Do you have your own transport? 1=Yes 2=No"

    elif state == "REGISTERING_3":
        ctx["has_transport"] = body.strip() == "1"
        conv.state = "REGISTERING_4"
        return "Which zone do you mainly work in? (e.g. Zone 4, Dharavi, Kurla East)"

    elif state == "REGISTERING_4":
        ctx["zone_id"] = body.strip()
        conv.state = "REGISTERING_5"
        return "What days are you usually available? (e.g. Mon Wed Fri)"

    elif state == "REGISTERING_5":
        days_text = body.strip()
        # Build schedule from text
        day_names = {"mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
                     "fri": "fri", "sat": "sat", "sun": "sun"}
        schedule = {}
        for word in days_text.lower().split():
            for key in day_names:
                if key in word:
                    schedule[key] = [{"start": "09:00", "end": "17:00"}]

        volunteer = Volunteer(
            phone=phone,
            name=ctx.get("name", ""),
            skills=ctx.get("skills", []),
            languages=["hindi", "english"],
            has_transport=ctx.get("has_transport", False),
            zone_id=ctx.get("zone_id"),
            availability_schedule=schedule if schedule else None,
        )
        db.add(volunteer)
        await db.flush()

        conv.state = "IDLE"
        conv.context = {}
        return (
            f"🎉 Welcome to NadiNet, {ctx.get('name', '')}!\n"
            f"Skills: {', '.join(ctx.get('skills', []) or ['general'])}\n"
            f"Zone: {ctx.get('zone_id', 'Unknown')}\n"
            "You'll receive dispatch requests when there's a need in your area."
        )

    return "I didn't understand that. Please try again."


async def _handle_awaiting_task(db, conv, volunteer, body: str) -> str:
    """Flow 3: Task accept/decline."""
    ctx = conv.context
    task_id = ctx.get("task_id")
    if not task_id:
        conv.state = "IDLE"
        return "No pending task found."

    task = await db.get(Task, task_id)
    if not task:
        conv.state = "IDLE"
        return "Task not found."

    now = datetime.now(timezone.utc)

    if body.strip() in ["1", "YES", "yes", "y"]:
        task.status = "accepted"
        task.accepted_at = now
        conv.state = "IDLE"
        return (
            "✅ Task accepted!\n"
            "Please head to your assigned zone and help the community.\n"
            "Reply DONE when you're finished."
        )
    else:
        task.status = "declined"
        conv.state = "IDLE"

        # Spec §6: On reply=NO or no reply in 30min → cascade to next candidate
        need = await db.get(Need, task.need_id)
        if need:
            from app.services.matching import cascade_to_next_candidate
            await cascade_to_next_candidate(
                db=db,
                need=need,
                declined_volunteer_id=task.volunteer_id,
                required_skills=[],
            )

        return "Understood. The request has been passed to the next volunteer."


async def _handle_debriefing(db, conv, volunteer, body: str) -> str:
    """Flow 4: Post-task debrief."""
    from app.models.debrief import Debrief
    state = conv.state
    ctx = conv.context

    if state == "DEBRIEFING_1":
        resolution_map = {"1": "resolved", "2": "partial", "3": "unresolved"}
        resolution = resolution_map.get(body.strip(), "partial")
        ctx["resolution"] = resolution
        conv.state = "DEBRIEFING_2"
        return "Roughly how many people did you help? (enter a number)"

    elif state == "DEBRIEFING_2":
        try:
            ctx["people_helped"] = int(body.strip())
        except Exception:
            ctx["people_helped"] = None
        conv.state = "DEBRIEFING_3"
        return "Anything the coordinator should know? (or reply SKIP)"

    elif state == "DEBRIEFING_3":
        notes = None if body.strip().upper() == "SKIP" else body.strip()
        ctx["notes"] = notes

        # Create debrief record
        task_id = ctx.get("task_id")
        task = await db.get(Task, task_id) if task_id else None

        if task and volunteer:
            # Extract new signals from notes
            if notes:
                need = await db.get(Task, task.need_id)
                new_signals = await extract_signals_from_debrief(
                    notes,
                    ctx.get("need_category", "other"),
                    ctx.get("zone_id", "Unknown")
                )
                if new_signals:
                    from app.services.ingestion import ingest_manual
                    for ns in new_signals:
                        await ingest_manual(
                            db=db,
                            zone_id=ctx.get("zone_id", "Unknown"),
                            need_category=ns.get("need_category", "other"),
                            urgency=ns.get("urgency", 3),
                            population_est=None,
                            raw_text=ns.get("description"),
                            reporter_id=None,
                        )

            debrief = Debrief(
                task_id=task.id,
                volunteer_id=volunteer.id,
                need_id=task.need_id,
                resolution=ctx.get("resolution", "partial"),
                people_helped=ctx.get("people_helped"),
                notes=notes,
            )
            db.add(debrief)
            task.status = "complete"
            task.completed_at = datetime.now(timezone.utc)
            await db.flush()

            # Update kinship + reporter trust
            from app.services.kinship import update_kinship_edges, update_reporter_trust
            await update_kinship_edges(db, str(task.id), ctx.get("resolution", "partial"))
            await update_reporter_trust(db, str(task.need_id), ctx.get("resolution", "partial"))

        conv.state = "IDLE"
        conv.context = {}
        return "🙏 Thank you for your debrief! Your work makes a difference."

    return "I didn't understand. Please try again."


async def _handle_reverification(db, conv, body: str) -> str:
    """Handle reverification response: 1=YES 2=NO 3=CHANGED."""
    from datetime import timezone
    from app.models.need import Need

    ctx = conv.context
    need_id = ctx.get("need_id")

    if not need_id:
        conv.state = "IDLE"
        return "Thank you for your response!"

    need = await db.get(Need, need_id)
    if not need:
        conv.state = "IDLE"
        return "Thank you!"

    now = datetime.now(timezone.utc)

    if body.strip() == "1":
        # Still happening — reset decay clock
        need.last_corroborated = now
        from app.services.decay import compute_t_score
        need.t_score = 1.0
        conv.state = "IDLE"
        return "Thanks for confirming! The need has been refreshed in our system."

    elif body.strip() == "2":
        # Resolved
        need.status = "resolved"
        conv.state = "IDLE"
        return "Great news! We've marked this as resolved. Thank you for the update."

    elif body.strip() == "3":
        conv.state = "AWAITING_REVERIFICATION_UPDATE"
        ctx["original_text"] = need.zone_id  # Store context
        return "Please describe what has changed:"

    elif conv.state == "AWAITING_REVERIFICATION_UPDATE":
        original = ctx.get("original_text", "")
        update = await classify_update_text(original, body)
        need.need_category = update.get("need_category", need.need_category)
        need.last_corroborated = now
        need.t_score = 1.0
        conv.state = "IDLE"
        return f"Thanks! Updated the need to: {update.get('need_category', 'other')}. Summary: {update.get('summary', '')}"

    return "Please reply 1=YES (still happening), 2=NO (resolved), 3=CHANGED"


async def send_dispatch_message(
    volunteer: Volunteer,
    need_category: str,
    zone_id: str,
    task_id: str,
    db: AsyncSession,
) -> None:
    """Send dispatch request and update conversation state."""
    conv = await get_or_create_conversation(db, volunteer.phone)
    conv.state = "AWAITING_TASK"
    conv.context = {"task_id": task_id, "need_category": need_category, "zone_id": zone_id}

    body = (
        f"Hi {volunteer.name}, there's a {need_category.replace('_', ' ')} "
        f"need in {zone_id} near you. Est. 2-4 hours. "
        f"Can you help? Reply 1=YES 2=NO"
    )
    send_whatsapp_message(volunteer.phone, body)


async def send_reverification_message(
    reporter: Reporter,
    need_category: str,
    zone_id: str,
    need_id: str,
    days_elapsed: int,
    db: AsyncSession,
) -> None:
    """Send reverification ping to original reporter."""
    conv = await get_or_create_conversation(db, reporter.phone)
    conv.state = "AWAITING_REVERIFICATION"
    conv.context = {"need_id": need_id}

    from datetime import date
    reported_date = date.today().isoformat()

    body = (
        f"Hi {reporter.name or 'there'}, the {need_category.replace('_', ' ')} issue "
        f"you reported in {zone_id} on {reported_date} hasn't been updated in "
        f"{days_elapsed} days. Is it still an issue?\n"
        f"Reply 1=YES (still happening), 2=NO (resolved), 3=CHANGED (situation changed)"
    )
    send_whatsapp_message(reporter.phone, body)
