# Operador Telefónico MVP

Backend mínimo en FastAPI para conectar herramientas/webhooks de Vapi.

## Inicio local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/health`. Debe responder `{"status":"ok"}`.

La documentación interactiva está en `http://127.0.0.1:8000/docs`.

## Despliegue en Render

El archivo `render.yaml` crea el servicio web y una base Postgres persistente.
Render ejecuta:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Autenticación

Los endpoints `/api/*` y `/vapi/tools` aceptan el encabezado `x-api-key` con el valor configurado en `.env`.

La agenda visual está en `/agenda` y solicita usuario y contraseña. Configura
`DASHBOARD_USER` y `DASHBOARD_PASSWORD`; si no defines una contraseña específica,
usa el valor de `API_KEY`.

## Prueba de tool para Vapi

```bash
curl -X POST http://127.0.0.1:8000/vapi/tools \
  -H 'content-type: application/json' \
  -H 'x-api-key: cambia-esta-clave' \
  -d '{"name":"save_note","arguments":{"customer_phone":"5551234567","content":"Solicita llamada mañana"}}'
```
