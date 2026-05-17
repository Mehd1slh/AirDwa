import gradio as gr
import torch
import json
import re
import requests
from transformers import pipeline

print("🚁 Starting AirDwa Systems...")

# ── Ollama config ──────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:1.7b"   # exactly as shown by `ollama list`

# ==========================================
# 1. LOAD THE ASR MODEL (Whisper Small Arabic)
# ==========================================
print("Loading Whisper ASR Model (ayoubkirouane/whisper-small-ar)...")
device = 0 if torch.cuda.is_available() else -1

asr_pipe = pipeline(
    "automatic-speech-recognition",
    model="ayoubkirouane/whisper-small-ar",
    device=device
)
print("✅ Whisper ready. Qwen3 runs via Ollama — no extra loading needed.")

# ==========================================
# 2. LLM EXTRACTION LOGIC  (Ollama / Qwen3)
# ==========================================
def extract_with_llm(transcription):
    """Sends the transcribed Darija/French text to local Qwen3 via Ollama."""

    messages = [
        {"role": "system", "content": """You are an AI assistant for a drone medical dispatch system in Morocco.
The user speaks in Darija or French to request a medicine delivery to a numbered station.

Map the medicine to one of these lowercase English keys:
doliprane, paracetamol, dalidol, antibiotic, antibiotique, amoxicillin, augmentin, aspirin,
insulin, insuline, inhaler, inhalateur, pompe, ventoline,
blood, sang, antivenom, antivenin, serum, epipen, epinephrine, adrenaline, morphine, glucagon

Darija hints:
  دوليبران → doliprane
  مضاد حيوي / antibiotique → antibiotic
  أنسولين → insulin
  بخاخ / pompe / ventoline → inhaler
  دم / sang → blood
  ترياق / sérum / antivenin → antivenom
  إيبيبن / adrénaline → epipen

Output ONLY a valid JSON object — no markdown, no extra text:
{"medicine": "<key>", "station": "<number>"}
Example: {"medicine": "antivenom", "station": "3"}"""},
        {"role": "user", "content": transcription}
    ]

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "think": False,                                    # Ollama-native: disable Qwen3 thinking
                "options": {"temperature": 0.1, "num_predict": 60}
            },
            timeout=30
        )
        resp.raise_for_status()
        payload = resp.json()
        response_text = payload["message"]["content"].strip()

        if not response_text:
            print(f"⚠️  Empty content from Ollama. Full payload: {payload}")
            return "Extraction Failed", "Extraction Failed"

        # Strip <think>…</think> blocks if the model leaked one anyway
        response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()

        # Strip accidental markdown fences
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        print(f"🤖 Qwen3 raw response: {response_text!r}")

        data = json.loads(response_text)
        return str(data.get("medicine", "Unknown")).lower(), str(data.get("station", "Unknown"))

    except requests.exceptions.ConnectionError:
        print("❌ Ollama not reachable — run: ollama serve")
        return "Extraction Failed", "Extraction Failed"
    except Exception as e:
        print(f"❌ LLM extraction error: {e}")
        return "Extraction Failed", "Extraction Failed"

# ==========================================
# 3. MAIN PROCESSING FUNCTION
# ==========================================
def process_voice_command(audio_filepath):
    if not audio_filepath:
        return "No audio provided", "", ""

    try:
        result = asr_pipe(audio_filepath)
        transcription = result["text"]
        medicine, station = extract_with_llm(transcription)
        return transcription, medicine, f"Station {station}"
    except Exception as e:
        return f"Error: {str(e)}", "Error", "Error"

# ==========================================
# 4. GRADIO UI
# ==========================================
demo = gr.Interface(
    fn=process_voice_command,
    inputs=gr.Audio(sources=["microphone", "upload"], type="filepath", label="🗣️ Speak your Order (Darija/Arabic)"),
    outputs=[
        gr.Textbox(label="📝 Raw Transcription"),
        gr.Textbox(label="💊 Medicament Detected"),
        gr.Textbox(label="📍 Target Station Number")
    ],
    title="🚁 AirDwa: Voice-Activated Drone Dispatch",
    description="Whisper transcribes audio. Qwen3:1.7b via Ollama extracts medicine + station."
)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1")