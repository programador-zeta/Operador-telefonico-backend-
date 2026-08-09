import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.database import init_db, list_rows
from app.main import vapi_tool


class VapiPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = get_settings()
        settings.database_path = Path(self.temp_dir.name) / "test.db"
        init_db()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def appointment(self) -> dict:
        future = datetime.now(ZoneInfo("America/Mexico_City")) + timedelta(days=2)
        return {
            "customer_name": "Juan Pérez",
            "customer_phone": "5512345678",
            "service": "Limpieza dental",
            "starts_at": future.replace(microsecond=0).isoformat(),
        }

    def test_current_vapi_arguments_format(self) -> None:
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-arguments",
                            "name": "create_appointment",
                            "arguments": self.appointment(),
                        }
                    ],
                }
            }
        )
        self.assertEqual(response["results"][0]["toolCallId"], "call-arguments")
        self.assertIn("Cita agendada correctamente", response["results"][0]["result"])
        self.assertEqual(len(list_rows("appointments")), 1)

    def test_parameters_format(self) -> None:
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-parameters",
                            "name": "create_appointment",
                            "parameters": self.appointment(),
                        }
                    ],
                }
            }
        )
        self.assertIn("result", response["results"][0])

    def test_openai_function_format(self) -> None:
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCalls": [
                        {
                            "id": "call-function",
                            "function": {
                                "name": "create_appointment",
                                "arguments": self.appointment(),
                            },
                        }
                    ],
                }
            }
        )
        self.assertIn("result", response["results"][0])

    def test_validation_error_is_returned_in_vapi_format(self) -> None:
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-invalid",
                            "name": "create_appointment",
                            "arguments": {"customer_name": "Juan"},
                        }
                    ],
                }
            }
        )
        self.assertEqual(response["results"][0]["toolCallId"], "call-invalid")
        self.assertIn("error", response["results"][0])

    def test_phone_with_spaces_and_dashes_is_normalized(self) -> None:
        appointment = self.appointment()
        appointment["customer_phone"] = "55 1234-5678"
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-formatted-phone",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        self.assertIn("result", response["results"][0])
        self.assertEqual(list_rows("appointments")[0]["customer_phone"], "+525512345678")

    def test_numeric_phone_is_normalized(self) -> None:
        appointment = self.appointment()
        appointment["customer_phone"] = 5512345678
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-numeric-phone",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        self.assertIn("result", response["results"][0])
        self.assertEqual(list_rows("appointments")[0]["customer_phone"], "+525512345678")

    def test_mexico_country_code_is_preserved(self) -> None:
        appointment = self.appointment()
        appointment["customer_phone"] = "+52 (55) 1234 5678"
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-country-code",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        self.assertIn("result", response["results"][0])
        self.assertEqual(list_rows("appointments")[0]["customer_phone"], "+525512345678")

    def test_invalid_phone_returns_actionable_error(self) -> None:
        appointment = self.appointment()
        appointment["customer_phone"] = "123"
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-bad-phone",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        self.assertNotIn("result", response["results"][0])
        self.assertIn("10 dígitos", response["results"][0]["error"])

    def test_naive_datetime_gets_mexico_timezone(self) -> None:
        appointment = self.appointment()
        future = datetime.now(ZoneInfo("America/Mexico_City")) + timedelta(days=2)
        appointment["starts_at"] = future.replace(tzinfo=None, microsecond=0).isoformat()
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-naive-time",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        self.assertIn("result", response["results"][0])
        self.assertRegex(list_rows("appointments")[0]["starts_at"], r"-0[56]:00$")

    def test_real_vapi_typo_is_accepted(self) -> None:
        appointment = self.appointment()
        appointment.pop("customer_phone")
        appointment["custumer_phone"] = "5512345678"
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-real-vapi-typo",
                            "type": "function",
                            "function": {
                                "name": "create_appointment",
                                "arguments": appointment,
                            },
                        }
                    ],
                }
            }
        )
        self.assertIn("result", response["results"][0])
        self.assertEqual(list_rows("appointments")[0]["customer_phone"], "+525512345678")

    def test_exact_accidentally_renamed_vapi_tool_is_accepted(self) -> None:
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-accidental-tool-name",
                            "type": "function",
                            "function": {
                                "name": "customer_phone",
                                "arguments": {
                                    "service": "dentista",
                                    "starts_at": self.appointment()["starts_at"],
                                    "customer_name": "Giovanni Cárdenas López",
                                    "custumer_phone": "5579328860",
                                },
                            },
                        }
                    ],
                }
            }
        )
        self.assertIn("Cita agendada correctamente", response["results"][0]["result"])
        saved = list_rows("appointments")[0]
        self.assertEqual(saved["customer_phone"], "+525579328860")

    def test_old_inferred_year_moves_to_future(self) -> None:
        appointment = self.appointment()
        future = datetime.now(ZoneInfo("America/Mexico_City")) + timedelta(days=1)
        appointment["starts_at"] = future.replace(year=2024).isoformat()
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-old-year",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        self.assertIn("result", response["results"][0])
        saved_year = int(list_rows("appointments")[0]["starts_at"][:4])
        self.assertGreaterEqual(saved_year, datetime.now().year)

    def test_past_time_is_rejected_instead_of_silently_moving_a_year(self) -> None:
        appointment = self.appointment()
        past = datetime.now(ZoneInfo("America/Mexico_City")) - timedelta(hours=1)
        appointment["starts_at"] = past.isoformat()
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-past-time",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        self.assertIn("error", response["results"][0])

    def test_availability_tool_reports_free_slot(self) -> None:
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-availability-free",
                            "name": "check_availability",
                            "arguments": {
                                "starts_at": self.appointment()["starts_at"],
                                "duration_minutes": 30,
                            },
                        }
                    ],
                }
            }
        )
        self.assertIn("está disponible", response["results"][0]["result"])

    def test_duplicate_appointment_is_rejected_with_alternatives(self) -> None:
        appointment = self.appointment()
        first = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-first-appointment",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        duplicate = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-duplicate-appointment",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )

        self.assertIn("Cita agendada correctamente", first["results"][0]["result"])
        self.assertIn("error", duplicate["results"][0])
        self.assertIn("ya está ocupado", duplicate["results"][0]["error"])
        self.assertIn("Opciones disponibles", duplicate["results"][0]["error"])
        self.assertEqual(len(list_rows("appointments")), 1)

    def test_overlapping_appointment_is_rejected(self) -> None:
        appointment = self.appointment()
        vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-original",
                            "name": "create_appointment",
                            "arguments": appointment,
                        }
                    ],
                }
            }
        )
        overlap = dict(appointment)
        overlap["starts_at"] = (
            datetime.fromisoformat(appointment["starts_at"]) + timedelta(minutes=15)
        ).isoformat()
        response = vapi_tool(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {
                            "id": "call-overlap",
                            "name": "create_appointment",
                            "arguments": overlap,
                        }
                    ],
                }
            }
        )
        self.assertIn("error", response["results"][0])
        self.assertEqual(len(list_rows("appointments")), 1)

    def test_whatsapp_failure_does_not_erase_saved_appointment(self) -> None:
        with patch(
            "app.main.send_appointment_confirmation",
            return_value={"status": "failed"},
        ):
            response = vapi_tool(
                {
                    "message": {
                        "type": "tool-calls",
                        "toolCallList": [
                            {
                                "id": "call-whatsapp-failure",
                                "name": "create_appointment",
                                "arguments": self.appointment(),
                            }
                        ],
                    }
                }
            )

        result = response["results"][0]["result"]
        self.assertIn("Cita agendada correctamente", result)
        self.assertIn("no se pudo enviar", result)
        self.assertEqual(len(list_rows("appointments")), 1)


if __name__ == "__main__":
    unittest.main()
