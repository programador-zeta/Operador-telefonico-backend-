import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, BaseModel, Field, field_validator


class KnowledgeCreate(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=2000)


class AppointmentCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    customer_phone: str = Field(
        min_length=8,
        max_length=16,
        validation_alias=AliasChoices(
            "customer_phone",
            "custumer_phone",  # Backward compatibility with the current Vapi schema typo.
            "phone_number",
            "phone",
        ),
    )
    service: str = Field(min_length=1, max_length=120)
    starts_at: datetime

    @field_validator("customer_name", "service", mode="before")
    @classmethod
    def clean_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())

    @field_validator("customer_phone", mode="before")
    @classmethod
    def normalize_mexican_phone(cls, value: Any) -> str:
        if value is None or isinstance(value, bool):
            raise ValueError("el número telefónico es obligatorio")
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError("el número telefónico contiene decimales")
            value = int(value)

        raw = str(value).strip()
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("00"):
            digits = digits[2:]

        # Normalize Mexico's obsolete mobile prefix +52 1 to current E.164.
        if len(digits) == 13 and digits.startswith("521"):
            digits = "52" + digits[3:]

        # For this Mexico-first MVP, a local 10-digit number gets country code +52.
        if len(digits) == 10:
            digits = "52" + digits

        if not 8 <= len(digits) <= 15:
            raise ValueError(
                "usa entre 8 y 15 dígitos; en México proporciona los 10 dígitos"
            )
        return f"+{digits}"

    @field_validator("starts_at")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        mexico_tz = ZoneInfo("America/Mexico_City")
        if value.tzinfo is None:
            value = value.replace(tzinfo=mexico_tz)
        else:
            value = value.astimezone(mexico_tz)

        # Voice models occasionally infer an old year when the caller omits it.
        # Correct only to the current year when that date is still in the future.
        now = datetime.now(mexico_tz)
        if value < now:
            candidate = value.replace(year=now.year)
            if candidate >= now:
                value = candidate
            else:
                raise ValueError("la fecha y hora solicitadas ya pasaron")
        return value


class NoteCreate(BaseModel):
    customer_phone: str | None = Field(default=None, max_length=30)
    content: str = Field(min_length=1, max_length=2000)


class MetricCreate(BaseModel):
    event: str = Field(min_length=1, max_length=100)
    value: float = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
