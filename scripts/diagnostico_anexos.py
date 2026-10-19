"""Explora metadatos públicos de anexos sin seguir sus enlaces ni descargar archivos."""
import argparse
import re
import unicodedata
from urllib.parse import parse_qs, urlsplit

import requests
from bs4 import BeautifulSoup

HOSTS = {"www.mercadopublico.cl", "mercadopublico.cl"}
PATH = "/Procurement/Modules/Attachment/ViewAttachment.aspx"
MAX_HTML_BYTES = 4 * 1024 * 1024


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).casefold().split())


def clean_text(tag):
    return " ".join(tag.get_text(" ", strip=True).split())


def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.path.lower() != PATH.lower():
        raise ValueError("Se requiere una URL HTTPS de ViewAttachment.aspx obtenida del botón Ver adjuntos (no ViewAttachmentLC.aspx).")
    if not parse_qs(parsed.query).get("enc"):
        raise ValueError("La URL debe incluir el parámetro enc de la ficha de anexos.")
    return url


def inspect_actions(cell):
    actions = []
    for tag in cell.find_all(True):
        for attribute in ("href", "onclick", "formaction"):
            value = tag.get(attribute)
            if value:
                actions.append(f"{tag.name}.{attribute}={str(value)[:180]}")
    return actions


def parse_attachments(html):
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row_index, row in enumerate(rows):
            cells = row.find_all(["th", "td"], recursive=False)
            headers = [normalize(clean_text(cell)) for cell in cells]
            positions = {
                name: headers.index(name)
                for name in ("anexo", "tipo", "descripcion", "tamano", "fecha de adjunto", "acciones")
                if name in headers
            }
            if len(positions) < 5 or "anexo" not in positions:
                continue
            results = []
            for data_row in rows[row_index + 1:]:
                values = data_row.find_all(["td", "th"], recursive=False)
                if len(values) <= max(positions.values()):
                    continue
                name = clean_text(values[positions["anexo"]])
                if not name or normalize(name) == "anexo":
                    continue

                def cell_value(field):
                    return clean_text(values[positions[field]]) if field in positions else ""

                results.append({
                    "nombre": name,
                    "tipo": cell_value("tipo"),
                    "descripcion": cell_value("descripcion"),
                    "tamano": cell_value("tamano"),
                    "fecha": cell_value("fecha de adjunto"),
                    "acciones": inspect_actions(values[positions["acciones"]]) if "acciones" in positions else [],
                })
            return results
    return None


def fetch_html(url):
    with requests.get(
        validate_url(url),
        headers={"Accept": "text/html,application/xhtml+xml"},
        timeout=(10, 25),
        allow_redirects=False,
        stream=True,
    ) as response:
        print(f"HTTP: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'sin cabecera')}")
        if response.status_code in (301, 302, 303, 307, 308):
            destination = urlsplit(response.headers.get("Location", "")).path or "(sin ruta)"
            print(f"Redirección detectada hacia: {destination}")
            raise RuntimeError("El servidor solicitó redirigir; se detiene la prueba sin seguirla.")
        if response.status_code != 200:
            raise RuntimeError(f"El visor devolvió HTTP {response.status_code}; se detiene la prueba.")
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise RuntimeError("La respuesta no es HTML; no se descargará contenido binario.")
        chunks, size = [], 0
        for chunk in response.iter_content(chunk_size=32768):
            size += len(chunk)
            if size > MAX_HTML_BYTES:
                raise RuntimeError("HTML demasiado grande; se detuvo la lectura.")
            chunks.append(chunk)
        response.encoding = response.encoding or "utf-8"
        return b"".join(chunks).decode(response.encoding, errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Inspecciona el HTML público de anexos sin descargar archivos.")
    parser.add_argument("--url", help="URL original ViewAttachment.aspx?enc=... del botón Ver adjuntos")
    args = parser.parse_args()
    url = args.url or input("Pega la URL original ViewAttachment.aspx del botón (con enc): ").strip()
    try:
        html = fetch_html(url)
        items = parse_attachments(html)
        if items is None:
            print("No se encontró una tabla de anexos reconocible en el HTML.")
            if "captcha" in normalize(html):
                print("La página contiene referencias a CAPTCHA, sin determinar si limita este listado.")
            return 1
        print(f"Anexos encontrados: {len(items)}")
        for index, item in enumerate(items, 1):
            print(f"\n[{index}] {item['nombre']}")
            print(f"  Tipo: {item['tipo']}")
            print(f"  Descripción: {item['descripcion'] or '(sin descripción)'}")
            print(f"  Tamaño: {item['tamano']} | Fecha: {item['fecha']}")
            print(f"  Atributos de acción: {item['acciones'] or '(sin href/onclick/formaction visibles)'}")
        print("\nNo se visitó ningún enlace individual ni se descargaron anexos.")
        return 0
    except requests.RequestException:
        print("Diagnóstico fallido: error de conexión HTTP. No se muestran URLs ni parámetros de la petición.")
        return 1
    except (ValueError, RuntimeError) as exc:
        print(f"Diagnóstico fallido: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
