import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module


class DocumentQAApiTests(unittest.TestCase):
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

    def test_rejects_missing_document_and_invalid_path(self):
        missing = self.client.post("/document-ask", json={"question": "What is the result?"})
        traversal = self.client.post(
            "/document-ask",
            json={"stored_as": "..\\private.pdf", "question": "What is the result?"},
        )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(traversal.status_code, 400)

    def test_home_renders_configured_default_model(self):
        with patch("app.is_ollama_available", return_value=False):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        expected_model = f'value="{app_module.OLLAMA_MODEL}" checked'.encode()
        self.assertIn(expected_model, response.data)

    def test_returns_answer_with_page_sources(self):
        document_id = f"{'a' * 32}_paper.pdf"
        pdf_path = Path(self.temporary_directory.name) / document_id
        pdf_path.write_bytes(b"%PDF test fixture")
        evidence = [{
            "filename": "paper.pdf",
            "page": 3,
            "section": "Results",
            "chunk_id": 1,
            "text": "The treatment improved the measured outcome.",
        }]

        with patch(
            "app.answer_document_question",
            return_value=("The treatment improved the outcome [1].", evidence),
        ) as answer_question:
            response = self.client.post(
                "/document-ask",
                json={"stored_as": document_id, "question": "What changed?"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["answer"], "The treatment improved the outcome [1].")
        self.assertEqual(payload["sources"][0]["page"], 3)
        self.assertEqual(payload["sources"][0]["excerpt"], evidence[0]["text"])
        self.assertEqual(answer_question.call_args.args[1:], (document_id, "paper.pdf", "What changed?"))


if __name__ == "__main__":
    unittest.main()