import unittest
from unittest.mock import Mock, patch

from scripts.diagnostico_api import inspect_paths, request_licitacion, summarize


class APIDiagnosticsTests(unittest.TestCase):
    def test_parses_detail_and_does_not_follow_redirects(self):
        fake_response = Mock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "application/json; charset=utf-8"}
        fake_response.json.return_value = {
            "Cantidad": 1,
            "Listado": [{"CodigoExterno": "1111089-6-LP26", "Nombre": "Modernización"}],
        }
        session = Mock()
        session.get.return_value = fake_response
        with patch("builtins.print"):
            result = request_licitacion("1111089-6-LP26", "ticket-de-prueba", session)
        self.assertEqual(result["Cantidad"], 1)
        kwargs = session.get.call_args.kwargs
        self.assertEqual(kwargs["params"]["codigo"], "1111089-6-LP26")
        self.assertFalse(kwargs["allow_redirects"])

    def test_rejects_html_even_with_http_200(self):
        response = Mock(status_code=200, headers={"Content-Type": "text/html"})
        session = Mock()
        session.get.return_value = response
        with patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "no respondió con JSON"):
                request_licitacion("1111089-6-LP26", "ticket-de-prueba", session)

    def test_rejects_redirect(self):
        response = Mock(status_code=302, headers={"Content-Type": "text/html", "Location": "/403.html"})
        session = Mock()
        session.get.return_value = response
        with patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "redirección"):
                request_licitacion("1111089-6-LP26", "ticket-de-prueba", session)

    def test_nested_paths(self):
        result = inspect_paths({"Listado": [{"Items": {"Listado": [{"NombreProducto": "Software"}]}}]})
        self.assertIn("Listado[].Items.Listado[].NombreProducto", result)

    def test_summary_supports_missing_optional_fields(self):
        with patch("builtins.print"):
            summarize({"Cantidad": 1, "Listado": [{"CodigoExterno": "1111089-6-LP26"}]})


if __name__ == "__main__":
    unittest.main()
