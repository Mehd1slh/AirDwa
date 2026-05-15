"""
AirDwa: Multi-Drone Delivery System Simulation
has been developed as a comprehensive simulation framework to model and analyze the behavior of multiple drones operating in a shared environment. The system incorporates various coordination mechanisms, including market-based approaches, contract net protocols, and centralized control strategies, to manage task allocation and execution among the drones.

Realised By : EL MAHRAOUI Amal  - SALIH El Mehdi - AKCHOUCH Abdelhakim - AIT EL MOUDEN Khaoula
"""

# Expose key classes for easier imports
from .model import AirDwaModel
from .agents import DroneAgent, MissionControlAgent

# Define what gets imported when someone runs 'from src import *'
__all__ = ["AirDwaModel", "DroneAgent", "MissionControlAgent"]