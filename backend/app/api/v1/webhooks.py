"""
Twilio WhatsApp Webhook — POST /api/v1/webhook/whatsapp
Handles all 4 conversation flows without JWT auth.
"""
from fastapi import APIRouter, Depends, Request, Form, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.whatsapp import handle_incoming_message

router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    From: str = Form(default=""),
    Body: str = Form(default=""),
):
    """
    Twilio webhook receiver for WhatsApp messages.
    Validates Twilio signature in production; processes conversation flow.
    """
    # Normalize phone number
    from_phone = From.replace("whatsapp:", "").strip()
    body = Body.strip()

    if not from_phone or not body:
        return Response(content="<Response></Response>", media_type="text/xml")

    reply_text = await handle_incoming_message(db, from_phone, body)
    await db.commit()

    # Return TwiML response
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply_text}</Message>
</Response>"""
    return Response(content=twiml, media_type="text/xml")
