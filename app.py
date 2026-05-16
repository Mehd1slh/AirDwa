import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import os
import json
import math
from dotenv import load_dotenv

load_dotenv()
from automated_map_builder import AutomatedMapBuilder

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

st.title("🚁 AirDwa: Custom Simulation Map Generator")

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
            grid_w, grid_h = math.ceil(width_meters / 30.0), math.ceil(height_meters / 30.0)
            
            if grid_w > 2000 or grid_h > 2000:
                st.error("🚨 Box exceeds max size (60x60km)!")
            elif not api_key:
                st.error("Missing OpenTopography API Key.")
            else:
                with st.spinner("Crunching OSM & Elevation Data..."):
                    builder = AutomatedMapBuilder(bbox=bbox, width=grid_w, height=grid_h, drone_alt_limit=drone_alt_limit, api_key=api_key)
                    builder.fetch_osm_data()
                    builder.fetch_elevation_data()
                    
                    # Store generated data in Session State and advance to Phase 2
                    st.session_state.map_data = builder.data
                    st.session_state.builder_params = {"bbox": bbox, "width": grid_w, "height": grid_h}
                    st.session_state.phase = 2
                    st.rerun() # Instantly refreshes the page to show the editor
        else:
            st.warning("Draw a bounding box first.")

# ==========================================
# PHASE 2: REVIEW & EDIT (MAP EDITOR)
# ==========================================
elif st.session_state.phase == 2:
    st.markdown("### Phase 2: Review & Edit Map")
    st.info("🔎 **Map Editor:** Use the **Marker Tool** (📍 on the left of the map) to click and add missed Douars, Bases, or Pharmacies. Your pins will automatically convert to grid coordinates.")

    params = st.session_state.builder_params
    bbox, grid_w, grid_h = params["bbox"], params["width"], params["height"]
    south, west, north, east = bbox
    
    col1, col2 = st.columns([2, 1])

    with col1:
        # Center the map on the selected area
        m2 = folium.Map(location=[(south + north) / 2, (west + east) / 2], zoom_start=12)
        
        # Draw the mission boundary
        folium.Rectangle(bounds=[[south, west], [north, east]], color="#ff7800", fill=False, weight=2).add_to(m2)
        
        # Render the detected grid points as colored dots
        # (We exclude obstacles here so the browser doesn't crash rendering 100k+ mountain points)
        colors = {"drone_bases": "red", "pharmacies": "green", "douars": "blue", "telecom_stations": "purple"}
        for category, color in colors.items():
            for pt in st.session_state.map_data[category]:
                lat, lon = grid_to_latlon(pt[0], pt[1], bbox, grid_w, grid_h)
                folium.CircleMarker(
                    location=[lat, lon], radius=5, color=color, fill=True, fill_opacity=0.9,
                    tooltip=f"{category.title()} (Grid: {pt[0]}, {pt[1]})"
                ).add_to(m2)
        
        # Add the single "Pin Drop" tool
        Draw(
            export=False, position='topleft',
            draw_options={'marker': True, 'rectangle': False, 'polyline': False, 'polygon': False, 'circle': False, 'circlemarker': False},
            edit_options={'edit': False}
        ).add_to(m2)
        
        # Capture interactions
        map_review = st_folium(m2, height=600, width=700, key="phase2_map")

    with col2:
        st.subheader("Add Missing Element")
        
        # Check if the user dropped a pin
        if map_review.get("all_drawings") and len(map_review["all_drawings"]) > 0:
            last_drawing = map_review["all_drawings"][-1]
            if last_drawing["geometry"]["type"] == "Point":
                draw_lon, draw_lat = last_drawing["geometry"]["coordinates"]
                
                # Convert the GPS pin back to the Simulation Grid Matrix
                x_ratio = (draw_lon - west) / (east - west)
                y_ratio = (draw_lat - south) / (north - south)
                grid_x = max(0, min(grid_w - 1, int(x_ratio * grid_w)))
                grid_y = max(0, min(grid_h - 1, int((1 - y_ratio) * grid_h)))
                
                st.markdown(f"**Coordinates:**\nLat: `{draw_lat:.4f}` | Lon: `{draw_lon:.4f}`\n\n**Grid Array Target:** `[{grid_x}, {grid_y}]`")
                
                with st.form("add_point_form"):
                    cell_type = st.selectbox("Assign Category:", ["douars", "drone_bases", "pharmacies", "telecom_stations"])
                    
                    if st.form_submit_button("➕ Add to Matrix"):
                        if [grid_x, grid_y] not in st.session_state.map_data[cell_type]:
                            st.session_state.map_data[cell_type].append([grid_x, grid_y])
                            # Rerun forces the map to reload, wiping the temporary pin and drawing a permanent colored circle
                            st.rerun() 
                        else:
                            st.warning("Point already exists.")
        else:
            st.info("Drop a marker (📍) on the map to add a missing location.")
            
        st.divider()
        st.subheader("Export System")
        json_str = json.dumps(st.session_state.map_data, indent=4)
        st.download_button(
            label="💾 Download map.json",
            data=json_str,
            file_name="custom_airdwa_map.json",
            mime="application/json",
            type="primary"
        )
        
        if st.button("🔄 Discard & Start Over"):
            st.session_state.phase = 1
            st.session_state.map_data = None
            st.rerun()