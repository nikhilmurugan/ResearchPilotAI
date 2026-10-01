"""
app.py
------
ResearchPilotAI — Flask application.
All AI features are powered by Ollama (qwen2.5-coder:3b).
"""

import os
import re
import uuid
import json
import logging
from datetime import datetime
from typing import Generator

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context
from werkzeug.utils import secure_filename

from services.agents import (
    CitationAgent,
    ReportAgent,
    ResearchAgent,
    SummaryAgent,
    citation_agent,
    report_agent,
    research_agent,
    summary_agent,
)
from services.ollama_service import (
    OLLAMA_EMBEDDING_MODEL,
    OLLAMA_MODEL,
    OllamaError,
    ask_ollama,
    stream_ollama,
    is_ollama_available,
    set_active_settings,
)
from services.pdf_service import PDFError, analyze_pdf, extract_pdf_text
from services.retrieval_service import RetrievalError, answer_document_question
from services.ppt_service import create_ppt
from services.report_service import REPORTS_DIR, create_pdf_report
from services.docx_service import create_docx

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
PRESENTATIONS_DIR = "presentations"
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB

for folder in (UPLOAD_FOLDER, REPORTS_DIR, PRESENTATIONS_DIR):
    os.makedirs(folder, exist_ok=True)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

_DEFAULT_STATS = {
    "total_chats": 0,
    "pdf_uploads": 0,
    "reports_generated": 0,
    "ppt_generated": 0,
    "docx_generated": 0,
    "citations_generated": 0,
}

if not os.path.exists("data/chat_history.json"):
    with open("data/chat_history.json", "w") as f:
        json.dump([], f)

if not os.path.exists("data/stats.json"):
    with open("data/stats.json", "w") as f:
        json.dump(_DEFAULT_STATS, f, indent=4)


# ── Helpers ────────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def json_error(message: str, status: int = 400):
    logger.warning("API error (%d): %s", status, message)
    return jsonify({"success": False, "error": message}), status


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"success": False, "error": "Request body exceeds the 32 MB upload limit."}), 413


def save_chat(user_msg: str, ai_msg: str) -> None:
    file_path = "data/chat_history.json"
    try:
        with open(file_path, "r") as f:
            chats = json.load(f)
    except Exception:
        chats = []

    chats.append({
        "question": user_msg,
        "answer": ai_msg,
        "time": datetime.now().strftime("%d-%m-%Y %H:%M"),
    })

    with open(file_path, "w") as f:
        json.dump(chats, f, indent=4)


def update_stat(key: str) -> None:
    try:
        with open("data/stats.json", "r") as f:
            stats = json.load(f)
    except Exception:
        stats = dict(_DEFAULT_STATS)

    stats[key] = stats.get(key, 0) + 1

    with open("data/stats.json", "w") as f:
        json.dump(stats, f, indent=4)


# ── Before-request hook ────────────────────────────────────────────────────────

@app.before_request
def apply_model_settings():
    """Allow callers to override Ollama settings per-request via modelSettings JSON."""
    set_active_settings(OLLAMA_MODEL, 0.7, 2048)
    if request.is_json:
        data = request.get_json(silent=True) or {}
        settings = data.get("modelSettings", {}) if isinstance(data, dict) else {}
        if not isinstance(settings, dict):
            settings = {}
        if settings:
            model_name = settings.get("model", OLLAMA_MODEL)
            if not isinstance(model_name, str) or not model_name.strip() or len(model_name) > 128:
                model_name = OLLAMA_MODEL
            try:
                temperature = min(1.0, max(0.0, float(settings.get("temperature", 0.7))))
            except (ValueError, TypeError):
                temperature = 0.7
            try:
                max_tokens = min(8192, max(256, int(settings.get("maxTokens", 2048))))
            except (ValueError, TypeError):
                max_tokens = 2048

            set_active_settings(model_name, temperature, max_tokens)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template(
        "index.html",
        api_configured=is_ollama_available(),
        default_model=OLLAMA_MODEL,
    )


