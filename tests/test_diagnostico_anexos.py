import unittest

from scripts.diagnostico_anexos import parse_attachments, validate_url


class AttachmentDiagnosticsTests(unittest.TestCase):
    def test_parse_table(self):
        html = '''<html><table><tr><th>Sel.</th><th>Anexo</th><th>Tipo</th>
        <th>Descripción</th><th>Tamaño</th><th>Fecha de Adjunto</th><th>Acciones</th></tr>
        <tr><td><input type="checkbox"></td><td>31.1. ACTIVIDADES DE DESARROLLO.pdf</td>
        <td>Otros Anexos</td><td>Actividades de desarrollo</td><td>451 KB</td>
        <td>24-06-2026 11:24:49</td><td><a href="javascript:abrir(123)">Ver</a></td></tr></table></html>'''
        rows = parse_attachments(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tamano"], "451 KB")
        self.assertIn("a.href=javascript:abrir(123)", rows[0]["acciones"])

    def test_no_table(self):
        self.assertIsNone(parse_attachments("<html><body>Sin anexos</body></html>"))

    def test_validate_url(self):
        self.assertTrue(validate_url("https://www.mercadopublico.cl/Procurement/Modules/Attachment/ViewAttachmentLC.aspx?enc=ABC"))
        with self.assertRaises(ValueError):
            validate_url("https://example.org/Procurement/Modules/Attachment/ViewAttachmentLC.aspx?enc=ABC")


if __name__ == "__main__":
    unittest.main()
