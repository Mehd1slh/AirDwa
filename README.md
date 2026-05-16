# AirDwa (أير-دوا): Voice-Activated Drone Medical Dispatch



**1. Project Overview** In the mountainous and rural regions of Morocco, rugged terrain and poorly maintained roads create severe barriers to healthcare. A sudden emergency can become fatal simply because of geographical isolation.

**AirDwa** democratizes emergency healthcare access by deploying a decentralized, Multi-Agent Drone Logistics System. Driven by an advanced Auction-based AI allocation algorithm and triggered seamlessly via a Darija Voice Assistant, AirDwa guarantees that critical medical supplies reach patients in remote douars in minutes, bypassing topographical obstacles entirely.

**2. Key Features**

- **Darija Voice Activation (ASR & LLM):** A zero-tech-literacy interface. Users speak naturally in Darija (e.g., "Khassna dwa dyal skhana..."). The system uses a fine-tuned Whisper model combined with a local LLM to extract the medical intent and destination.
    
- **Real-World Map Auto-Generation:** A custom map builder that pulls data from OpenStreetMap and OpenTopography. Select a bounding box anywhere in Morocco, and the system automatically maps pharmacies, telecom towers (for charging), and impassable high-altitude terrain into the simulation grid.
    
- **Auction-Based Dispatch Protocol:** Drones bid on missions based on a complex cost function prioritizing battery preservation, flight distance, and payload urgency.
    
- **Patient-First Rescue Protocol:** If a drone suffers a critical failure mid-flight, the central dispatcher abandons the crashed payload and instantly orders a fresh supply from the nearest hospital via a new drone, ensuring the patient is always the priority.
    
- **Telecom Tower Recharging:** Utilizes existing telecom infrastructure in rural areas as mid-flight charging pads to keep the fleet sustainable.
    

**3. Project Structure**

- `app.py`: Streamlit UI for the Automated Custom Map Builder.
    
- `demo.py`: Main global system launcher bridging ASR and Simulation.
    
- `requirements.txt`: Project dependencies.
    
- `asr/`: Contains Darija ASR transcription, NLP extraction rules, and Voice command processing via Whisper and local LLMs.
    
- `map_build/`: OSM and OpenTopography BBox generation scripts.
    
- `pygame/`: Logic for manual grid layout editing and the main Pygame GUI for real-time simulation monitoring.
    
- `maps/`: Saved custom simulation layouts.
    
- `src/`: Behavior logic for Drones, Dispatcher, Infrastructure, the Mesa Model, and Solara visualization configuration.
    

**4. Installation & Setup**

1. Clone the repository and navigate to the directory.
    
2. Create and activate a virtual environment (`python -m venv venv`).
    
3. Install dependencies using `pip install -r requirements.txt`.
    
4. Set up Environment Variables: Ensure you have your OpenTopography API key for map generation. Create a `.env` file in the root directory with `OPENTOPOGRAPHY_KEY=your_api_key_here`.
    

**5. Usage** The project offers multiple interfaces for the demo:

- **Option A: Generate a Custom Simulation Map (Streamlit)** Use the interactive map to select a Bounding Box in Morocco and generate the grid constraints. Run `streamlit run app.py`.
    
- **Option B: Full Voice-to-Drone Global Demo (Gradio + Mesa)** Launch the unified demo where you can speak in Darija and watch the order inject into the running Mesa simulation. Run `python demo.py`.
    
- **Option C: Pygame Real-Time Visualizer** Recommended for watching smooth drone pathfinding, obstacle avoidance, and mechanical failure recoveries. Run `python pygame/visualizer.py`.
    

**Team** EL MAHRAOUI Amal, SALIH El Mehdi, AKCHOUCH Abdelhakim, AIT EL MOUDEN Khaoula.