@app.route("/status")
def status():
    ollama_ok = is_ollama_available()
    return jsonify(
        {
            "status": "running",
            "project": "ResearchPilotAI",
            "version": "2.1",
            "ollama_available": ollama_ok,
            "model": OLLAMA_MODEL,
            "embedding_model": OLLAMA_EMBEDDING_MODEL,
        }
    )


@app.route("/chat", methods=["POST"])
def chat():
    """Non-streaming fallback chat endpoint."""
    try:
        data = request.get_json(silent=True) or {}
        user_message = data.get("message", "").strip()

        if not user_message:
            return json_error("Message cannot be empty.")

        ai_response = ask_ollama(user_message)
        save_chat(user_message, ai_response)
        update_stat("total_chats")
        return jsonify({"success": True, "response": ai_response})

    except OllamaError:
        return json_error("Ollama is unavailable or the selected model could not complete the request.", 503)
    except Exception:
        logger.exception("Chat error")
        return json_error("Chat failed. Please try again.", 500)


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    The frontend reads each token progressively.
    """
    try:
        data = request.get_json(silent=True) or {}
        user_message = data.get("message", "").strip()

        if not user_message:
            return json_error("Message cannot be empty.")

        logger.info("Streaming chat request: %d chars", len(user_message))

        # Collect full response for history while streaming
        full_response: list[str] = []

        def event_stream() -> Generator[str, None, None]:
            try:
                for token in stream_ollama(user_message):
                    full_response.append(token)
                    # SSE format: data: <payload>\n\n
                    payload = json.dumps({"token": token})
                    yield f"data: {payload}\n\n"

                # Final event signals completion
                complete_text = "".join(full_response)
                yield f"data: {json.dumps({'done': True, 'full': complete_text})}\n\n"

                # Persist only after full response is assembled
                save_chat(user_message, complete_text)
                update_stat("total_chats")

            except OllamaError:
                yield f"data: {json.dumps({'error': 'Ollama is unavailable or the selected model could not complete the request.'})}\n\n"
            except Exception:
                logger.exception("Streaming error")
                yield f"data: {json.dumps({'error': 'Streaming failed. Please try again.'})}\n\n"

        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    except Exception:
        logger.exception("Chat stream setup error")
        return json_error("Streaming setup failed. Please try again.", 500)


@app.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    try:
        if "file" not in request.files:
            return json_error("No file uploaded.")

        file = request.files["file"]

        if not file or file.filename == "":
            return json_error("Empty filename.")

        if not allowed_file(file.filename):
            return json_error("Invalid file type. Only PDF files are allowed.")

        safe_name = secure_filename(file.filename)
        if not safe_name:
            return json_error("Invalid filename.")

        # Check file size before saving (early rejection)
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        if file_size > app.config["MAX_CONTENT_LENGTH"]:
            return json_error(f"File too large. Maximum size is 32 MB.", 413)

        header = file.stream.read(1024)
        file.stream.seek(0)
        if b"%PDF-" not in header:
            return json_error("The uploaded file is not a valid PDF.")

        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(file_path)

        logger.info("PDF uploaded: %s (%d bytes)", safe_name, file_size)

        extracted_text = extract_pdf_text(file_path)
        update_stat("pdf_uploads")

        return jsonify(
            {
                "success": True,
                "filename": safe_name,
                "stored_as": unique_name,
                "content": extracted_text,
                "char_count": len(extracted_text),
            }
        )

    except PDFError:
        return json_error("Unable to extract readable text from this PDF.", 422)
    except Exception:
        logger.exception("PDF upload error")
        return json_error("Upload failed. Please verify the PDF and try again.", 500)


@app.route("/analyze-pdf", methods=["POST"])
def analyze_pdf_route():
    try:
        data = request.get_json(silent=True) or {}
        content = data.get("content", "").strip()

        if not content:
            return json_error("No PDF content provided for analysis.")

        logger.info("PDF analysis request: %d chars", len(content))
        analysis = analyze_pdf(content)
        return jsonify({"success": True, **analysis})

    except (PDFError, OllamaError):
        return json_error("PDF analysis failed. Check the document and local model, then try again.", 503)
    except Exception:
        logger.exception("PDF analysis error")
        return json_error("PDF analysis failed. Please try again.", 500)


@app.route("/document-ask", methods=["POST"])
def document_ask():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return json_error("A JSON object is required.")
    document_id = data.get("stored_as", "")
    question = data.get("question", "")

    if not isinstance(document_id, str) or not document_id:
        return json_error("Uploaded document ID is required.")
    safe_name = secure_filename(document_id)
    if safe_name != document_id or not safe_name.lower().endswith(".pdf"):
        return json_error("Invalid uploaded document ID.")
    if not isinstance(question, str) or not question.strip():
        return json_error("Question cannot be empty.")
    if len(question) > 4000:
        return json_error("Question is too long. Maximum length is 4,000 characters.", 413)

    upload_root = os.path.realpath(app.config["UPLOAD_FOLDER"])
    pdf_path = os.path.realpath(os.path.join(upload_root, safe_name))
    if os.path.commonpath((upload_root, pdf_path)) != upload_root:
        return json_error("Invalid uploaded document ID.")
    if not os.path.isfile(pdf_path):
        return json_error("Uploaded PDF not found. Upload the document again.", 404)

    try:
        original_filename = safe_name[33:] if len(safe_name) > 33 and safe_name[32] == "_" else safe_name
        answer, evidence = answer_document_question(
            pdf_path,
            safe_name,
            original_filename,
            question.strip(),
        )
        return jsonify({
            "success": True,
            "answer": answer,
            "sources": [
                {
                    "filename": item["filename"],
                    "page": item["page"],
                    "section": item["section"],
                    "chunk_id": item["chunk_id"],
                    "excerpt": item["text"],
                }
                for item in evidence
            ],
        })
    except RetrievalError:
        logger.exception("Document retrieval failed")
        return json_error("Could not retrieve evidence from this PDF.", 422)
    except OllamaError:
        logger.exception("Document Q&A model request failed")
        return json_error(
            "Document Q&A is unavailable. Check Ollama and the configured embedding model.",
            503,
        )
    except Exception:
        logger.exception("Document Q&A failed")
        return json_error("Document question could not be answered.", 500)


@app.route("/agent", methods=["POST"])
def run_agent():
    try:
        data = request.get_json(silent=True) or {}
        agent_name = data.get("agent", "").strip().lower()
        content = data.get("content", "").strip()
        citation_format = data.get("format", "both").strip().lower()

        if not agent_name:
            return json_error("Agent name is required.")
        if not content:
            return json_error("Content is required.")

        logger.info("Agent '%s' request: %d chars", agent_name, len(content))

        if agent_name == "research":
            result = research_agent(content)
        elif agent_name == "summary":
            result = summary_agent(content)
        elif agent_name == "citation":
            agent = CitationAgent()
            if citation_format == "apa":
                result = agent.generate_apa(content)
            elif citation_format == "ieee":
                result = agent.generate_ieee(content)
            else:
                result = citation_agent(content)
        elif agent_name == "report":
            result = report_agent(content)
        else:
            return json_error(
                "Invalid agent. Choose: research, summary, citation, or report."
            )

        return jsonify({"success": True, "agent": agent_name, "result": result})

    except OllamaError:
        return json_error("Ollama is unavailable or the selected model could not complete the request.", 503)
    except Exception:
        logger.exception("Agent execution error")
        return json_error("Agent execution failed. Please try again.", 500)


@app.route("/agents", methods=["GET"])
def list_agents():
    agents = [
        {"id": "research", "name": ResearchAgent.name, "description": "Research a topic in depth"},
        {"id": "summary", "name": SummaryAgent.name, "description": "Summarize content"},
        {"id": "citation", "name": CitationAgent.name, "description": "Generate APA and IEEE citations"},
        {"id": "report", "name": ReportAgent.name, "description": "Generate a full research report"},
    ]
    return jsonify({"success": True, "agents": agents})


@app.route("/generate-report", methods=["POST"])
def generate_report():
    try:
        data = request.get_json(silent=True) or {}
        content = data.get("content", "").strip()

        if not content:
            return json_error("Report content cannot be empty.")

        logger.info("Report generation request: %d chars", len(content))
        output_path = create_pdf_report(content)
        update_stat("reports_generated")
        filename = os.path.basename(output_path)

        return jsonify(
            {
                "success": True,
                "message": "Research report generated successfully.",
                "file": filename,
                "download_url": f"/download/report/{filename}",
            }
        )

    except OllamaError:
        return json_error("Ollama is unavailable or the selected model could not complete the request.", 503)
    except Exception:
        logger.exception("Report generation error")
        return json_error("Report generation failed. Please try again.", 500)


@app.route("/generate-ppt", methods=["POST"])
def generate_ppt_route():
    try:
        data = request.get_json(silent=True) or {}
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()

        if not title:
            return json_error("Presentation title is required.")
        if not content:
            return json_error("Presentation content is required.")

        logger.info("PPT generation request: title='%s', content=%d chars", title, len(content))
        output_path = create_ppt(title, content)
        update_stat("ppt_generated")
        filename = os.path.basename(output_path)

        return jsonify(
            {
                "success": True,
                "message": "Presentation generated successfully.",
                "file": filename,
                "download_url": f"/download/presentation/{filename}",
            }
        )

    except OllamaError:
        return json_error("Ollama is unavailable or the selected model could not complete the request.", 503)
    except Exception:
        logger.exception("PPT generation error")
        return json_error("PPT generation failed. Please try again.", 500)


@app.route("/download/report/<path:filename>")
def download_report(filename):
    safe_name = secure_filename(filename)
    file_path = os.path.join(REPORTS_DIR, safe_name)

    if not os.path.isfile(file_path):
        return json_error("Report file not found.", 404)

    mime = "application/pdf" if safe_name.lower().endswith(".pdf") else "application/octet-stream"
    return send_from_directory(REPORTS_DIR, safe_name, as_attachment=True, mimetype=mime)


@app.route("/download/presentation/<path:filename>")
def download_presentation(filename):
    safe_name = secure_filename(filename)
    file_path = os.path.join(PRESENTATIONS_DIR, safe_name)

    if not os.path.isfile(file_path):
        return json_error("Presentation file not found.", 404)

    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return send_from_directory(PRESENTATIONS_DIR, safe_name, as_attachment=True, mimetype=mime)


@app.route("/history")
def history():
    try:
        with open("data/chat_history.json", "r") as f:
            chats = json.load(f)
    except Exception:
        chats = []
    return jsonify(chats)


@app.route("/stats")
def stats():
    try:
        with open("data/stats.json", "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception:
        logger.exception("Statistics read failed")
        return jsonify({"success": False, "error": "Statistics are temporarily unavailable."}), 500


@app.route("/generate-docx", methods=["POST"])
def generate_docx_route():
    try:
        data = request.get_json(silent=True) or {}
        content = data.get("content", "").strip()

        if not content:
            return json_error("Report content cannot be empty.")

        logger.info("DOCX generation request: %d chars", len(content))
        output_path = create_docx(content)
        update_stat("docx_generated")
        filename = os.path.basename(output_path)

        return jsonify(
            {
                "success": True,
                "message": "DOCX Report generated successfully.",
                "file": filename,
                "download_url": f"/download/docx/{filename}",
            }
        )

    except OllamaError:
        return json_error("Ollama is unavailable or the selected model could not complete the request.", 503)
    except Exception:
        logger.exception("DOCX generation error")
        return json_error("DOCX generation failed. Please try again.", 500)


@app.route("/download/docx/<path:filename>")
def download_docx(filename):
    safe_name = secure_filename(filename)
    file_path = os.path.join("reports", safe_name)

    if not os.path.isfile(file_path):
        return json_error("DOCX file not found.", 404)

    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return send_from_directory(
        "reports",
        safe_name,
        as_attachment=True,
        mimetype=mime,
        download_name=safe_name,
    )


@app.route("/generate-citations", methods=["POST"])
def generate_citations_route():
    try:
        data = request.get_json(silent=True) or {}
        title = data.get("title", "").strip()
        author = data.get("author", "").strip()
        year = data.get("year", "").strip()
        journal = data.get("journal", "").strip()
        publisher = data.get("publisher", "").strip()

        if not title:
            return json_error("Title is required for citation generation.")

        # Validate year format
        if year and not re.match(r"^\d{4}$", year):
            year = re.sub(r"[^\d]", "", year)[:4] or "n.d."

        logger.info("Citation generation: title='%s', author='%s', year='%s'", title, author, year)

        prompt = f"""You are a professional academic citation generator.
