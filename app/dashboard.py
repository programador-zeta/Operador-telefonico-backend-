from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo


MEXICO_TZ = ZoneInfo("America/Mexico_City")


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MEXICO_TZ)
    return parsed.astimezone(MEXICO_TZ)


def render_agenda(appointments: list[dict]) -> str:
    now = datetime.now(MEXICO_TZ)
    ordered = sorted(
        appointments,
        key=lambda item: _parse_datetime(item["starts_at"]),
    )
    upcoming = [item for item in ordered if _parse_datetime(item["starts_at"]) >= now]
    today = [
        item
        for item in upcoming
        if _parse_datetime(item["starts_at"]).date() == now.date()
    ]

    cards = []
    for item in upcoming:
        starts_at = _parse_datetime(item["starts_at"])
        date_label = starts_at.strftime("%d/%m/%Y")
        time_label = starts_at.strftime("%H:%M")
        cards.append(
            f"""
            <article class="appointment">
              <div class="date"><strong>{date_label}</strong><span>{time_label}</span></div>
              <div class="details">
                <h2>{escape(str(item['customer_name']))}</h2>
                <p>{escape(str(item['service']))}</p>
                <a href="tel:{escape(str(item['customer_phone']))}">{escape(str(item['customer_phone']))}</a>
              </div>
              <div class="folio">Folio {int(item['id'])}</div>
            </article>
            """
        )

    empty_state = """
      <section class="empty">
        <h2>No hay próximas citas</h2>
        <p>Las citas registradas por el operador aparecerán aquí.</p>
      </section>
    """
    appointment_list = "".join(cards) if cards else empty_state

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>Agenda · Operador Telefónico</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #0b0d10; color: #f4f7f8; }}
    main {{ width: min(920px, calc(100% - 32px)); margin: 0 auto; padding: 40px 0 64px; }}
    header {{ display: flex; justify-content: space-between; gap: 20px; align-items: end; margin-bottom: 28px; }}
    h1 {{ margin: 0; font-size: clamp(30px, 6vw, 48px); letter-spacing: -0.04em; }}
    header p {{ color: #8d989e; margin: 8px 0 0; }}
    .live {{ color: #63e6be; font-size: 14px; white-space: nowrap; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 28px; }}
    .metric {{ background: #14181d; border: 1px solid #232a31; border-radius: 16px; padding: 18px; }}
    .metric strong {{ display: block; font-size: 30px; }}
    .metric span {{ color: #8d989e; font-size: 14px; }}
    .appointment {{ display: grid; grid-template-columns: 112px 1fr auto; align-items: center; gap: 20px; padding: 20px; margin-bottom: 12px; background: #14181d; border: 1px solid #232a31; border-radius: 18px; }}
    .date {{ display: flex; flex-direction: column; gap: 3px; color: #8d989e; }}
    .date strong {{ color: #f4f7f8; }}
    .details h2 {{ margin: 0 0 4px; font-size: 19px; }}
    .details p {{ margin: 0 0 7px; color: #aab4b9; }}
    .details a {{ color: #63e6be; text-decoration: none; }}
    .folio {{ color: #8d989e; font-size: 14px; }}
    .empty {{ text-align: center; color: #8d989e; background: #14181d; border: 1px dashed #34404a; border-radius: 18px; padding: 56px 20px; }}
    .empty h2 {{ color: #f4f7f8; margin: 0 0 8px; }}
    .empty p {{ margin: 0; }}
    footer {{ color: #667178; font-size: 13px; margin-top: 28px; }}
    @media (max-width: 620px) {{
      main {{ padding-top: 24px; }}
      header {{ align-items: start; flex-direction: column; }}
      .metrics {{ grid-template-columns: 1fr; }}
      .appointment {{ grid-template-columns: 92px 1fr; }}
      .folio {{ grid-column: 2; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>Agenda</h1><p>Operador Telefónico IA</p></div>
      <div class="live">● Actualización automática</div>
    </header>
    <section class="metrics">
      <div class="metric"><strong>{len(upcoming)}</strong><span>Próximas citas</span></div>
      <div class="metric"><strong>{len(today)}</strong><span>Citas de hoy</span></div>
      <div class="metric"><strong>{len(appointments)}</strong><span>Total registrado</span></div>
    </section>
    <section>{appointment_list}</section>
    <footer>La agenda se actualiza cada 30 segundos.</footer>
  </main>
</body>
</html>"""
