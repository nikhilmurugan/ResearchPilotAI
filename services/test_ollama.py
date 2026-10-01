"""
test_ollama.py
--------------
Quick smoke-test for the Ollama service layer.
Run:  python test_ollama.py
"""

import sys
sys.path.insert(0, ".")

from services.ollama_service import ask_ollama, is_ollama_available, OllamaError

def main():
    print("=== ResearchPilotAI — Ollama smoke test ===\n")

    if not is_ollama_available():
        print("❌  Ollama server is not running. Please start Ollama.")
        sys.exit(1)

    print("✅  Ollama server is reachable.\n")

    try:
        response = ask_ollama("Say hello in one sentence.")
        print(f"Model response: {response}\n")
        print("✅  Test passed.")
    except OllamaError as e:
        print(f"❌  OllamaError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()