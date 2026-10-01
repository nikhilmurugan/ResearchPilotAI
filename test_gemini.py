import os

import google.generativeai as genai

print("Starting...")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("Set GEMINI_API_KEY in the environment before running this test.")

genai.configure(api_key=api_key)

print("API configured")

model = genai.GenerativeModel(
    "models/gemini-2.5-flash"
)

print("Model loaded")

response = model.generate_content(
    "Say hello in one sentence."
)

print("Response received")
print(response.text)