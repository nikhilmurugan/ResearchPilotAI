import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module


class GeneratorApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_directory = os.getcwd()
        self.original_root_path = app_module.app.root_path
        self.original_testing = app_module.app.config.get("TESTING", False)
        os.chdir(self.temporary_directory.name)
        app_module.app.root_path = self.temporary_directory.name
        app_module.app.config["TESTING"] = True
        self.stats_patcher = patch("app.update_stat")
        self.stats_patcher.start()
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.stats_patcher.stop()
        os.chdir(self.original_directory)
        app_module.app.root_path = self.original_root_path
        app_module.app.config["TESTING"] = self.original_testing
        self.temporary_directory.cleanup()

    def test_report_docx_and_ppt_downloads_are_valid_files(self):
        with patch("services.report_service.ask_ollama", return_value="Verified test section."):
            report = self.client.post("/generate-report", json={"content": "Test topic"})
        self.assertEqual(report.status_code, 200)
        with self.client.get(report.get_json()["download_url"]) as report_download:
            self.assertEqual(report_download.status_code, 200)
            self.assertEqual(report_download.mimetype, "application/pdf")
            self.assertTrue(report_download.data.startswith(b"%PDF"))

        docx_sections = {name: "Verified test section." for name in (
            "Abstract", "Introduction", "Methodology", "Analysis", "Findings",
            "Conclusion", "Future Scope", "References",
        )}
        with patch("services.docx_service.get_report_sections_preview", return_value=docx_sections):
            docx = self.client.post("/generate-docx", json={"content": "Test topic"})
        self.assertEqual(docx.status_code, 200)
        with self.client.get(docx.get_json()["download_url"]) as docx_download:
            self.assertEqual(docx_download.status_code, 200)
            self.assertEqual(
                docx_download.mimetype,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            self.assertTrue(docx_download.data.startswith(b"PK"))

        slides = [
            {"title": "Test topic", "subtitle": "Test", "is_cover": True},
            {"title": "Findings", "bullets": ["Verified test finding."], "is_cover": False},
        ]
        with patch("services.ppt_service._get_presentation_slides", return_value=slides):
            ppt = self.client.post(
                "/generate-ppt",
                json={"title": "Test topic", "content": "Verified source material."},
            )
        self.assertEqual(ppt.status_code, 200)
        with self.client.get(ppt.get_json()["download_url"]) as ppt_download:
            self.assertEqual(ppt_download.status_code, 200)
            self.assertEqual(
                ppt_download.mimetype,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
            self.assertTrue(ppt_download.data.startswith(b"PK"))

    def test_citation_agent_and_research_tool_routes_keep_response_shapes(self):
        citations_xml = (
            "<apa>Test APA citation</apa><ieee>Test IEEE citation</ieee>"
            "<mla>Test MLA citation</mla><chicago>Test Chicago citation</chicago>"
        )
        with patch("app.ask_ollama", return_value=citations_xml), patch("app.update_stat"):
            citations = self.client.post(
                "/generate-citations",
                json={"title": "Test source", "author": "Example Author", "year": "2024"},
            )
        self.assertEqual(citations.status_code, 200)
        self.assertEqual(set(citations.get_json()) - {"success"}, {"apa", "ieee", "mla", "chicago"})

        with patch("app.summary_agent", return_value="Concise summary"):
            agent = self.client.post("/agent", json={"agent": "summary", "content": "Test content"})
        self.assertEqual(agent.status_code, 200)
        self.assertEqual(agent.get_json()["result"], "Concise summary")

        with patch("app.ask_ollama", return_value="Generated test topics"):
            tool = self.client.post(
                "/research-enhancements",
                json={"tool": "topic_generator", "content": "Test research domain"},
            )
        self.assertEqual(tool.status_code, 200)
        self.assertEqual(tool.get_json()["result"], "Generated test topics")


if __name__ == "__main__":
    unittest.main()