"""
ppt_service.py
--------------
AI-powered PowerPoint generator for ResearchPilotAI.
Generates a 10-slide academic presentation with professional dark-theme layout.
"""

import os
import json
import re
import logging
from datetime import datetime

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE_TYPE

from services.ollama_service import ask_ollama, OllamaError

logger = logging.getLogger(__name__)

PRESENTATIONS_DIR = "presentations"

# ── Theme colors ───────────────────────────────────────────────────────────────
BG_COLOR        = RGBColor(7,  20,  15)    # #07140F — matches app bg
TEXT_MAIN       = RGBColor(248, 250, 252)  # #F8FAFC
TEXT_MUTED      = RGBColor(148, 163, 184)  # #94A3B8
ACCENT_PRIMARY  = RGBColor(16,  185, 129)  # #10B981 — matches UI accent
ACCENT_GRADIENT = RGBColor(52,  211, 153)  # #34D399

SLIDE_STRUCTURE = [
    {"type": "cover",   "title": "Cover",             "field": "subtitle"},
    {"type": "content", "title": "Executive Summary",  "field": "bullets"},
    {"type": "content", "title": "Introduction",       "field": "bullets"},
    {"type": "content", "title": "Literature Review",  "field": "bullets"},
    {"type": "content", "title": "Methodology",        "field": "bullets"},
    {"type": "content", "title": "Key Findings",       "field": "bullets"},
    {"type": "content", "title": "Analysis",           "field": "bullets"},
    {"type": "content", "title": "Future Scope",       "field": "bullets"},
    {"type": "content", "title": "Conclusion",         "field": "bullets"},
    {"type": "content", "title": "References",         "field": "bullets"},
]


def _get_presentation_slides(title: str, content: str) -> list:
    """
    Query Ollama for slide content and return a list of 10 slide dicts.
    Falls back to intelligent default content on parse failure.
    """
    excerpt = content[:8000]

    prompt = f"""Generate slide content for a 10-slide academic research presentation.
Presentation Title: {title}
Source material/topic:
{excerpt}

Return a JSON array of exactly 10 objects in this EXACT order:
1. Cover slide:      {{"title": "...", "subtitle": "...", "is_cover": true}}
2. Executive Summary:{{"title": "Executive Summary", "bullets": ["...", "...", "..."], "is_cover": false}}
3. Introduction:     {{"title": "Introduction", "bullets": ["...", "...", "..."], "is_cover": false}}
4. Literature Review:{{"title": "Literature Review", "bullets": ["...", "...", "..."], "is_cover": false}}
5. Methodology:      {{"title": "Methodology", "bullets": ["...", "...", "..."], "is_cover": false}}
6. Key Findings:     {{"title": "Key Findings", "bullets": ["...", "...", "..."], "is_cover": false}}
7. Analysis:         {{"title": "Analysis", "bullets": ["...", "...", "..."], "is_cover": false}}
8. Future Scope:     {{"title": "Future Scope", "bullets": ["...", "...", "..."], "is_cover": false}}
9. Conclusion:       {{"title": "Conclusion", "bullets": ["...", "...", "..."], "is_cover": false}}
10. References:      {{"title": "References", "bullets": ["...", "...", "..."], "is_cover": false}}

Rules:
- Each bullet must be a complete, meaningful sentence (not a single word).
- Provide 3–5 bullets per content slide.
- Make content directly relevant to: {title}
- Use only facts in the supplied source material; mark missing details as not provided.
- Do not invent empirical results, statistical significance, studies, or references.
- Output ONLY the JSON array — no markdown, no explanation, no extra text.
Start your response with [ and end with ]."""

    try:
        raw = ask_ollama(prompt, max_tokens=2048)

        # Try to extract JSON from markdown code block first
        json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Find the outermost JSON array
            start = raw.find("[")
            end   = raw.rfind("]")
            if start != -1 and end != -1 and end > start:
                json_str = raw[start:end + 1]
            else:
                json_str = raw.strip()

        slides = json.loads(json_str)

        # Validate and normalise
        if not isinstance(slides, list) or len(slides) < 2:
            raise ValueError(f"Expected a list of slides, got {type(slides)}")

        # Pad to 10 if Ollama returned fewer
        while len(slides) < 10:
            idx = len(slides)
            template = SLIDE_STRUCTURE[idx] if idx < len(SLIDE_STRUCTURE) else SLIDE_STRUCTURE[-1]
            slides.append({
                "title": template["title"],
                "bullets": [f"Content for {template['title']} will be elaborated here."],
                "is_cover": template["type"] == "cover",
            })

        return slides[:10]

    except Exception as exc:
        logger.warning("Ollama slide JSON parsing failed: %s — using fallback content.", exc)
        return _fallback_slides(title)


