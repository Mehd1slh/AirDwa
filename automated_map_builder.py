import requests
import json
import os
import osmnx as ox
import rasterio

OPENTOPOGRAPHY_KEY = os.getenv("OPENTOPOGRAPHY_KEY")

class AutomatedMapBuilder:
    def __init__(self, bbox, width=50, height=50, drone_alt_limit=2500, api_key=OPENTOPOGRAPHY_KEY):
        """
        bbox format: (south, west, north, east)
        """
        self.south, self.west, self.north, self.east = bbox
        self.width = width
        self.height = height
        self.drone_alt_limit = drone_alt_limit
        self.api_key = api_key
        
        # Expanding the JSON format to include new features
        self.data = {
            "width": width,
            "height": height,
            "pharmacies": [],
            "douars": [],
            "drone_bases": [],
            "telecom_stations": [], # New: Charging stations
            "obstacles": []         # New: High altitude mountains
        }
    
    def latlon_to_grid(self, lat, lon):
        # Translate geographic coordinates to 2D Array indices (x, y)
        x_ratio = (lon - self.west) / (self.east - self.west)
        y_ratio = (lat - self.south) / (self.north - self.south)
        
        x = int(x_ratio * self.width)
        # Assuming origin (0,0) is top-left
        y = int((1 - y_ratio) * self.height) 
        
        # Clamp bounds
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))
        return x, y

    def fetch_osm_data(self):
        print("🌍 Fetching OSM Data (Douars, Hospitals, Telecoms)...")
        bbox_ox = (self.north, self.south, self.east, self.west)
        
        # 1. Hospitals and Pharmacies
        try:
            health_pois = ox.features_from_bbox(*bbox_ox, tags={'amenity': ['hospital', 'pharmacy', 'clinic']})
            for idx, row in health_pois.iterrows():
                point = row.geometry.centroid
                x, y = self.latlon_to_grid(point.y, point.x)
                if row.get('amenity') == 'hospital':
                    self.data["drone_bases"].append([x, y])
                else:
                    self.data["pharmacies"].append([x, y])
        except Exception:
            print("No hospitals/pharmacies found in this area.")

        # 2. Douars (Villages & Hamlets)
        try:
            villages = ox.features_from_bbox(*bbox_ox, tags={'place': ['village', 'hamlet', 'isolated_dwelling']})
            for idx, row in villages.iterrows():
                point = row.geometry.centroid
                x, y = self.latlon_to_grid(point.y, point.x)
                self.data["douars"].append([x, y])
        except Exception:
            print("No douars found in this area.")
            
        # 3. Telecom Towers
        try:
            towers = ox.features_from_bbox(*bbox_ox, tags={'telecom': ['tower', 'antenna'], 'man_made': ['mast']})
            for idx, row in towers.iterrows():
                point = row.geometry.centroid
                x, y = self.latlon_to_grid(point.y, point.x)
                self.data["telecom_stations"].append([x, y])
        except Exception:
            print("No telecom stations found.")

    def fetch_elevation_data(self):
        print("⛰️ Fetching Topography Data from OpenTopography...")
        url = "https://portal.opentopography.org/API/globaldem"
        params = {
            'demtype': 'COP30', # Copernicus 30m resolution 
            'south': self.south, 'north': self.north,
            'west': self.west, 'east': self.east,
            'outputFormat': 'GTiff',
            'API_Key': self.api_key
        }
        
        tif_filename = "temp_elevation.tif"
        response = requests.get(url, params=params, stream=True)
        
        if response.status_code == 200:
            with open(tif_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Processing altitudes against Drone Limits...")
            self.process_elevation(tif_filename)
            os.remove(tif_filename)
        else:
            print("Failed to fetch topography data. Check API key.")

    def process_elevation(self, tif_filename):
        # Open the GeoTIFF and map altitudes to our grid
        with rasterio.open(tif_filename) as src:
            points = []
            grid_coords = []
            
            lat_step = (self.north - self.south) / self.height
            lon_step = (self.east - self.west) / self.width
            
            for y in range(self.height):
                for x in range(self.width):
                    # Find center coordinate of the grid cell
                    lon = self.west + (x + 0.5) * lon_step
                    lat = self.north - (y + 0.5) * lat_step
                    points.append((lon, lat))
                    grid_coords.append((x, y))
                    
            # Sample all points at once from the DEM
            elevations = list(src.sample(points))
            
            for i, elev in enumerate(elevations):
                val = elev[0] # The altitude in meters
                if val > self.drone_alt_limit:
                    gx, gy = grid_coords[i]
                    self.data["obstacles"].append([gx, gy])

    def generate(self, filename="automated_map.json"):
        self.fetch_osm_data()
        self.fetch_elevation_data()
        
        # Clean up duplicates in case nodes mapped to the same grid cell
        for key in self.data.keys():
            if isinstance(self.data[key], list):
                self.data[key] = [list(x) for x in set(tuple(x) for x in self.data[key])]

        os.makedirs("maps", exist_ok=True)
        filepath = os.path.join("maps", filename)
        with open(filepath, "w") as f:
            json.dump(self.data, f, indent=4)
        print(f"✅ Map successfully saved to {filepath}!")

# --- TO RUN IT ---
if __name__ == "__main__":
    # Example: BBox around the Toubkal region
    builder = AutomatedMapBuilder(
        bbox=(31.0, -8.0, 31.2, -7.8), 
        width=40, 
        height=40, 
        drone_alt_limit=2800, # Mark any cell > 2800m as an obstacle
        api_key=OPENTOPOGRAPHY_KEY
    )
    builder.generate("toubkal_map.json")