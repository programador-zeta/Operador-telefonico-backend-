import unittest
from types import SimpleNamespace

from app.notifications import send_appointment_confirmation


class FakeMessages:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(sid="SM-test-message")


class WhatsAppNotificationTests(unittest.TestCase):
    def settings(self, **overrides):
        values = {
            "twilio_account_sid": "AC-test",
            "twilio_auth_token": "secret-test-token",
            "twilio_whatsapp_from": "whatsapp:+14155238886",
            "twilio_appointment_content_sid": "HX-test-template",
            "business_name": "Clínica Nova",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def appointment(self):
        return {
            "customer_name": "Giovani Cárdenas",
            "customer_phone": "+525512345678",
            "service": "Consulta general",
            "starts_at": "2026-08-10T16:30:00-06:00",
        }

    def test_sends_personalized_template(self) -> None:
        messages = FakeMessages()
        client = SimpleNamespace(messages=messages)

        result = send_appointment_confirmation(
            self.appointment(),
            settings=self.settings(),
            client_factory=lambda _sid, _token: client,
        )

        self.assertEqual(result, {"status": "sent", "message_sid": "SM-test-message"})
        self.assertEqual(messages.kwargs["to"], "whatsapp:+5215512345678")
        self.assertEqual(messages.kwargs["from_"], "whatsapp:+14155238886")
        self.assertEqual(messages.kwargs["content_sid"], "HX-test-template")
        self.assertEqual(
            messages.kwargs["content_variables"],
            '{"1":"Giovani Cárdenas","2":"Clínica Nova",'
            '"3":"Consulta general","4":"10/08/2026","5":"16:30"}',
        )

    def test_non_mexican_recipient_is_not_changed(self) -> None:
        messages = FakeMessages()
        client = SimpleNamespace(messages=messages)
        appointment = self.appointment()
        appointment["customer_phone"] = "+16285550100"

        send_appointment_confirmation(
            appointment,
            settings=self.settings(),
            client_factory=lambda _sid, _token: client,
        )

        self.assertEqual(messages.kwargs["to"], "whatsapp:+16285550100")

    def test_missing_credentials_disables_delivery(self) -> None:
        result = send_appointment_confirmation(
            self.appointment(),
            settings=self.settings(twilio_auth_token=""),
        )
        self.assertEqual(result, {"status": "not_configured"})

    def test_twilio_failure_does_not_raise(self) -> None:
        messages = FakeMessages(error=RuntimeError("temporary Twilio failure"))
        client = SimpleNamespace(messages=messages)

        result = send_appointment_confirmation(
            self.appointment(),
            settings=self.settings(),
            client_factory=lambda _sid, _token: client,
        )

        self.assertEqual(result, {"status": "failed"})


if __name__ == "__main__":
    unittest.main()
