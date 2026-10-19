"""Recolecta nuevas licitaciones y conserva el histórico sin duplicados."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.mercado_publico import collect_licitaciones, load_keywords


def merge_records(previous, fresh):
    records = {row["id"]: row for row in previous if isinstance(row, dict) and row.get("id")}
    for row in fresh:
        old = records.get(row["id"], {})
        merged = {**old, **row}
        merged["primera_consulta"] = old.get("primera_consulta", row["ultima_consulta"])
        records[row["id"]] = merged
    return sorted(records.values(), key=lambda row: row["id"])


def main():
    parser = argparse.ArgumentParser(description="Extrae licitaciones de Mercado Público.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--max-details", type=int, default=70)
    parser.add_argument("--output", default="data/licitaciones.json")
    args = parser.parse_args()
    path = Path(args.output)
    previous = []
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8")).get("licitaciones", [])

    ticket = os.environ.get("MERCADO_PUBLICO_TICKET", "").strip()
    fresh = collect_licitaciones(ticket, args.days, args.max_details, load_keywords())
    records = merge_records(previous, fresh)
    payload = {
        "version": 1,
        "fuentes_implementadas": ["licitacion"],
        "generado_en": datetime.now(ZoneInfo("America/Santiago")).isoformat(timespec="seconds"),
        "encontradas_en_ejecucion": len(fresh),
        "total_historico": len(records),
        "licitaciones": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(f"Encontradas: {len(fresh)} | Histórico: {len(records)}")


if __name__ == "__main__":
    main()
