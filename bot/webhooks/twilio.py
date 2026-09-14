"""Twilio WhatsApp webhook — the only Twilio-aware code in the project.

It contains no knowledge of bus routes: it authenticates the request, dedupes
retries, hands the text to the conversation engine and renders the reply as
TwiML.
"""

import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from bot.conversation import render
from bot.conversation.machine import dispatch, get_session
from bot.models import MessageLog
from bot.services.booking import get_or_create_profile

log = logging.getLogger("bot")


def _is_signed_by_twilio(request) -> bool:
    """Verify X-Twilio-Signature so a leaked ngrok URL can't be driven by anyone."""
    if not settings.TWILIO_VALIDATE_SIGNATURE:
        return True
    auth_token = settings.TWILIO_AUTH_TOKEN
    if not auth_token:
        log.warning("TWILIO_AUTH_TOKEN unset; rejecting webhook call")
        return False

    validator = RequestValidator(auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    # Twilio signs the URL it called — behind ngrok that is the public URL,
    # not the local one Django reconstructs from the request.
    url = settings.PUBLIC_BASE_URL.rstrip("/") + request.get_full_path()
    return validator.validate(url, request.POST.dict(), signature)


@csrf_exempt  # Twilio cannot supply a CSRF token; the signature check replaces it.
@require_POST
def whatsapp_webhook(request):
    if not _is_signed_by_twilio(request):
        log.warning("Rejected unsigned webhook call from %s", request.META.get("REMOTE_ADDR"))
        return HttpResponseForbidden("Invalid Twilio signature")

    from_number = (request.POST.get("From") or "").replace("whatsapp:", "").strip()
    body = (request.POST.get("Body") or "").strip()
    message_sid = (request.POST.get("MessageSid") or "").strip()
    profile_name = (request.POST.get("ProfileName") or "").strip()

    if not from_number:
        return HttpResponse(str(MessagingResponse()), content_type="application/xml")

    # Twilio retries on timeout or a non-2xx response. Without this check a
    # retry would run the booking a second time.
    if message_sid and MessageLog.objects.filter(
        twilio_sid=message_sid, direction=MessageLog.Direction.IN
    ).exists():
        log.info("Duplicate MessageSid %s ignored", message_sid)
        return HttpResponse(str(MessagingResponse()), content_type="application/xml")

    session = get_session(from_number)
    if session.profile is None:
        session.profile = get_or_create_profile(from_number, profile_name)
        session.save(update_fields=["profile"])

    state_before = session.state
    MessageLog.objects.create(
        whatsapp_number=from_number,
        direction=MessageLog.Direction.IN,
        body=body,
        twilio_sid=message_sid,
        state_before=state_before,
    )

    try:
        reply = dispatch(session, body)
    except Exception:
        # A crash must not leave the user with silence; Twilio would also retry.
        log.exception("Conversation engine failed for %s", from_number)
        reply_messages = [
            "😕 Something went wrong on our side. Send MENU to start again."
        ]
        reply_state = state_before
    else:
        reply_messages = reply.messages
        reply_state = reply.state

    twiml = MessagingResponse()
    for message in reply_messages:
        for part in render.split_message(message):
            twiml.message(part)

    MessageLog.objects.create(
        whatsapp_number=from_number,
        direction=MessageLog.Direction.OUT,
        body="\n\n".join(reply_messages),
        twilio_sid=message_sid,
        state_before=state_before,
        state_after=reply_state,
    )

    return HttpResponse(str(twiml), content_type="application/xml")
