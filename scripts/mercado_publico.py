"""Extracción descriptiva de licitaciones desde la API oficial de ChileCompra."""
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

API_URL = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
TIMEZONE = ZoneInfo("America/Santiago")


def normalize_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold()


def match_topics(text, keywords):
    normalized = normalize_text(text)
    return [
        category
        for category, terms in keywords.items()
        if any(re.search(r"(?<!\w)" + re.escape(normalize_text(term)) + r"(?!\w)", normalized) for term in terms)
    ]


def load_keywords(path="config/keywords.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(terms, list) for terms in data.values()):
        raise ValueError("El archivo de palabras clave requiere categorías con listas.")
    return data


def request_json(session, ticket, params):
    """No incluir ticket ni URL completa en mensajes de error."""
    for attempt in range(3):
        try:
            response = session.get(API_URL, params={**params, "ticket": ticket}, timeout=35)
        except requests.RequestException:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError("No se pudo conectar con Mercado Público.") from None
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(2 ** attempt)
            continue
        if not response.ok:
            raise RuntimeError(f"Mercado Público respondió HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError("Mercado Público respondió JSON inválido.") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("Listado"), list):
            raise RuntimeError("Formato de API inesperado: falta 'Listado'.")
        return payload
    raise RuntimeError("No fue posible completar la consulta.")


def text(value):
    return "" if value is None else str(value).strip()


def normalize_item(item, captured_at, keywords):
    if not isinstance(item, dict):
        return None
    code = text(item.get("CodigoExterno"))
    title = text(item.get("Nombre"))
    description = text(item.get("Descripcion"))
    topics = match_topics(f"{title} {description}", keywords)
    if not code or not topics:
        return None
    buyer = item.get("Comprador") if isinstance(item.get("Comprador"), dict) else {}
    dates = item.get("Fechas") if isinstance(item.get("Fechas"), dict) else {}
    return {
        "id": f"licitacion:{code}",
        "fuente": "licitacion",
        "codigo": code,
        "titulo": title,
        "descripcion": description,
        "organismo": text(buyer.get("NombreOrganismo") or item.get("NombreOrganismo")),
        "estado": text(item.get("Estado") or item.get("CodigoEstado")),
        "fecha_publicacion": text(dates.get("FechaPublicacion") or item.get("FechaPublicacion")),
        "fecha_cierre": text(dates.get("FechaCierre") or item.get("FechaCierre")),
        "monto_estimado": text(item.get("MontoEstimado")),
        "moneda": text(item.get("Moneda")),
        "categorias_detectadas": topics,
        "enlace": text(item.get("UrlFicha") or item.get("URL")),
        "ultima_consulta": captured_at,
    }


def collect_licitaciones(ticket, days, max_details, keywords, session=None, now=None):
    if not ticket:
        raise ValueError("Falta MERCADO_PUBLICO_TICKET.")
    if days < 1 or max_details < 1:
        raise ValueError("days y max_details deben ser mayores que cero.")
    session = session or requests.Session()
    today = (now or datetime.now(TIMEZONE)).date()
    captured_at = datetime.now(TIMEZONE).isoformat(timespec="seconds")
    records = {}
    inspected = 0
    for offset in range(days):
        date_value = today - timedelta(days=offset)
        payload = request_json(session, ticket, {"fecha": date_value.strftime("%d%m%Y")})
        for summary in payload["Listado"]:
            if inspected >= max_details:
                break
            if not isinstance(summary, dict):
                continue
            code = text(summary.get("CodigoExterno"))
            if not code or f"licitacion:{code}" in records:
                continue
            if not match_topics(f"{summary.get('Nombre', '')} {summary.get('Descripcion', '')}", keywords):
                continue
            inspected += 1
            detail = request_json(session, ticket, {"codigo": code})
            if not detail["Listado"]:
                continue
            item = normalize_item(detail["Listado"][0], captured_at, keywords)
            if item:
                records[item["id"]] = item
        if inspected >= max_details:
            break
    return list(records.values())
