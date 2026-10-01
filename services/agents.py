"""
agents.py
---------
Research-oriented AI agents powered by Ollama.
"""

from services.ollama_service import ask_ollama, OllamaError
import logging

logger = logging.getLogger(__name__)


class BaseAgent:
    name = "BaseAgent"

    def run(self, content: str) -> str:
        raise NotImplementedError


class ResearchAgent(BaseAgent):
    name = "ResearchAgent"

    def run(self, topic: str) -> str:
        if not topic or not topic.strip():
            raise OllamaError("Research topic cannot be empty.")

        prompt = f"""You are a senior academic researcher. Conduct a comprehensive research overview on the following topic.

Topic: {topic.strip()[:8000]}

Provide a structured, scholarly response covering:

## 1. Overview & Background
[Provide historical context and foundational understanding of the topic]

## 2. Key Concepts & Definitions
[Define the most important terms, frameworks, and concepts]

## 3. Current State of Research
[Summarize recent academic progress and dominant schools of thought]

## 4. Important Studies & Developments
[Highlight landmark studies, datasets, or breakthroughs]

## 5. Research Gaps & Open Questions
[Identify unresolved problems and promising research directions]

## 6. Future Directions
[Recommend paths for future investigation and emerging opportunities]

Write in clear, formal academic prose. Use concrete details and examples wherever possible."""

        logger.info("ResearchAgent running for topic: %.60s...", topic)
        return ask_ollama(prompt, max_tokens=2048)


class SummaryAgent(BaseAgent):
    name = "SummaryAgent"

    def run(self, content: str) -> str:
        if not content or not content.strip():
            raise OllamaError("Content to summarize cannot be empty.")

        excerpt = content.strip()[:8000]

        prompt = f"""You are an expert academic summarizer. Summarize the following content clearly and precisely.

Content:
{excerpt}

Provide a well-structured summary with:

## Executive Summary
[2-3 concise sentences capturing the core message]

## Key Points
[Bullet list of the most important facts, findings, or arguments]

## Main Arguments / Contributions
[What the content adds to knowledge or practice]

## Conclusions
[What the content ultimately establishes or recommends]

Be concise, accurate, and avoid padding."""

        logger.info("SummaryAgent running: %d chars input", len(content))
        return ask_ollama(prompt, max_tokens=1024)


class CitationAgent(BaseAgent):
    name = "CitationAgent"

    def generate_apa(self, content: str) -> str:
        if not content or not content.strip():
            raise OllamaError("Citation source information cannot be empty.")

        prompt = f"""Generate APA 7th edition citations for the following source(s).

Source information:
{content.strip()[:8000]}

Instructions:
- Format each source as a correctly structured APA 7th edition reference entry.
- Number each source if multiple are provided.
- Include DOI or URL if available in the source information.
- Use hanging indent style in the text (indent second and subsequent lines).
- Do not include any introduction text — return only the formatted reference list."""

        logger.info("CitationAgent generating APA citation")
        return ask_ollama(prompt, max_tokens=512)

    def generate_ieee(self, content: str) -> str:
        if not content or not content.strip():
            raise OllamaError("Citation source information cannot be empty.")

        prompt = f"""Generate IEEE format citations for the following source(s).

Source information:
{content.strip()[:8000]}

Instructions:
- Format each source as a correctly structured IEEE reference entry.
- Use [1], [2], [3] numbering style.
- Use initials for first names of authors.
- Follow standard IEEE reference format precisely.
- Do not include any introduction text — return only the numbered reference list."""

        logger.info("CitationAgent generating IEEE citation")
        return ask_ollama(prompt, max_tokens=512)

    def run(self, content: str) -> str:
        apa = self.generate_apa(content)
        ieee = self.generate_ieee(content)
        return f"=== APA Citations (7th Edition) ===\n\n{apa}\n\n=== IEEE Citations ===\n\n{ieee}"


class ReportAgent(BaseAgent):
    name = "ReportAgent"

    def run(self, content: str) -> str:
        if not content or not content.strip():
            raise OllamaError("Report content cannot be empty.")

        excerpt = content.strip()[:8000]

        prompt = f"""You are a senior academic research writer. Create a comprehensive, publication-quality research report from the following material.

Material:
{excerpt}

Structure the report with these clearly labeled sections using markdown headings:

# [Derive an appropriate research title from the content]

## Abstract
[200-250 word structured abstract covering background, objective, method, results, conclusion]

## 1. Introduction
[Context, significance, problem statement, objectives, and scope]

## 2. Literature Review
[Survey of related work, theoretical foundations, comparative analysis]

## 3. Methodology
[Research design, data collection, analytical framework, tools, validation]

## 4. Analysis
[Interpretation of data, pattern identification, comparison with prior work]

## 5. Findings
[Empirical results, key discoveries, statistical observations]

## 6. Conclusion
[Summary of contributions, objective achievement, broader implications]

## 7. Future Scope
[Open questions, recommended follow-up studies, practical applications]

## 8. References
[List only references explicitly supplied in the source material. If none are supplied, state that references require verification; do not invent citations.]

Write in formal academic style. Be specific, evidence-based, and avoid vague generalities. Clearly mark details not supported by the supplied material, and do not invent study results or citations."""

        logger.info("ReportAgent running: %d chars input", len(content))
        return ask_ollama(prompt, max_tokens=2048)


# ── Module-level singleton instances ───────────────────────────────────────────

research_agent_instance = ResearchAgent()
summary_agent_instance = SummaryAgent()
citation_agent_instance = CitationAgent()
report_agent_instance = ReportAgent()


def research_agent(topic: str) -> str:
    return research_agent_instance.run(topic)


def summary_agent(content: str) -> str:
    return summary_agent_instance.run(content)


def citation_agent(content: str) -> str:
    return citation_agent_instance.run(content)


def report_agent(content: str) -> str:
    return report_agent_instance.run(content)