def _fallback_slides(title: str) -> list:
    """Return sensible default slides when Ollama JSON parsing fails."""
    return [
        {
            "title": title,
            "subtitle": "An Academic Research Presentation",
            "is_cover": True,
        },
        {
            "title": "Executive Summary",
            "bullets": [
                f"This presentation concerns {title}.",
                "Source-specific summary details were not available to the fallback renderer.",
                "Verify statements against the supplied research material.",
            ],
            "is_cover": False,
        },
        {
            "title": "Introduction",
            "bullets": [
                f"The topic is {title}.",
                "The source-specific background and research objectives were not available to the fallback renderer.",
                "Add verified context from the primary research material.",
            ],
            "is_cover": False,
        },
        {
            "title": "Literature Review",
            "bullets": [
                "No verifiable literature details were available to the fallback renderer.",
                "Add and verify primary sources before presenting a literature synthesis.",
            ],
            "is_cover": False,
        },
        {
            "title": "Methodology",
            "bullets": [
                "The research design was not available to the fallback renderer.",
                "Describe only data collection and analysis methods documented in the source.",
            ],
            "is_cover": False,
        },
        {
            "title": "Key Findings",
            "bullets": [
                "No validated findings were available to the fallback renderer.",
                "Do not report statistical results unless they are present in the source material.",
            ],
            "is_cover": False,
        },
        {
            "title": "Analysis",
            "bullets": [
                "Source-specific analysis was not available to the fallback renderer.",
                "Interpret results only when supporting data and methods are documented.",
            ],
            "is_cover": False,
        },
        {
            "title": "Future Scope",
            "bullets": [
                "Future directions were not available to the fallback renderer.",
                "Derive proposed work from limitations explicitly described in the source.",
            ],
            "is_cover": False,
        },
        {
            "title": "Conclusion",
            "bullets": [
                "No source-grounded conclusion was available to the fallback renderer.",
                "Review the primary material before stating conclusions or contributions.",
            ],
            "is_cover": False,
        },
        {
            "title": "References",
            "bullets": [
                "No verifiable references were available to the fallback renderer.",
                "Add bibliographic details from confirmed primary sources.",
            ],
            "is_cover": False,
        },
    ]


# ── Shape helpers ──────────────────────────────────────────────────────────────

def _set_bg(slide) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = BG_COLOR


def _add_rect(slide, left, top, width, height, color: RGBColor):
    from pptx.util import Inches as I_
    from pptx.enum.shapes import MSO_SHAPE
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()  # no border
    return shape


def _add_textbox(slide, left, top, width, height) -> object:
    tx = slide.shapes.add_textbox(left, top, width, height)
    tx.text_frame.word_wrap = True
    return tx


# ── Slide builders ─────────────────────────────────────────────────────────────

def _build_cover_slide(slide, slide_info: dict, slide_num: int) -> None:
    _set_bg(slide)

    # Left accent bar
    _add_rect(slide, Inches(0), Inches(0), Inches(0.45), Inches(7.5), ACCENT_PRIMARY)

    # Title area
    tx = _add_textbox(slide, Inches(1.0), Inches(1.8), Inches(11.0), Inches(4.5))
    tf = tx.text_frame

    # Main title
    p = tf.paragraphs[0]
    p.text = slide_info.get("title", "Research Presentation")
    p.font.name  = "Calibri"
    p.font.size  = Pt(40)
    p.font.bold  = True
    p.font.color.rgb = TEXT_MAIN
    p.space_after = Pt(16)

    # Subtitle
    p2 = tf.add_paragraph()
    p2.text = slide_info.get("subtitle", "An Academic Research Framework")
    p2.font.name  = "Calibri"
    p2.font.size  = Pt(20)
    p2.font.color.rgb = TEXT_MUTED
    p2.space_after = Pt(30)

    # Author + date
    p3 = tf.add_paragraph()
    date_str = datetime.now().strftime("%B %d, %Y")
    p3.text = f"ResearchPilotAI  ·  Nikhil Murugan  ·  {date_str}"
    p3.font.name  = "Calibri"
    p3.font.size  = Pt(13)
    p3.font.color.rgb = ACCENT_PRIMARY

    # Bottom accent line
    _add_rect(slide, Inches(0.45), Inches(6.9), Inches(12.9), Inches(0.12), ACCENT_GRADIENT)


