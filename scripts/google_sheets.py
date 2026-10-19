"""Actualiza solo columnas automáticas y respeta notas/estudios manuales en Google Sheets."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

TAB = "Licitaciones"
AUTO_COLUMNS = 15
HEADERS = [
    "ID", "Fuente", "Código", "Título", "Descripción", "Organismo", "Estado",
    "Fecha publicación", "Fecha cierre", "Monto estimado", "Moneda",
    "Categorías detectadas", "Temas", "Enlace", "Última consulta",
    "Qué solicita (análisis)", "Situación actual (análisis)",
    "Requisitos (análisis)", "Qué se puede reutilizar (análisis)",
    "Mejoras posibles (análisis)", "Observaciones manuales",
]


def sheet_row(record):
    topics = ", ".join(record.get("categorias_detectadas") or [])
    return [
        record.get("id", ""), record.get("fuente", ""), record.get("codigo", ""),
        record.get("titulo", ""), record.get("descripcion", ""),
        record.get("organismo", ""), record.get("estado", ""),
        record.get("fecha_publicacion", ""), record.get("fecha_cierre", ""),
        record.get("monto_estimado", ""), record.get("moneda", ""),
        topics, topics, record.get("enlace", ""), record.get("ultima_consulta", ""),
    ]


def send(session, method, url, **kwargs):
    try:
        response = session.request(method, url, timeout=45, **kwargs)
    except Exception:
        raise RuntimeError("No fue posible conectarse a Google Sheets.") from None
    if not response.ok:
        raise RuntimeError(f"Google Sheets API respondió HTTP {response.status_code}. Comprueba permisos e identificadores.")
    return response.json() if response.content else {}


def sync(payload, sheet_id, credentials_json):
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(credentials_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    session = AuthorizedSession(credentials)
    base = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(sheet_id, safe='')}/values"
    all_range = quote(f"'{TAB}'!A1:U", safe="")
    existing = send(session, "GET", f"{base}/{all_range}").get("values", [])
    if not existing:
        header_range = quote(f"'{TAB}'!A1:U1", safe="")
        send(session, "PUT", f"{base}/{header_range}?valueInputOption=RAW", json={"values": [HEADERS]})
        existing = [HEADERS]
    if existing[0] != HEADERS:
        raise RuntimeError("Encabezados distintos: se detuvo la sincronización para proteger datos manuales.")

    known = {row[0]: index + 1 for index, row in enumerate(existing) if index > 0 and row and row[0]}
    updates, additions = [], []
    for record in payload.get("licitaciones", []):
        values = [str(item) for item in sheet_row(record)]
        key = values[0]
        if not key:
            continue
        if key in known:
            row_index = known[key]
            previous = (existing[row_index - 1] + [""] * AUTO_COLUMNS)[:AUTO_COLUMNS]
            if previous != values:
                updates.append({"range": f"'{TAB}'!A{row_index}:O{row_index}", "values": [values]})
        else:
            additions.append(values)

    for offset in range(0, len(updates), 100):
        send(session, "POST", f"{base}:batchUpdate", json={
            "valueInputOption": "RAW", "data": updates[offset:offset + 100],
        })
    if additions:
        append_range = quote(f"'{TAB}'!A:O", safe="")
        send(session, "POST", f"{base}/{append_range}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
             json={"values": additions})
    print(f"Google Sheets: {len(updates)} actualizadas; {len(additions)} nuevas.")


def main():
    parser = argparse.ArgumentParser(description="Sincroniza el histórico en Google Sheets.")
    parser.add_argument("--input", default="data/licitaciones.json")
    args = parser.parse_args()
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not sheet_id or not credentials_json:
        raise RuntimeError("Faltan secrets GOOGLE_SHEET_ID y/o GOOGLE_SERVICE_ACCOUNT_JSON.")
    sync(json.loads(Path(args.input).read_text(encoding="utf-8")), sheet_id, credentials_json)


if __name__ == "__main__":
    main()
