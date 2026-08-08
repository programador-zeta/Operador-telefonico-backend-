import json
import secrets
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.dashboard import render_agenda
from app.database import init_db, insert, list_rows, log_tool_event
from app.schemas import (
    AppointmentCreate,
    KnowledgeCreate,
    MetricCreate,
    NoteCreate,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=get_settings().app_name, version="0.1.0", lifespan=lifespan)
dashboard_security = HTTPBasic(auto_error=False)


def require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def require_dashboard_login(
    credentials: HTTPBasicCredentials | None = Depends(dashboard_security),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.dashboard_password:
        raise HTTPException(status_code=503, detail="Dashboard password is not configured")
    valid = credentials is not None and secrets.compare_digest(
        credentials.username.encode(), settings.dashboard_user.encode()
    ) and secrets.compare_digest(
        credentials.password.encode(), settings.dashboard_password.encode()
    )
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": 'Basic realm="Agenda"'},
        )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": get_settings().app_name, "status": "online"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/agenda",
    response_class=HTMLResponse,
    dependencies=[Depends(require_dashboard_login)],
)
def agenda() -> HTMLResponse:
    return HTMLResponse(render_agenda(list_rows("appointments")))


@app.get("/api/knowledge", dependencies=[Depends(require_api_key)])
def get_knowledge() -> list[dict]:
    return list_rows("knowledge")


@app.post("/api/knowledge", dependencies=[Depends(require_api_key)])
def create_knowledge(item: KnowledgeCreate) -> dict:
    return insert("knowledge", item.model_dump())


@app.get("/api/appointments", dependencies=[Depends(require_api_key)])
def get_appointments() -> list[dict]:
    return list_rows("appointments")


@app.post("/api/appointments", dependencies=[Depends(require_api_key)])
def create_appointment(item: AppointmentCreate) -> dict:
    data = item.model_dump()
    data["starts_at"] = item.starts_at.isoformat()
    return insert("appointments", data)


@app.get("/api/notes", dependencies=[Depends(require_api_key)])
def get_notes() -> list[dict]:
    return list_rows("notes")


@app.post("/api/notes", dependencies=[Depends(require_api_key)])
def create_note(item: NoteCreate) -> dict:
    return insert("notes", item.model_dump())


@app.get("/api/metrics", dependencies=[Depends(require_api_key)])
def get_metrics() -> list[dict]:
    rows = list_rows("metrics")
    for row in rows:
        row["metadata"] = json.loads(row["metadata"])
    return rows


@app.post("/api/metrics", dependencies=[Depends(require_api_key)])
def create_metric(item: MetricCreate) -> dict:
    row = insert("metrics", item.model_dump())
    row["metadata"] = json.loads(row["metadata"])
    return row


def run_tool(name: str, arguments: dict[str, Any]) -> str:
    canonical_name = {
        # Compatibility with an accidental Vapi function rename during MVP setup.
        "customer_phone": "create_appointment",
        "custumer_phone": "create_appointment",
    }.get(name, name)
    handlers = {
        "create_appointment": lambda args: create_appointment(AppointmentCreate(**args)),
        "save_note": lambda args: create_note(NoteCreate(**args)),
        "record_metric": lambda args: create_metric(MetricCreate(**args)),
        "get_knowledge": lambda _: get_knowledge(),
    }
    handler = handlers.get(canonical_name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")
    result = handler(arguments)
    if canonical_name == "create_appointment":
        return (
            "Cita agendada correctamente. "
            f"Folio {result['id']}, cliente {result['customer_name']}, "
            f"servicio {result['service']}, fecha y hora {result['starts_at']}."
        )
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def parse_arguments(call: dict[str, Any]) -> dict[str, Any]:
    """Support the payload variants documented and emitted by Vapi providers."""
    arguments = call.get("arguments")
    if arguments is None:
        arguments = call.get("parameters")
    if arguments is None:
        function = call.get("function", {})
        arguments = function.get("arguments", function.get("parameters", {}))
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object")
    return arguments


def extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls = message.get("toolCallList") or message.get("toolCalls") or []
    if calls:
        return calls

    extracted = []
    for item in message.get("toolWithToolCallList", []):
        call = item.get("toolCall", {})
        function = call.get("function", {})
        extracted.append(
            {
                "id": call.get("id", ""),
                "name": call.get("name") or function.get("name") or item.get("name", ""),
                "arguments": (
                    call.get("arguments")
                    or call.get("parameters")
                    or function.get("arguments")
                    or function.get("parameters")
                    or {}
                ),
            }
        )
    return extracted


def friendly_tool_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        errors = exc.errors(include_url=False)
        fields = {str(error.get("loc", [""])[-1]) for error in errors}
        if fields.intersection({"customer_phone", "custumer_phone", "phone_number", "phone"}):
            return (
                "El número telefónico no es válido. Pide al cliente que repita "
                "los 10 dígitos de su número y vuelve a intentar agendar."
            )
        missing_names = {
            "customer_name": "nombre",
            "service": "servicio",
            "starts_at": "fecha y hora",
        }
        missing_fields = {
            str(error.get("loc", [""])[-1])
            for error in errors
            if error.get("type") == "missing"
        }
        missing = [
            label for field, label in missing_names.items() if field in missing_fields
        ]
        if missing:
            return "Faltan estos datos para agendar: " + ", ".join(missing) + "."
        if "starts_at" in fields:
            return "La fecha y hora ya pasaron. Pide al cliente un horario futuro y vuelve a intentar."
        return "Los datos de la cita no tienen el formato esperado. Confírmalos e inténtalo otra vez."
    if isinstance(exc, json.JSONDecodeError):
        return "Los datos recibidos no forman un JSON válido. Intenta enviar la cita otra vez."
    return f"No se pudo agendar la cita: {exc}"


@app.post("/vapi/tools", dependencies=[Depends(require_api_key)])
def vapi_tool(payload: dict[str, Any] = Body(...)) -> dict:
    """Accept Vapi's current tool-calls envelope and return matched results."""
    message = payload.get("message", {})
    tool_calls = extract_tool_calls(message)

    # Retain a small direct-call format for local testing.
    if not tool_calls and "name" in payload:
        response = {"result": run_tool(payload["name"], payload.get("arguments", {}))}
        return response

    results = []
    for call in tool_calls:
        tool_call_id = call.get("id", "")
        function = call.get("function", {})
        name = call.get("name") or function.get("name", "")
        arguments: dict[str, Any] = {}
        try:
            arguments = parse_arguments(call)
            tool_result = run_tool(name, arguments)
            results.append(
                {
                    "name": name,
                    "toolCallId": tool_call_id,
                    "result": tool_result,
                }
            )
            log_tool_event(tool_call_id, name, arguments, tool_result)
        except Exception as exc:
            error_message = friendly_tool_error(exc)
            results.append(
                {
                    "toolCallId": tool_call_id,
                    "error": error_message,
                }
            )
            log_tool_event(tool_call_id, name, arguments, error_message)
    response = {"results": results}
    return response
