import gradio as gr
import torch
import json
import threading
import time
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer
from src.model import AirDwaModel

print("🚁 Starting AirDwa Global System...")

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
# 2. LOAD AI MODELS (Whisper & Qwen)
# ==========================================
device = 0 if torch.cuda.is_available() else -1 
asr_pipe = pipeline("automatic-speech-recognition", model="ayoubkirouane/whisper-small-ar", device=device)

model_name = "Qwen/Qwen2.5-1.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
llm = AutoModelForCausalLM.from_pretrained(
    model_name, 
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto"
)

def extract_with_llm(transcription):
    messages = [
        {"role": "system", "content": """You are an AI assistant for a drone medical dispatch system in Morocco. 
        Read the transcribed Arabic/Darija text and extract the requested medicine and the target station number.
        Output ONLY a valid JSON object with the keys "medicine" (string) and "station" (number). 
        Example: {"medicine": "antivenom", "station": 3}"""},
        {"role": "user", "content": transcription}
    ]
    
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(llm.device)
    
    outputs = llm.generate(**inputs, max_new_tokens=50, temperature=0.1)
    response_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    
    try:
        data = json.loads(response_text)
        return str(data.get("medicine", "Unknown")).lower(), str(data.get("station", "Unknown"))
    except:
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
            out_transcript = gr.Textbox(label="📝 Whisper Transcription")
            with gr.Row():
                out_med = gr.Textbox(label="💊 Medicament")
                out_station = gr.Textbox(label="📍 Target Station")
            out_status = gr.Textbox(label="💻 Simulation Status")
            
    submit_btn.click(
        fn=process_voice_command, 
        inputs=audio_in, 
        outputs=[out_transcript, out_med, out_station, out_status]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1")