def _build_content_slide(slide, slide_info: dict, slide_num: int) -> None:
    _set_bg(slide)

    # Top accent bar
    _add_rect(slide, Inches(0), Inches(0), Inches(13.333), Inches(0.12), ACCENT_PRIMARY)

    # Slide number indicator (top-right)
    num_tx = _add_textbox(slide, Inches(12.0), Inches(0.18), Inches(1.1), Inches(0.4))
    num_p = num_tx.text_frame.paragraphs[0]
    num_p.text = f"{slide_num:02d}"
    num_p.alignment = PP_ALIGN.RIGHT
    num_p.font.name  = "Calibri"
    num_p.font.size  = Pt(11)
    num_p.font.color.rgb = ACCENT_PRIMARY

    # Title
    title_tx = _add_textbox(slide, Inches(0.6), Inches(0.5), Inches(11.5), Inches(1.1))
    title_tf = title_tx.text_frame
    t = title_tf.paragraphs[0]
    t.text = slide_info.get("title", "")
    t.font.name  = "Calibri"
    t.font.size  = Pt(30)
    t.font.bold  = True
    t.font.color.rgb = TEXT_MAIN

    # Thin divider below title
    _add_rect(slide, Inches(0.6), Inches(1.55), Inches(11.5), Inches(0.04), ACCENT_PRIMARY)

    # Bullets
    bullets = slide_info.get("bullets", [])
    bul_tx = _add_textbox(slide, Inches(0.6), Inches(1.75), Inches(11.5), Inches(4.8))
    bul_tf = bul_tx.text_frame

    for idx, b_text in enumerate(bullets[:6]):  # max 6 bullets
        p = bul_tf.paragraphs[0] if idx == 0 else bul_tf.add_paragraph()
        p.text = f"▸  {b_text.strip()}"
        p.font.name  = "Calibri"
        p.font.size  = Pt(17)
        p.font.color.rgb = TEXT_MAIN
        p.space_after = Pt(10)

    # Footer bar
    _add_rect(slide, Inches(0), Inches(7.2), Inches(13.333), Inches(0.3), RGBColor(14, 29, 23))

    foot_left = _add_textbox(slide, Inches(0.5), Inches(7.22), Inches(7.0), Inches(0.26))
    fl = foot_left.text_frame.paragraphs[0]
    fl.text = "Generated by ResearchPilotAI  ·  Nikhil Murugan"
    fl.font.name  = "Calibri"
    fl.font.size  = Pt(8.5)
    fl.font.color.rgb = TEXT_MUTED

    foot_right = _add_textbox(slide, Inches(9.5), Inches(7.22), Inches(3.5), Inches(0.26))
    fr = foot_right.text_frame.paragraphs[0]
    fr.alignment = PP_ALIGN.RIGHT
    date_str = datetime.now().strftime("%b %d, %Y")
    fr.text = f"{date_str}  ·  Slide {slide_num}"
    fr.font.name  = "Calibri"
    fr.font.size  = Pt(8.5)
    fr.font.color.rgb = TEXT_MUTED


# ── Public API ─────────────────────────────────────────────────────────────────

def create_ppt(title: str, content: str, output_filename: str | None = None) -> str:
    """
    Generate a 10-slide professional PowerPoint presentation.

    Returns the absolute path to the saved .pptx file.
    """
    if not title or not title.strip():
        raise OllamaError("Presentation title cannot be empty.")
    if not content or not content.strip():
        raise OllamaError("Presentation content cannot be empty.")

    os.makedirs(PRESENTATIONS_DIR, exist_ok=True)

    if not output_filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"research_presentation_{timestamp}.pptx"

    if not output_filename.lower().endswith(".pptx"):
        output_filename += ".pptx"

    output_path = os.path.join(PRESENTATIONS_DIR, output_filename)

    logger.info("Generating PPT: %s", output_filename)
    slides_data = _get_presentation_slides(title.strip(), content.strip())

    prs = Presentation()
    prs.slide_width  = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]  # blank

    for i, slide_info in enumerate(slides_data):
        slide = prs.slides.add_slide(blank_layout)
        slide_num = i + 1
        is_cover = slide_info.get("is_cover", False) or (slide_num == 1)

        if is_cover:
            _build_cover_slide(slide, slide_info, slide_num)
        else:
            _build_content_slide(slide, slide_info, slide_num)

    prs.save(output_path)
    logger.info("PPT saved: %s", output_path)
    return output_path