Generate citations for the following source details in 4 formats: APA (7th edition), IEEE, MLA (9th edition), and Chicago (Notes and Bibliography format).

Source Details:
- Title: {title}
- Author(s): {author or 'Unknown'}
- Year: {year or 'n.d.'}
- Journal/Conference: {journal or 'N/A'}
- Publisher: {publisher or 'N/A'}

Please return the output wrapped in strict XML tags exactly as shown below:
<apa>APA citation text</apa>
<ieee>IEEE citation text</ieee>
<mla>MLA citation text</mla>
<chicago>Chicago citation text</chicago>

Do not include any extra text, headings, or markdown formatting outside these tags.
"""
        raw = ask_ollama(prompt, max_tokens=1024)
        logger.info("Citation response: %d chars", len(raw))

        # Case-insensitive XML tag extraction
        def extract_tag(tag: str, text: str) -> str:
            match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.IGNORECASE | re.DOTALL)
            return match.group(1).strip() if match else ""

        def clean_xml_tags(text: str) -> str:
            return re.sub(r"<[^>]+>", "", text).strip()

        apa = clean_xml_tags(extract_tag("apa", raw))
        ieee = clean_xml_tags(extract_tag("ieee", raw))
        mla = clean_xml_tags(extract_tag("mla", raw))
        chicago = clean_xml_tags(extract_tag("chicago", raw))

        # Heading-based fallback parser
        if not apa or not ieee or not mla or not chicago:
            logger.info("XML parsing incomplete — trying heading-based fallback parser")
            lines = raw.splitlines()
            current_tag = None
            tag_contents: dict[str, list[str]] = {"apa": [], "ieee": [], "mla": [], "chicago": []}
            for line in lines:
                lower_line = line.lower().strip()
                if not lower_line:
                    continue
                if "apa" in lower_line and (":" in lower_line or lower_line.startswith("apa")):
                    current_tag = "apa"
                elif "ieee" in lower_line and (":" in lower_line or lower_line.startswith("ieee")):
                    current_tag = "ieee"
                elif "mla" in lower_line and (":" in lower_line or lower_line.startswith("mla")):
                    current_tag = "mla"
                elif "chicago" in lower_line and (":" in lower_line or lower_line.startswith("chicago")):
                    current_tag = "chicago"
                elif current_tag:
                    clean_line = re.sub(
                        rf'^(?:{current_tag}|{current_tag.upper()}):\s*', '', line, flags=re.I
                    ).strip()
                    if clean_line:
                        tag_contents[current_tag].append(clean_line)

            for tag_key in ("apa", "ieee", "mla", "chicago"):
                if tag_contents[tag_key]:
                    locals()[tag_key] = clean_xml_tags(" ".join(tag_contents[tag_key]))

            # Re-check after fallback
            apa = apa or clean_xml_tags(" ".join(tag_contents["apa"]))
            ieee = ieee or clean_xml_tags(" ".join(tag_contents["ieee"]))
            mla = mla or clean_xml_tags(" ".join(tag_contents["mla"]))
            chicago = chicago or clean_xml_tags(" ".join(tag_contents["chicago"]))

        # Programmatic last-resort fallbacks
        auth_last = author.split(",")[0].strip() if author else "Unknown"
        if not apa:
            apa = f"{author or 'Unknown'} ({year or 'n.d.'}). {title}. {journal or publisher or ''}."
            logger.info("Using programmatic APA fallback")
        if not ieee:
            ieee = f"{auth_last}, \"{title},\" {journal or publisher or ''}, {year or 'n.d.'}."
            logger.info("Using programmatic IEEE fallback")
        if not mla:
            mla = f"{author or 'Unknown'}. \"{title}.\" {journal or publisher or ''}, {year or 'n.d.'}."
            logger.info("Using programmatic MLA fallback")
        if not chicago:
            chicago = f"{author or 'Unknown'}. \"{title}.\" {journal or publisher or ''} ({year or 'n.d.'})."
            logger.info("Using programmatic Chicago fallback")

        update_stat("citations_generated")

        return jsonify({
            "success": True,
            "apa": apa,
            "ieee": ieee,
            "mla": mla,
            "chicago": chicago,
        })

    except OllamaError:
        return json_error("Ollama is unavailable or the selected model could not complete the request.", 503)
    except Exception:
        logger.exception("Citation generation error")
        return json_error("Citation generation failed. Please try again.", 500)


@app.route("/research-enhancements", methods=["POST"])
def research_enhancements_route():
    try:
        data = request.get_json(silent=True) or {}
        tool = data.get("tool", "").strip().lower()
        content = data.get("content", "").strip()

        if not tool:
            return json_error("Tool type is required.")
        if not content:
            return json_error("Input content is required.")

        logger.info("Research tool '%s' request: %d chars", tool, len(content))

        # Limit input to avoid excessive token usage
        excerpt = content[:12000]

        if tool == "topic_generator":
            prompt = f"""You are an academic research advisor. Based on the following research domain or keywords, generate 5 novel, feasible, and high-impact research topics.
