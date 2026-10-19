import unittest

from scripts.google_sheets import HEADERS, sheet_row
from scripts.mercado_publico import match_topics, normalize_item
from scripts.run import merge_records


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.categories = {"migracion": ["migración de datos"], "modernizacion": ["modernización"]}

    def test_accents(self):
        self.assertEqual(match_topics("MIGRACION DE DATOS", self.categories), ["migracion"])

    def test_irrelevant(self):
        self.assertIsNone(normalize_item({"CodigoExterno": "1", "Nombre": "Compra de sillas"}, "hoy", self.categories))

    def test_normalized_record(self):
        result = normalize_item({
            "CodigoExterno": "123-4-LE26", "Nombre": "Modernización del sistema",
            "Comprador": {"NombreOrganismo": "Municipalidad"},
        }, "2026-10-19", self.categories)
        self.assertEqual(result["id"], "licitacion:123-4-LE26")
        self.assertEqual(result["organismo"], "Municipalidad")
        self.assertEqual(len(sheet_row(result)), 15)

    def test_history_merge(self):
        old = [{"id": "licitacion:1", "ultima_consulta": "2026-10-01", "primera_consulta": "2026-10-01"}]
        new = [{"id": "licitacion:1", "ultima_consulta": "2026-10-19"}]
        data = merge_records(old, new)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["primera_consulta"], "2026-10-01")

    def test_manual_columns(self):
        self.assertEqual(len(HEADERS), 21)
        self.assertEqual(HEADERS[15], "Qué solicita (análisis)")


if __name__ == "__main__":
    unittest.main()
