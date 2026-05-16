import pygame
import json
import os

# --- Configuration Constants ---

# Available tile types that can be placed in the airdwa grid
TILE_TYPES = ["HealthFacility", "Douar", "ChargingStation", "Empty"]

COLORS = {
    "HealthFacility": (139, 69, 19),      
    "Douar": (0, 0, 0),                   
    "ChargingStation": (255, 140, 0),     
    "Empty": (200, 200, 200)              
}

class MapEditor:
    """
    Handles the logical state of the custom map builder, 
    translating mouse clicks into grid data.
    """
    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height
        # Initialize the grid as a 2D array filled with "Empty" tiles
        self.grid = [[ "Empty" for _ in range(height)] for _ in range(width)]
        # Default tile type to place on left-click
        self.current_selection = "Pharmacy"
        # Pixel size of each cell for coordinate translation
        self.cell_size = 30
        
    def handle_click(self, pos, offset_x, offset_y, right_click=False):
        """
        Converts screen mouse coordinates into grid indices and updates the tile type.
        """
        # Calculate which grid cell was clicked based on current zoom/offset
        grid_x = (pos[0] - offset_x) // self.cell_size
        grid_y = (pos[1] - offset_y) // self.cell_size
        
        # Ensure the click is within the actual grid boundaries
        if 0 <= grid_x < self.width and 0 <= grid_y < self.height:
            if right_click:
                # Right-click acts as an eraser
                self.grid[grid_x][grid_y] = "Empty"
            else:
                # Left-click places the currently selected tile type
                self.grid[grid_x][grid_y] = self.current_selection

    def save_map(self, filename="custom_map.json"):
        """
        Exports the grid layout to a JSON format that the AirDwaModel can parse.
        """
        # Dictionary structure to store coordinates of each object type
        data = {
            "width": self.width,
            "height": self.height,
            "pharmacies": [],
            "douars": [],
            "drone_bases": []
        }

        # Iterate through the grid and collect coordinates for each agent type
        for x in range(self.width):
            for y in range(self.height):
                tile = self.grid[x][y]
                if tile == "Pharmacy": 
                    data["pharmacies"].append([x, y])
                elif tile == "Douar": 
                    data["douars"].append([x, y])
                elif tile == "DroneBase": 
                    data["drone_bases"].append([x, y])
        
        # Ensure the 'maps' directory exists before saving
        os.makedirs("maps", exist_ok=True)
        
        # Write the data to a JSON file
        with open(f"maps/{filename}", "w") as f:
            json.dump(data, f)
            
        print(f"Map saved to maps/{filename}")