Domain/Keywords: {excerpt}

For each topic, structure it as follows:
### Topic [Number]: [Title]
- **Background**: [Brief context and rationale — 2-3 sentences]
- **Research Questions**: [1-2 key questions to address]
- **Expected Methodology**: [Recommended approach, e.g., qualitative, quantitative, simulation]
---
"""
        elif tool == "gap_finder":
            prompt = f"""You are a senior scientist. Analyze the following research topic or literature summary, and identify 3-5 critical research gaps (methodological limitations, population gaps, theoretical inconsistencies, or under-researched variables).
Source Material/Topic: {excerpt}

For each gap, structure it as follows:
### Gap [Number]: [Short Descriptive Name]
- **Description**: [Detailed explanation of the gap and why it exists]
- **Evidence**: [Where this gap appears in current literature or approaches]
- **Actionable Path**: [Concrete steps a researcher can take to address this gap]
---
"""
        elif tool == "lit_review":
            prompt = f"""You are an academic writer. Write a comprehensive, synthesis-focused Literature Review based on the following topic or source materials.
Topic/Materials: {excerpt}

Requirements:
- Synthesize current perspectives and key themes
- Highlight scholarly consensus and ongoing debates
- Use formal academic prose with clear subheadings
- Include a brief introduction and conclusion to the review
- Minimum 5 paragraphs
"""
        elif tool == "abstract_generator":
            prompt = f"""You are a journal editor. Write a structured academic abstract (250-300 words) based on the following research findings or paper summary.
Findings/Summary: {excerpt}

Ensure the abstract contains these labeled sections:
**Background**: The context, problem, and significance.
**Objective**: The core purpose and research aim.
**Methodology**: The research design, data collection, and analytical approach.
**Results**: The key empirical findings and outcomes.
**Conclusion**: Broader implications, contributions, and future directions.
"""
        else:
            return json_error(
                "Invalid research enhancement tool. "
                "Choose: topic_generator, gap_finder, lit_review, or abstract_generator."
            )

        result = ask_ollama(prompt, max_tokens=2048)
        return jsonify({"success": True, "result": result})

    except OllamaError:
        return json_error("Ollama is unavailable or the selected model could not complete the request.", 503)
    except Exception:
        logger.exception("Research enhancement error")
        return json_error("Research enhancement failed. Please try again.", 500)


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(
        debug=debug,
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
    )
