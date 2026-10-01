import tempfile
import unittest
from pathlib import Path

from services.retrieval_service import (
    answer_document_question,
    chunk_pages,
    index_document_pages,
    retrieve_evidence,
)
from services.evaluation_service import (
    citation_coverage,
    compare_retrievers,
    evidence_support_rate,
    failure_rate,
    latency_summary,
    retrieval_metrics,
)


_VOCABULARY = ("orchard", "yield", "attention", "transformer")


def _fake_embedder(texts):
    return [
        [text.lower().split().count(term) for term in _VOCABULARY]
        for text in texts
    ]


class RetrievalServiceTests(unittest.TestCase):
    def test_chunks_retain_page_metadata_and_overlap(self):
        text = " ".join(f"word{index}" for index in range(25))
        chunks = chunk_pages([(7, text)], max_words=10, overlap_words=2)

        self.assertEqual([chunk["page"] for chunk in chunks], [7, 7, 7])
        self.assertEqual(chunks[0]["text"].split()[-2:], chunks[1]["text"].split()[:2])
        self.assertIsNone(chunks[0]["section"])

    def test_retrieval_ranks_relevant_page(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "knowledge.sqlite3"
            index_document_pages(
                "paper.pdf",
                "paper.pdf",
                [
                    (2, "Attention transformer models process language."),
                    (9, "Orchard yield improved after irrigation."),
                ],
                database_path=database_path,
                embedder=_fake_embedder,
            )

            evidence = retrieve_evidence(
                "paper.pdf",
                "orchard yield",
                database_path=database_path,
                embedder=_fake_embedder,
            )

        self.assertEqual(evidence[0]["page"], 9)
        self.assertEqual(evidence[0]["filename"], "paper.pdf")

    def test_indexing_batches_large_embedding_requests(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            calls = []

            def recording_embedder(texts):
                calls.append(len(texts))
                return [[1.0, 0.0] for _ in texts]

            index_document_pages(
                "large.pdf",
                "large.pdf",
                [(page, f"Content for page {page}.") for page in range(1, 34)],
                database_path=Path(temporary_directory) / "knowledge.sqlite3",
                embedder=recording_embedder,
            )

        self.assertEqual(calls, [32, 1])

    def test_answer_returns_the_retrieved_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "knowledge.sqlite3"
            index_document_pages(
                "paper.pdf",
                "paper.pdf",
                [(4, "Orchard yield improved after irrigation.")],
                database_path=database_path,
                embedder=_fake_embedder,
            )

            answer, evidence = answer_document_question(
                "unused.pdf",
                "paper.pdf",
                "paper.pdf",
                "orchard yield",
                database_path=database_path,
                embedder=_fake_embedder,
                answerer=lambda prompt, **kwargs: "Yield improved after irrigation [1].",
            )

        self.assertIn("[1]", answer)
        self.assertEqual(evidence[0]["page"], 4)
        self.assertIn("irrigation", evidence[0]["text"])

    def test_answer_declines_when_vectors_have_no_positive_similarity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "knowledge.sqlite3"

            def orthogonal_embedder(texts):
                return [[1.0, 0.0] if "document" in text else [0.0, 1.0] for text in texts]

            index_document_pages(
                "paper.pdf",
                "paper.pdf",
                [(1, "document fact")],
                database_path=database_path,
                embedder=orthogonal_embedder,
            )
            answer, evidence = answer_document_question(
                "unused.pdf",
                "paper.pdf",
                "paper.pdf",
                "unrelated question",
                database_path=database_path,
                embedder=orthogonal_embedder,
                answerer=lambda *_args, **_kwargs: self.fail("Answer model should not be called"),
            )

        self.assertEqual(answer, "Insufficient evidence found in the uploaded documents.")
        self.assertEqual(evidence, [])


class EvaluationServiceTests(unittest.TestCase):
    def test_retrieval_metrics_and_baseline_comparison_are_calculated(self):
        self.assertEqual(
            retrieval_metrics(["wrong", "target"], ["target"], k=2),
            {"precision_at_k": 0.5, "recall_at_k": 1.0, "mrr_at_k": 0.5},
        )
        cases = [{"relevant_passage_ids": ["target"]}]
        comparison = compare_retrievers(
            cases,
            baseline=lambda _: ["wrong"],
            candidate=lambda _: ["target"],
            k=1,
        )
        self.assertEqual(comparison["baseline"]["recall_at_k"], 0.0)
        self.assertEqual(comparison["candidate"]["recall_at_k"], 1.0)

    def test_operational_metrics_require_real_samples_or_annotations(self):
        claims = [
            {"citations": ["chunk-1"], "evidence_status": "supported"},
            {"citations": [], "evidence_status": "uncertain"},
        ]
        self.assertEqual(citation_coverage(claims), 0.5)
        self.assertEqual(evidence_support_rate(claims), 0.5)
        self.assertEqual(failure_rate([{"success": True}, {"success": False}]), 0.5)
        self.assertEqual(latency_summary([1.0, 3.0])["mean_seconds"], 2.0)
        self.assertIsNone(latency_summary([]))


if __name__ == "__main__":
    unittest.main()