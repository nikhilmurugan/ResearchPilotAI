import requests
import json
import os
import time

BASE_URL = "http://127.0.0.1:5000"

def test_status():
    r = requests.get(f"{BASE_URL}/status")
    assert r.status_code == 200
    print("Status endpoint: OK")

def test_stats():
    r = requests.get(f"{BASE_URL}/stats")
    assert r.status_code == 200
    print("Stats endpoint: OK")

def test_agents():
    r = requests.get(f"{BASE_URL}/agents")
    assert r.status_code == 200
    assert len(r.json()["agents"]) > 0
    print("Agents list: OK")

def test_chat():
    r = requests.post(f"{BASE_URL}/chat", json={"message": "What is 2+2? Answer in one word."})
    assert r.status_code == 200
    assert "response" in r.json()
    print("Chat endpoint: OK")

def test_pdf_upload():
    # Create a dummy PDF
    from reportlab.pdfgen import canvas
    pdf_path = "test.pdf"
    c = canvas.Canvas(pdf_path)
    c.drawString(100, 750, "This is a test PDF document for research analysis.")
    c.save()
    
    with open(pdf_path, "rb") as f:
        r = requests.post(f"{BASE_URL}/upload-pdf", files={"file": ("test.pdf", f, "application/pdf")})
    
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == True
    assert len(data["content"]) > 0
    print("PDF Upload: OK")
    
    # Analyze PDF
    r2 = requests.post(f"{BASE_URL}/analyze-pdf", json={"content": data["content"]})
    assert r2.status_code == 200
    assert "summary" in r2.json()
    print("PDF Analyze: OK")

def test_report_gen():
    r = requests.post(f"{BASE_URL}/generate-report", json={"content": "Artificial Intelligence in Healthcare"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == True
    assert "download_url" in data
    
    # Download report
    r2 = requests.get(f"{BASE_URL}{data['download_url']}")
    assert r2.status_code == 200
    assert len(r2.content) > 0
    print("Report Generator (PDF): OK")

def test_docx_gen():
    r = requests.post(f"{BASE_URL}/generate-docx", json={"content": "Quantum Computing Basics"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == True
    assert "download_url" in data
    
    # Download docx
    r2 = requests.get(f"{BASE_URL}{data['download_url']}")
    assert r2.status_code == 200
    assert len(r2.content) > 0
    print("DOCX Generator: OK")

def test_ppt_gen():
    r = requests.post(f"{BASE_URL}/generate-ppt", json={"title": "Space Exploration", "content": "Mars rovers and future missions."})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == True
    assert "download_url" in data
    
    # Download ppt
    r2 = requests.get(f"{BASE_URL}{data['download_url']}")
    assert r2.status_code == 200
    assert len(r2.content) > 0
    print("PPT Generator: OK")

def test_citations():
    r = requests.post(f"{BASE_URL}/generate-citations", json={
        "title": "Attention Is All You Need",
        "author": "Vaswani",
        "year": "2017",
        "journal": "NIPS",
        "publisher": ""
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] == True
    assert "apa" in data and "ieee" in data
    print("Citation Generator: OK")

def test_research_tools():
    tools = ["topic_generator", "gap_finder", "lit_review", "abstract_generator"]
    for t in tools:
        r = requests.post(f"{BASE_URL}/research-enhancements", json={
            "tool": t,
            "content": "Impact of AI on academic integrity"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] == True
        assert len(data["result"]) > 0
    print("Research Tools: OK")

def run_all():
    try:
        test_status()
        test_stats()
        test_agents()
        test_chat()
        test_pdf_upload()
        test_report_gen()
        test_docx_gen()
        test_ppt_gen()
        test_citations()
        test_research_tools()
        print("ALL TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        import traceback
        print(f"Test failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    run_all()
