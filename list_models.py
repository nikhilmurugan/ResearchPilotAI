"""
list_models.py — legacy Gemini utility (no longer used).
ResearchPilotAI now uses Ollama. Run `ollama list` to see available models.
"""
import subprocess
result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
print(result.stdout or result.stderr)