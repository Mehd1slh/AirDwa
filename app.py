import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import os
import json
import math
from dotenv import load_dotenv

load_dotenv()
from map_build.automated_map_builder import AutomatedMapBuilder

# --- GEOGRAPHIC MATH HELPERS ---
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Helper to convert grid coordinates back to Lat/Lon for visualization
def grid_to_latlon(x, y, bbox, grid_w, grid_h):
    south, west, north, east = bbox
    lon = west + (x / grid_w) * (east - west)
    # Y is inverted (0 is top/north)
    lat = north - (y / grid_h) * (north - south)
    return lat, lon

# --- UI SETUP & STATE MANAGEMENT ---
st.set_page_config(page_title="AirDwa Map Builder", layout="wide")

# Initialize Session State to handle the transition between Generation and Review
if "phase" not in st.session_state:
    st.session_state.phase = 1
if "map_data" not in st.session_state:
    st.session_state.map_data = None
if "builder_params" not in st.session_state:
    st.session_state.builder_params = None

st.title("AirDwa: Custom Simulation Map Generator")

# ==========================================
# PHASE 1: SELECTION & GENERATION
# ==========================================
if st.session_state.phase == 1:
    st.markdown("### Phase 1: Define Mission Area")
    st.markdown("Draw a bounding box. Max limit: 60x60km (2000x2000 grid).")

    col1, col2 = st.columns([2, 1])

    with col1:
        m = folium.Map(location=[31.13, -7.95], zoom_start=10)
        Draw(
            export=False, position='topleft',
            draw_options={'rectangle': True, 'polyline': False, 'polygon': False, 'circle': False, 'marker': False, 'circlemarker': False},
            edit_options={'edit': False}
        ).add_to(m)
        map_data = st_folium(m, height=500, width=700, key="phase1_map")

    with col2:
        with st.form("map_params_form"):
            drone_alt_limit = st.number_input("Drone Altitude Limit (m)", min_value=1000, max_value=6000, value=2500)
            env_api_key = os.getenv("OPENTOPOGRAPHY_KEY", "")
            api_key = st.text_input("OpenTopography API Key", value=env_api_key, type="password")
            submitted = st.form_submit_button("Generate Initial Grid")

    if submitted:
        if map_data.get("all_drawings") and len(map_data["all_drawings"]) > 0:
            geom = map_data["all_drawings"][-1]["geometry"]["coordinates"][0]
            lons, lats = [pt[0] for pt in geom], [pt[1] for pt in geom]
            bbox = (min(lats), min(lons), max(lats), max(lons))
            
            width_meters = haversine_distance(bbox[0], bbox[1], bbox[0], bbox[3])
            height_meters = haversine_distance(bbox[0], bbox[1], bbox[2], bbox[1])
            grid_w, grid_h = math.ceil(width_meters / 100.0), math.ceil(height_meters / 100.0)
            
            if grid_w > 2000 or grid_h > 2000:
                st.error("Box exceeds max size (60x60km)!")
            elif not api_key:
                st.error("Missing OpenTopography API Key.")
            else:
                with st.spinner("Crunching OSM & Elevation Data..."):
                    builder = AutomatedMapBuilder(bbox=bbox, width=grid_w, height=grid_h, drone_alt_limit=drone_alt_limit, api_key=api_key)
                    builder.fetch_osm_data()
                    builder.fetch_elevation_data()
                    
                    st.session_state.map_data = builder.data
                    st.session_state.builder_params = {"bbox": bbox, "width": grid_w, "height": grid_h}
                    st.session_state.phase = 2
                    st.rerun() 
        else:
            st.warning("Draw a bounding box first.")

