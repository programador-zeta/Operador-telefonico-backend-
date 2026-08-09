import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.config import Settings, get_settings


logger = logging.getLogger(__name__)


def _whatsapp_address(phone: str) -> str:
    if phone.startswith("whatsapp:"):
        return phone
    return f"whatsapp:{phone}"


def _twilio_whatsapp_recipient(phone: str) -> str:
    """Format a destination for Twilio's WhatsApp channel.

    Twilio requires Mexican mobile WhatsApp destinations to include the legacy
    mobile marker after the country code (``+521``), even though the canonical
    phone number stored by the application remains ``+52``.
    """
    address = _whatsapp_address(phone)
    if address.startswith("whatsapp:+52") and not address.startswith("whatsapp:+521"):
        local_number = address.removeprefix("whatsapp:+52")
        if len(local_number) == 10:
            return f"whatsapp:+521{local_number}"
    return address


def _appointment_template_variables(starts_at: str) -> dict[str, str]:
    appointment_time = datetime.fromisoformat(starts_at)
    return {
        "1": appointment_time.strftime("%d/%m/%Y"),
        "2": appointment_time.strftime("%H:%M"),
    }


def send_appointment_confirmation(
    appointment: dict[str, Any],
    *,
    settings: Settings | None = None,
    client_factory: Callable[[str, str], Any] | None = None,
) -> dict[str, str]:
    """Send a WhatsApp template without risking the saved appointment.

    Delivery failures are reported to the caller, but never raise. The appointment
    remains valid even if Twilio is unavailable.
    """
    settings = settings or get_settings()
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return {"status": "not_configured"}
    if not settings.twilio_whatsapp_from or not settings.twilio_appointment_content_sid:
        return {"status": "not_configured"}

    try:
        if client_factory is None:
            # Import lazily so local development works before Twilio is configured.
            from twilio.rest import Client

            client_factory = Client

        client = client_factory(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
        )
        message = client.messages.create(
            from_=_whatsapp_address(settings.twilio_whatsapp_from),
            to=_twilio_whatsapp_recipient(appointment["customer_phone"]),
            content_sid=settings.twilio_appointment_content_sid,
            content_variables=json.dumps(
                _appointment_template_variables(appointment["starts_at"]),
                separators=(",", ":"),
            ),
        )
        return {"status": "sent", "message_sid": str(message.sid)}
    except Exception as exc:
        logger.warning("WhatsApp confirmation could not be sent: %s", exc)
        return {"status": "failed"}
