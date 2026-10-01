"""
report_service.py
-----------------
AI-powered academic report generator using Ollama.
Generates structured reports with 9 sections and proper formatting.
"""

import os
import re
import logging
from datetime import datetime

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, HRFlowable, PageBreak
)

from services.ollama_service import ask_ollama, OllamaError

logger = logging.getLogger(__name__)

REPORTS_DIR = "reports"

SECTION_ORDER = [
    "Abstract",
    "Introduction",
    "Methodology",
    "Analysis",
    "Findings",
    "Conclusion",
    "Future Scope",
    "References",
]


def _generate_report_sections(topic_or_content: str) -> dict:
    """
    Ask Ollama to produce each report section individually for higher quality
    and to avoid token-limit truncation of a single massive prompt.
    """
    excerpt = topic_or_content[:10000]

    system_prompt = (
        "You are a senior academic research writer. "
        "Write in formal academic prose. Use clear structure and scholarly language. "
        "Use only facts supported by the supplied material. Mark missing methods, results, "
        "or evidence as not provided. Never invent data, findings, or references. "
        "Do not use markdown formatting — use plain text only."
    )

    section_prompts = {
        "Abstract": (
            f"Write a structured academic Abstract (200–250 words) for a research report on the following topic/content.\n\n"
            f"Include: background, objective, methodology, key results, and conclusion.\n\nTOPIC/CONTENT:\n{excerpt}"
        ),
        "Introduction": (
            f"Write a comprehensive Introduction section for an academic research report on the following topic.\n\n"
            f"Cover: context and significance, problem statement, objectives, and scope of the study.\n\nTOPIC/CONTENT:\n{excerpt}"
        ),
        "Methodology": (
            f"Write a detailed Methodology section for an academic research report on the following topic.\n\n"
            f"Describe: research design, data collection approach, analytical methods, tools, and validation strategy.\n\nTOPIC/CONTENT:\n{excerpt}"
        ),
        "Analysis": (
            f"Write a thorough Analysis section for an academic research report on the following topic.\n\n"
            f"Interpret the data, identify patterns, compare with prior work, and discuss implications.\n\nTOPIC/CONTENT:\n{excerpt}"
        ),
        "Findings": (
            f"Write a detailed Findings section for an academic research report on the following topic.\n\n"
            f"Present the key empirical findings, data insights, and statistical observations clearly.\n\nTOPIC/CONTENT:\n{excerpt}"
        ),
        "Conclusion": (
            f"Write a concise Conclusion section for an academic research report on the following topic.\n\n"
            f"Summarize contributions, verify objectives were met, and state broader implications.\n\nTOPIC/CONTENT:\n{excerpt}"
        ),
        "Future Scope": (
            f"Write a Future Scope section for an academic research report on the following topic.\n\n"
            f"Identify open research questions, recommend follow-up studies, and suggest practical applications.\n\nTOPIC/CONTENT:\n{excerpt}"
        ),
        "References": (
            f"Format only references explicitly included in the supplied material as APA 7th edition entries. "
            f"If no references are provided, return: No source references were supplied; references require verification. "
            f"Never invent authors, titles, journals, dates, DOIs, or URLs.\n\nTOPIC/CONTENT:\n{excerpt}"
        ),
    }

    sections: dict = {}

    for heading in SECTION_ORDER:
        prompt = section_prompts.get(heading)
        if not prompt:
            sections[heading] = "Content not generated."
            continue
        try:
            logger.info("Generating report section: %s", heading)
            result = ask_ollama(prompt, system_prompt=system_prompt, max_tokens=1024)
            sections[heading] = result.strip() if result.strip() else f"Unable to generate {heading}."
        except OllamaError as exc:
            logger.error("Failed to generate section '%s': %s", heading, exc)
            sections[heading] = f"Section generation failed: {exc}"

    return sections


def create_pdf_report(content: str, output_filename: str | None = None) -> str:
    """
    Generate a structured academic PDF report from the given content or topic.
    Returns the absolute path to the saved PDF file.
    """
    if not content or not content.strip():
        raise OllamaError("Report content cannot be empty.")

    os.makedirs(REPORTS_DIR, exist_ok=True)

    if not output_filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"research_report_{timestamp}.pdf"

    if not output_filename.lower().endswith(".pdf"):
        output_filename += ".pdf"

    output_path = os.path.join(REPORTS_DIR, output_filename)

    logger.info("Generating PDF report: %s", output_filename)
    sections = _generate_report_sections(content)

    # ── Page layout ────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.85 * inch,
        leftMargin=0.85 * inch,
        topMargin=1.0 * inch,
        bottomMargin=1.0 * inch,
        title="Research Report",
        author="ResearchPilotAI",
        subject="Academic Research Report",
        creator="ResearchPilotAI — Developed by Nikhil Murugan",
    )

    # ── Colour palette ─────────────────────────────────────────────────────────
    ACCENT     = colors.HexColor("#10B981")
    DARK_TEXT  = colors.HexColor("#1E293B")
    MUTED_TEXT = colors.HexColor("#64748B")

    # ── Styles ─────────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=26,
        alignment=TA_CENTER,
        spaceAfter=6,
        textColor=DARK_TEXT,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=MUTED_TEXT,
        fontName="Helvetica",
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=18,
        spaceAfter=6,
        textColor=ACCENT,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontSize=10.5,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        textColor=DARK_TEXT,
        fontName="Helvetica",
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=MUTED_TEXT,
        fontName="Helvetica",
    )

    # ── Story ──────────────────────────────────────────────────────────────────
    date_str = datetime.now().strftime("%B %d, %Y")
    story = [
        Spacer(1, 0.3 * inch),
        Paragraph("Research Report", title_style),
        Paragraph("Generated by ResearchPilotAI", subtitle_style),
        Paragraph(f"Developed by Nikhil Murugan  ·  {date_str}", subtitle_style),
        Spacer(1, 0.15 * inch),
        HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=6),
        Spacer(1, 0.15 * inch),
    ]

    for heading in SECTION_ORDER:
        body_text = sections.get(heading, "").strip()

        story.append(Paragraph(heading, heading_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=6))

        if body_text:
            # Split on double-newline paragraphs
            for para in re.split(r"\n{2,}", body_text):
                para = para.strip()
                if para:
                    # Escape any stray XML characters
                    para = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    # Convert single newlines to line breaks
                    para = para.replace("\n", "<br/>")
                    story.append(Paragraph(para, body_style))
        else:
            story.append(Paragraph("Content not generated.", body_style))

        story.append(Spacer(1, 0.1 * inch))

    # Footer
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0")))
    story.append(Paragraph(
        "Generated by ResearchPilotAI  ·  Developed by Nikhil Murugan",
        footer_style,
    ))

    doc.build(story)
    logger.info("PDF report saved: %s", output_path)
    return output_path


def get_report_sections_preview(content: str) -> dict:
    return _generate_report_sections(content)
