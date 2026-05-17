import gradio as gr
import torch
import json
import threading
import time
import requests
from transformers import pipeline
from src.model import AirDwaModel
from src.agents import MEDICINE_DB

# ── Ollama config ──────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:1.7b"   # exactly as shown by `ollama list`

print("Starting AirDwa Global System...")

# ==========================================
# 1. INITIALIZE AIRDWA SIMULATION
# ==========================================
# Load your generated map data (or leave empty for default)
try:
    with open("maps/custom_airdwa.json", "r") as f:
        map_data = json.load(f)
except:
    map_data = None

# Create the simulation model. Set order_rate=0 to stop random orders!
airdwa_env = AirDwaModel(n_robots=4, order_rate=0.0, map_data=map_data)

def run_simulation_in_background():
    """ Runs the simulation ticks automatically in the background """
    while airdwa_env.running:
        airdwa_env.step()
        time.sleep(1) # 1 tick per second

sim_thread = threading.Thread(target=run_simulation_in_background, daemon=True)
sim_thread.start()

# ==========================================
# 2. LOAD ASR MODEL (Whisper)
# ==========================================
# Qwen runs via Ollama locally — no model loading needed here.
device = 0 if torch.cuda.is_available() else -1
asr_pipe = pipeline("automatic-speech-recognition", model="ayoubkirouane/whisper-small-ar", device=device)

def extract_with_llm(transcription):
    # Build the list of recognized medicine keys so the model stays within bounds
    known_medicines = ", ".join(sorted(set(MEDICINE_DB.keys())))

    messages = [
        {"role": "system", "content": f"""You are an AI assistant for a drone medical dispatch system in Morocco.
The user will speak in Darija (Moroccan Arabic) or French to request a medicine delivery to a numbered station.

Your job:
1. Identify the medicine they are requesting.
2. Map it to ONE of the following recognized keys (lowercase English): {known_medicines}
   - If the user says "دوليبران" or "dalidol" → use "doliprane"
   - If the user says "مضاد حيوي" or "antibiotique" → use "antibiotic"
   - If the user says "أنسولين" → use "insulin"
   - If the user says "بخاخ", "pompe" or "ventoline" → use "inhaler"
   - If the user says "دم" or "sang" → use "blood"
   - If the user says "ترياق", "sérum" or "antivenin" → use "antivenom"
   - If the user says "إيبيبن" or "adrénaline" → use "epipen"
   - Use the closest key from the list for anything else.
3. Extract the station number (integer).

Output ONLY a valid JSON object with exactly two keys:
  "medicine": one of the recognized keys above (string, lowercase)
  "station": the station number as a string (e.g. "3")

Example: {{"medicine": "antivenom", "station": "3"}}
Do not include any other text, markdown, or explanation."""},
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

        # Fallback: if content is empty, Ollama put everything in 'thinking' — shouldn't
        # happen with think=False but guard anyway
        if not response_text:
            print(f"Empty content from Ollama. Full payload: {payload}")
            return "Unknown", "Unknown"

        # Strip <think>…</think> blocks if the model leaked one anyway
        import re
        response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()

        # Strip accidental markdown fences
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        print(f"Qwen3 raw response: {response_text!r}")

        data = json.loads(response_text)
        return str(data.get("medicine", "Unknown")).lower(), str(data.get("station", "Unknown"))

    except requests.exceptions.ConnectionError:
        print("❌ Ollama not reachable — is `ollama serve` running?")
        return "Unknown", "Unknown"
    except Exception as e:
        print(f"❌ LLM extraction error: {e}")
        return "Unknown", "Unknown"

# ==========================================
# 3. GRADIO UI PROCESSING
# ==========================================
def process_voice_command(audio_filepath):
    if not audio_filepath: return "No audio", "", "", "Waiting..."
        
    try:
        # A. Transcribe
        result = asr_pipe(audio_filepath)
        transcription = result["text"]
        
        # B. Extract Intent
        medicine, station = extract_with_llm(transcription)
        
        # C. Inject into Simulation!
        success = airdwa_env.order_manager.create_specific_order(medicine, station)
        
        status = f"✅ Order injected for {medicine} to Station {station}!" if success else f"❌ Failed: Station {station} not found."
        
        # Find which drone picked it up (Optional: wait a moment for the auction to finish)
        time.sleep(0.5) 
        assigned_drone = "Pending/Auction"
        for m in airdwa_env.order_manager.missions:
            if m.medicine_name == medicine and m.assigned_to:
                assigned_drone = f"Drone {m.assigned_to.custom_id} (Speed {m.assigned_to.speed})"
                
        return transcription, medicine.capitalize(), f"Station {station}", status + f" Handled by: {assigned_drone}"
        
    except Exception as e:
        return f"Error: {str(e)}", "Error", "Error", "Failed"

# ==========================================
# 4. LAUNCH DEMO UI
# ==========================================
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🚁 AirDwa: Voice-Activated Command Center")
    gr.Markdown("**Speak in Darija to trigger a drone delivery in the running Mesa environment.**")
    
    with gr.Row():
        with gr.Column():
            audio_in = gr.Audio(sources=["microphone", "upload"], type="filepath", label="🗣️ Audio Input")
            submit_btn = gr.Button("Dispatch Drone", variant="primary")
            
        with gr.Column():
            out_transcript = gr.Textbox(label="Whisper Transcription")
            with gr.Row():
                out_med = gr.Textbox(label="Medicament")
                out_station = gr.Textbox(label="Target Station")
            out_status = gr.Textbox(label="Simulation Status")
            
    submit_btn.click(
        fn=process_voice_command, 
        inputs=audio_in, 
        outputs=[out_transcript, out_med, out_station, out_status]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1")