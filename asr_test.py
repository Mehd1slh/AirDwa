import gradio as gr
import torch
import json
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer

print("🚁 Starting AirDwa Systems...")

# ==========================================
# 1. LOAD THE ASR MODEL (Whisper Small Arabic)
# ==========================================
print("Loading Whisper ASR Model (ayoubkirouane/whisper-small-ar)...")
# Automatically use GPU if available, otherwise use CPU
device = 0 if torch.cuda.is_available() else -1 

asr_pipe = pipeline(
    "automatic-speech-recognition", 
    model="ayoubkirouane/whisper-small-ar",
    device=device
)

# ==========================================
# 2. LOAD THE LOCAL LLM (Qwen 1.5B)
# ==========================================
print("Loading Qwen 1.5B Local LLM...")
model_name = "Qwen/Qwen2.5-1.5B-Instruct"

tokenizer = AutoTokenizer.from_pretrained(model_name)
llm = AutoModelForCausalLM.from_pretrained(
    model_name, 
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto"
)

# ==========================================
# 3. LLM EXTRACTION LOGIC
# ==========================================
def extract_with_llm(transcription):
    """Passes the transcribed Arabic text to Qwen to extract clean JSON."""
    
    messages = [
        {"role": "system", "content": """You are an AI assistant for a drone medical dispatch system in Morocco. 
        Read the transcribed Arabic/Darija text and extract the requested medicine and the station number.
        Output ONLY a valid JSON object with the keys "medicine" and "station". Do not include any other text or markdown formatting.
        Example: {"medicine": "Doliprane", "station": "31"}"""},
        {"role": "user", "content": transcription}
    ]
    
    # Prepare prompt for Qwen
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(llm.device)
    
    # Generate the response
    outputs = llm.generate(**inputs, max_new_tokens=50, temperature=0.1)
    response_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    
    # Safely parse the JSON
    try:
        data = json.loads(response_text)
        return data.get("medicine", "Unknown"), str(data.get("station", "Unknown"))
    except json.JSONDecodeError:
        return "Extraction Failed", "Extraction Failed"

# ==========================================
# 4. MAIN PROCESSING FUNCTION
# ==========================================
def process_voice_command(audio_filepath):
    if not audio_filepath:
        return "No audio provided", "", ""
        
    try:
        # A. Transcribe the audio using the Whisper Pipeline
        result = asr_pipe(audio_filepath)
        transcription = result["text"]
        
        # B. Extract using Qwen
        medicine, station = extract_with_llm(transcription)
        
        return transcription, medicine, f"Station {station}"
        
    except Exception as e:
        return f"Error: {str(e)}", "Error", "Error"

# ==========================================
# 5. GRADIO UI
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
    description="Record a voice note. The ayoubkirouane/whisper-small-ar model handles the transcription, and a local Qwen 1.5B LLM extracts the variables for the drone swarm."
)

if __name__ == "__main__":
    # Launch locally and let Gradio assign an open port automatically
    demo.launch(server_name="127.0.0.1")