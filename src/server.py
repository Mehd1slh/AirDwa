import sys
import os
import solara

# Ensure the script can import local modules from the current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mesa
from mesa.visualization import SolaraViz, make_space_component, make_plot_component

# Local Imports: Environment agents and state constants for visualization
from model import AirDwaModel
from agents import (
    DroneAgent, 
    STATE_TO_DELIVER, 
    STATE_TO_PICKUP, 
    STATE_CHARGING, 
    STATE_TO_CHARGE, 
    LOW_BATTERY_THRESHOLD
)


# --- VISUALIZATION LOGIC ---

def agent_portrayal(agent):
    """
    Determines how each agent (Drone, Pharmacy, Station) is rendered in the web UI.
    Returns a dictionary of visual properties.
    """
    if agent is None: return {}
    
    # Default: Circular marker for mobile agents
    portrayal = {"size": 50, "marker": "o"}

    if isinstance(agent, DroneAgent):
        # Priority 1: Visual feedback for critical failure (Mechanical breakdown)
        if agent.state == "FAILED": 
            portrayal["color"] = "red"
        
        # Priority 2: Visual alert for low battery (needs charging)
        elif agent.battery < LOW_BATTERY_THRESHOLD:
            portrayal["color"] = "yellow"
            
        # Standard States: Color-coded based on current task
        elif agent.state == STATE_TO_DELIVER:
            portrayal["color"] = "green"   # Carrying a medical supply
        elif agent.state == STATE_TO_PICKUP:
            portrayal["color"] = "blue"    # Moving to fetch a medical supply
        elif agent.state == STATE_CHARGING:
            portrayal["color"] = "yellow"  # Currently at a station
        elif agent.state == STATE_TO_CHARGE:
            portrayal["color"] = "orange"  # Heading to a station
        else:
            portrayal["color"] = "grey"    # Idle or undefined

    elif hasattr(agent, "type_name"):
        # Infrastructure: Rendered as larger squares
        portrayal["marker"] = "s" 
        portrayal["size"] = 80
        
        # Use custom highlighted colors from the model if available, else defaults
        if hasattr(agent, "color"):
            portrayal["color"] = agent.color
        else:
            if agent.type_name == "Pharmacy":
                portrayal["color"] = "#2ECC71"
            elif agent.type_name == "Douar":
                portrayal["color"] = "#3498DB"
            elif agent.type_name == "DroneBase":
                portrayal["color"] = "#F1C40F"
            elif agent.type_name == "Obstacle": # Added Obstacle Support
                portrayal["color"] = "#808080"

    return portrayal


# --- UI MODEL PARAMETERS ---

# Defines the sliders and dropdowns in the web sidebar to control simulation settings
model_params = {

    "n_robots": {
        "type": "SliderInt",
        "value": 3,
        "label": "Number of Drones",
        "min": 1,
        "max": 10,
        "step": 1,
    },
    "order_rate": {
        "type": "SliderFloat",
        "value": 0.1,
        "label": "Mission Rate (Prob/Step)",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
    }
}


# --- CUSTOM UI COMPONENTS ---

@solara.component
def ManualFaultControls(model):
    """
    Adds a custom section to the sidebar allowing the user to 
    manually inject a drone failure for testing resilience.
    """
    with solara.Sidebar(): 
        with solara.Card("Manual Fault Injection"):
            solara.Button(
                label="Fail Random Drone", 
                on_click=model.fail_random_robot, 
                color="error",
                style={"width": "100%"}
            )


# --- SERVER PAGE INITIALIZATION ---

# Create the initial model instance
initial_model = AirDwaModel(n_robots=3, order_rate=0.1)

# Assemble the Solara visualization page
page = SolaraViz(
    model=initial_model,
    components=[
        # 1. The 2D grid space view
        make_space_component(agent_portrayal),
        
        # 2. Custom sidebar button for manual failure
        ManualFaultControls,
        
        # 3. Real-time metric monitoring graphs (linked to DataCollector in model.py)
        make_plot_component({"Throughput": "black"}),      # Missions completed
        make_plot_component({"Total_Distance": "blue"}),   # Energy cost / effort
        make_plot_component({"Conflict_Rate": "red"}),     # Current failed drones
        make_plot_component({"Fairness_Gini": "purple"}),  # Workload distribution
    ],
    model_params=model_params,
    name="Multi-Drone Delivery System"
)