# ==========================================
# PHASE 2: REVIEW & EDIT (MAP EDITOR)
# ==========================================
elif st.session_state.phase == 2:
    st.markdown("### Phase 2: Review & Edit Map")
    st.info("🔎 **Map Editor:** Use the **Marker** (📍) for single points, or the **Polygon/Circle Tools** (⬟ / ⭕) to select large zones (like mountain chains).")

    params = st.session_state.builder_params
    bbox, grid_w, grid_h = params["bbox"], params["width"], params["height"]
    south, west, north, east = bbox
    
    col1, col2 = st.columns([2, 1])

    with col1:
        m2 = folium.Map(location=[(south + north) / 2, (west + east) / 2], zoom_start=12)
        folium.Rectangle(bounds=[[south, west], [north, east]], color="#ff7800", fill=False, weight=2).add_to(m2)
        
        colors = {"drone_bases": "red", "pharmacies": "green", "douars": "blue", "telecom_stations": "purple"}
        
        for category, color in colors.items():
            for pt in st.session_state.map_data.get(category, []):
                lat, lon = grid_to_latlon(pt[0], pt[1], bbox, grid_w, grid_h)
                folium.CircleMarker(
                    location=[lat, lon], 
                    radius=8, # High visibility
                    color=color, 
                    fill=True, 
                    fill_opacity=0.9,
                    weight=2
                ).add_to(m2)
        
        Draw(
            export=False, position='topleft',
            draw_options={'marker': True, 'rectangle': True, 'polyline': False, 'polygon': True, 'circle': True, 'circlemarker': False},
            edit_options={'edit': False}
        ).add_to(m2)
        
        map_review = st_folium(m2, height=600, width=700, key="phase2_map")

    with col2:
        st.subheader("Add Missing Element")
        
        if map_review.get("all_drawings") and len(map_review["all_drawings"]) > 0:
            last_drawing = map_review["all_drawings"][-1]
            geom = last_drawing["geometry"]
            props = last_drawing.get("properties", {})
            
            new_grid_points = []
            display_text = ""
            
            if geom["type"] == "Point":
                draw_lon, draw_lat = geom["coordinates"]
                
                # Check if it's the Circle tool
                if "radius" in props:
                    radius_m = props["radius"]
                    display_text = f"**Circle Tool:** Radius `{radius_m:.1f}m`\n\n"
                    
                    lat_deg_dist = radius_m / 111000.0
                    lon_deg_dist = radius_m / (111000.0 * math.cos(math.radians(draw_lat)))
                    
                    min_lon, max_lon = draw_lon - lon_deg_dist, draw_lon + lon_deg_dist
                    min_lat, max_lat = draw_lat - lat_deg_dist, draw_lat + lat_deg_dist
                    
                    min_x = max(0, int((min_lon - west) / (east - west) * grid_w))
                    max_x = min(grid_w - 1, int((max_lon - west) / (east - west) * grid_w))
                    min_y = max(0, int((north - max_lat) / (north - south) * grid_h))
                    max_y = min(grid_h - 1, int((north - min_lat) / (north - south) * grid_h))
                    
                    for gx in range(min_x, max_x + 1):
                        for gy in range(min_y, max_y + 1):
                            glat, glon = grid_to_latlon(gx, gy, bbox, grid_w, grid_h)
                            if haversine_distance(glat, glon, draw_lat, draw_lon) <= radius_m:
                                new_grid_points.append([gx, gy])
                                
                    display_text += f"**Grid Cells Selected:** `{len(new_grid_points)}`"
                else:
                    # Single Marker
                    x_ratio = (draw_lon - west) / (east - west)
                    y_ratio = (draw_lat - south) / (north - south)
                    grid_x = max(0, min(grid_w - 1, int(x_ratio * grid_w)))
                    grid_y = max(0, min(grid_h - 1, int((1 - y_ratio) * grid_h)))
                    new_grid_points.append([grid_x, grid_y])
                    display_text = f"**Coordinates:**\nLat: `{draw_lat:.4f}` | Lon: `{draw_lon:.4f}`\n\n**Grid Target:** `[{grid_x}, {grid_y}]`"
                    
            elif geom["type"] == "Polygon":
                poly_coords = geom["coordinates"][0]
                display_text = f"**Polygon/Rectangle Tool:** `{len(poly_coords)}` vertices\n\n"
                
                lons = [pt[0] for pt in poly_coords]
                lats = [pt[1] for pt in poly_coords]
                min_lon, max_lon = min(lons), max(lons)
                min_lat, max_lat = min(lats), max(lats)
                
                min_x = max(0, int((min_lon - west) / (east - west) * grid_w))
                max_x = min(grid_w - 1, int((max_lon - west) / (east - west) * grid_w))
                min_y = max(0, int((north - max_lat) / (north - south) * grid_h))
                max_y = min(grid_h - 1, int((north - min_lat) / (north - south) * grid_h))
                
                # Ray Casting to detect internal grid points
                def point_in_polygon(x, y, poly):
                    n = len(poly)
                    inside = False
                    p1x, p1y = poly[0]
                    for i in range(1, n + 1):
                        p2x, p2y = poly[i % n]
                        if y > min(p1y, p2y):
                            if y <= max(p1y, p2y):
                                if x <= max(p1x, p2x):
                                    if p1y != p2y:
                                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                                        if p1x == p2x or x <= xints:
                                            inside = not inside
                        p1x, p1y = p2x, p2y
                    return inside

                for gx in range(min_x, max_x + 1):
                    for gy in range(min_y, max_y + 1):
                        glat, glon = grid_to_latlon(gx, gy, bbox, grid_w, grid_h)
                        if point_in_polygon(glon, glat, poly_coords):
                            new_grid_points.append([gx, gy])
                            
                display_text += f"**Grid Cells Selected:** `{len(new_grid_points)}`"
            
            st.markdown(display_text)
            
            if new_grid_points:
                with st.form("add_point_form"):
                    category_map = {
                        "⚕️ Health Facility (Hospital/Pharmacy)": "pharmacies",
                        "🏠 Douar (Delivery Target)": "douars",
                        "⚡ Charging Station (Telecom Tower)": "telecom_stations",
                        "⛰️ Obstacle (Mountain/No-Fly)": "obstacles"
                    }
                    ui_choice = st.selectbox("Assign Category:", list(category_map.keys()))
                    cell_type = category_map[ui_choice]
                    
                    if st.form_submit_button(f"➕ Add {len(new_grid_points)} Cell(s) to Matrix"):
                        added_count = 0
                        for pt in new_grid_points:
                            if pt not in st.session_state.map_data[cell_type]:
                                st.session_state.map_data[cell_type].append(pt)
                                added_count += 1
                        
                        if added_count > 0:
                            st.rerun() 
                        else:
                            st.warning("Points already exist.")
        else:
            st.info("Drop a marker (📍) or draw a shape (⬟) on the map to select zones.")
            
        st.divider()
        st.subheader("Export System")
        json_str = json.dumps(st.session_state.map_data, indent=4)
        
        st.download_button(
            label="Download map.json to computer",
            data=json_str,
            file_name="custom_airdwa_map.json",
            mime="application/json",
            type="primary"
        )
        
        if st.button("Save as 'Last Saved Map' for Visualizer"):
            os.makedirs("maps", exist_ok=True)
            with open("maps/custom_airdwa.json", "w") as f:
                json.dump(st.session_state.map_data, f, indent=4)
            st.success("✅ Map saved to maps/custom_airdwa.json!")
        
        if st.button("🔄 Discard & Start Over"):
            st.session_state.phase = 1
            st.session_state.map_data = None
            st.rerun()