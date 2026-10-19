"""Diagnóstico de una licitación por la API oficial de ChileCompra, sin guardar archivos."""
import argparse
import getpass
import os
import re

import requests

API_URL = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
DEFAULT_CODE = "1111089-6-LP26"
CODE_PATTERN = re.compile(r"^[A-Za-z0-9-]{5,40}$")
DOCUMENT_TERMS = ("adjunt", "anexo", "archivo", "document", "url", "bases")


def read_field(data, *path):
    for part in path:
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def inspect_paths(data, prefix="", limit=250):
    """Enumera rutas del JSON sin mostrar valores ni información personal."""
    paths = []

    def walk(value, name):
        if len(paths) >= limit:
            return
        if isinstance(value, dict):
            for key, nested in value.items():
                if len(paths) >= limit:
                    break
                location = f"{name}.{key}" if name else key
                if isinstance(nested, (dict, list)):
                    paths.append(location)
                    walk(nested, location)
                else:
                    paths.append(location)
        elif isinstance(value, list):
            if value:
                walk(value[0], f"{name}[]")

    walk(data, prefix)
    return paths


def request_licitacion(code, ticket, session=None):
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError("Código de licitación inválido.")
    if not ticket:
        raise ValueError("Es necesario un ticket oficial de ChileCompra.")
    client = session if session is not None else requests.Session()
    try:
        response = client.get(
            API_URL,
            params={"codigo": code, "ticket": ticket},
            headers={"Accept": "application/json"},
            timeout=(10, 30),
            allow_redirects=False,
        )
    except requests.RequestException:
        raise RuntimeError("Falló la conexión HTTP. No se muestran la URL ni el ticket.") from None

    content_type = response.headers.get("Content-Type", "(sin Content-Type)")
    print(f"HTTP: {response.status_code}")
    print(f"Content-Type: {content_type}")

    if response.status_code in (301, 302, 303, 307, 308):
        raise RuntimeError("La API respondió con una redirección; se detuvo sin seguirla.")
    if response.status_code != 200:
        raise RuntimeError(f"La API devolvió HTTP {response.status_code}; revisa ticket y disponibilidad.")
    if "json" not in content_type.lower():
        raise RuntimeError("El servidor no respondió con JSON. No se procesó HTML.")

    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError("La API respondió un JSON inválido.") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Se esperaba un objeto JSON en la respuesta.")

    listado = payload.get("Listado")
    if not isinstance(listado, list):
        raise RuntimeError("La respuesta no contiene 'Listado' como lista.")

    return payload


def summarize(payload):
    listado = payload.get("Listado", [])
    print(f"Cantidad declarada: {payload.get('Cantidad', '(no informada)')}")
    print(f"Registros recibidos: {len(listado)}")
    if not listado:
        print("La API no devolvió registros para el código consultado.")
        return

    item = listado[0]
    if not isinstance(item, dict):
        print("El primer registro no es un objeto JSON.")
        return

    buyer = item.get("Comprador") if isinstance(item.get("Comprador"), dict) else {}
    dates = item.get("Fechas") if isinstance(item.get("Fechas"), dict) else {}
    lines = [
        ("Código", item.get("CodigoExterno")),
        ("Nombre", item.get("Nombre")),
        ("Descripción", item.get("Descripcion")),
        ("Estado", item.get("Estado") or item.get("CodigoEstado")),
        ("Organismo", buyer.get("NombreOrganismo")),
        ("Región", buyer.get("RegionUnidad")),
        ("Publicación", dates.get("FechaPublicacion")),
        ("Cierre", dates.get("FechaCierre") or item.get("FechaCierre")),
        ("Monto estimado", item.get("MontoEstimado")),
        ("Moneda", item.get("Moneda")),
        ("Duración contrato", item.get("TiempoDuracionContrato")),
        ("Unidad de duración", item.get("TipoDuracionContrato") or item.get("UnidadTiempoDuracionContrato")),
        ("Permite subcontratación", item.get("SubContratacion")),
    ]
    print("\n--- Datos descriptivos ---")
    for label, value in lines:
        if isinstance(value, str):
            value = " ".join(value.split())[:700]
        print(f"{label}: {value if value is not None and value != '' else '(no informado)'}")

    items = item.get("Items")
    items_list = items.get("Listado") if isinstance(items, dict) else None
    if isinstance(items_list, list):
        print(f"\nÍtems declarados: {items.get('Cantidad', '(sin cantidad)')}")
        print(f"Ítems en JSON: {len(items_list)}")
        for product in items_list[:3]:
            if not isinstance(product, dict):
                continue
            name = product.get("NombreProducto", "(sin nombre)")
            description = product.get("Descripcion", "(sin descripción)")
            print(f" - {str(name)[:180]}: {str(description)[:220]}")

    award = item.get("Adjudicacion")
    if isinstance(award, dict):
        print("\n--- Adjudicación ---")
        print("Fecha:", award.get("Fecha", "(no informada)"))
        print("Cantidad de oferentes adjudicados:", award.get("NumeroOferentes", "(no informada)"))
        print("Tiene UrlActa:", bool(award.get("UrlActa")))

    paths = inspect_paths(payload)
    print(f"\n--- Estructura JSON (primeros {len(paths)} campos/rutas) ---")
    for path in paths:
        print(" -", path)

    candidates = [
        path for path in paths
        if any(term in path.lower() for term in DOCUMENT_TERMS)
    ]
    print("\n--- Posibles referencias a documentos (solo nombres de campos) ---")
    if candidates:
        for path in candidates:
            print(" -", path)
    else:
        print("No se detectaron campos con nombres asociados a documentos.")


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico de la API de licitaciones de ChileCompra.")
    parser.add_argument("--codigo", default=DEFAULT_CODE, help="Código de licitación")
    args = parser.parse_args()
    ticket = os.environ.get("MERCADO_PUBLICO_TICKET", "").strip()
    if not ticket:
        ticket = getpass.getpass("Ticket API de ChileCompra (oculto, no se guarda): ").strip()
    try:
        payload = request_licitacion(args.codigo, ticket)
        summarize(payload)
        print("\nFinalizado. No se guardaron archivos ni se consultaron anexos.")
    except (ValueError, RuntimeError) as error:
        print("Diagnóstico fallido:", error)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
