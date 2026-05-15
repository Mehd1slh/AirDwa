"""
Multi-Robot Delivery Coordination System
Master IPS - M2 Project (2025-2026)
Realised By : EL MAHRAOUI Amal  - SALIH El Mehdi

This package contains the agent logic, environment model, and visualization server 
for simulating a warehouse environment with multiple coordination mechanisms.
"""

# Expose key classes for easier imports
from .model import WarehouseModel
from .agents import RobotAgent, OrderManagerAgent

# Define what gets imported when someone runs 'from src import *'
__all__ = ["WarehouseModel", "RobotAgent", "OrderManagerAgent"]