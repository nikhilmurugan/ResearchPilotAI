from io import BytesIO
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from reportlab.pdfgen import canvas

import app as app_module


class _PageContractParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.tabs = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if "data-tab" in attributes:
            self.tabs.append(attributes["data-tab"])


class ExistingContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_upload_folder = app_module.app.config["UPLOAD_FOLDER"]
        self.original_testing = app_module.app.config.get("TESTING", False)
        app_module.app.config.update(
            UPLOAD_FOLDER=self.temporary_directory.name,
            TESTING=True,
        )
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.app.config.update(
            UPLOAD_FOLDER=self.original_upload_folder,
            TESTING=self.original_testing,
        )
        self.temporary_directory.cleanup()

    def test_existing_routes_remain_registered(self):
        routes = {rule.rule for rule in app_module.app.url_map.iter_rules()}
        expected = {
            "/", "/status", "/chat", "/chat/stream", "/upload-pdf",
            "/analyze-pdf", "/agent", "/agents", "/generate-report",
            "/generate-ppt", "/download/report/<path:filename>",
            "/download/presentation/<path:filename>", "/history", "/stats",
            "/generate-docx", "/download/docx/<path:filename>",
            "/generate-citations", "/research-enhancements",
        }
        self.assertTrue(expected.issubset(routes))

    def test_navigation_and_javascript_dom_ids_remain_connected(self):
        template = Path("templates/index.html").read_text(encoding="utf-8")
        script = Path("static/script.js").read_text(encoding="utf-8")
        parser = _PageContractParser()
        parser.feed(template)

        self.assertEqual(len(parser.ids), len(set(parser.ids)), "HTML IDs must be unique")
        ids = set(parser.ids)
        self.assertTrue({f"tab-{tab}" for tab in parser.tabs}.issubset(ids))
        selectors = set(re.findall(r"(?:\$|document\.querySelector)\(\s*['\"]#([\w-]+)['\"]", script))
        runtime_ids = set(re.findall(r"\.id\s*=\s*['\"]([\w-]+)['\"]", script))
        self.assertTrue(
            selectors.issubset(ids | runtime_ids),
            f"Missing UI IDs: {sorted(selectors - ids - runtime_ids)}",
        )

    def test_chat_and_streaming_contracts_are_preserved(self):
        with patch("app.ask_ollama", return_value="A concise answer."), \
                patch("app.save_chat"), patch("app.update_stat"):
            response = self.client.post("/chat", json={"message": "Question"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["response"], "A concise answer.")

        with patch("app.stream_ollama", return_value=iter(["First", " second"])), \
                patch("app.save_chat"), patch("app.update_stat"):
            stream = self.client.post("/chat/stream", json={"message": "Question"})
            events = stream.get_data(as_text=True)

        self.assertEqual(stream.status_code, 200)
        self.assertIn('"token": "First"', events)
        self.assertIn('"done": true', events)

    def test_legacy_pdf_upload_still_extracts_text_and_rejects_bad_signature(self):
        pdf = BytesIO()
        document = canvas.Canvas(pdf)
        document.drawString(72, 720, "Legacy upload contract test text.")
        document.save()
        pdf.seek(0)

        with patch("app.update_stat"):
            response = self.client.post(
                "/upload-pdf",
                data={"file": (pdf, "contract-test.pdf", "application/pdf")},
                content_type="multipart/form-data",
            )
            invalid = self.client.post(
                "/upload-pdf",
                data={"file": (BytesIO(b"not a PDF"), "invalid.pdf", "application/pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Legacy upload contract test text.", response.get_json()["content"])
        self.assertIn("stored_as", response.get_json())
        self.assertEqual(invalid.status_code, 400)


if __name__ == "__main__":
    unittest.main()