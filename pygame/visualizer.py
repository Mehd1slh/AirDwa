import pygame
import sys
import os
import json

# Add src to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from src.model import AirDwaModel
from src.agents import DroneAgent, HealthFacilityAgent, DouarAgent, ChargingStationAgent, ObstacleAgent

# Map Editor Constants aligned with model.py
TILE_TYPES = ["HealthFacility", "Douar", "ChargingStation", "Obstacle", "Empty"]
TILE_COLORS = {
    "HealthFacility": (46, 204, 113),  # Green
    "Douar": (52, 152, 219),           # Blue
    "ChargingStation": (241, 196, 15), # Yellow/Orange
    "Obstacle": (128, 128, 128),       # Gray
    "Empty": (236, 240, 241)
}

# --- CONFIGURATION ---
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 900 
SIDEBAR_WIDTH = 300
FPS = 60

# State Constants
STATE_MENU = "MENU"
STATE_EDITOR = "EDITOR"
STATE_SIMULATION = "SIMULATION"

# Colors
COLOR_BG = (255, 255, 255)
COLOR_GRID = (230, 230, 230)
COLOR_SIDEBAR = (40, 44, 52)
COLOR_BUTTON = (70, 130, 180)
COLOR_BUTTON_HOVER = (100, 149, 237)
COLOR_BUTTON_EDIT = (60, 179, 113) 
COLOR_BUTTON_ERROR = (200, 60, 60)
COLOR_BUTTON_ERROR_HOVER = (230, 90, 90)
COLOR_TEXT_WHITE = (255, 255, 255)
COLOR_TEXT_BLACK = (0, 0, 0)
COLOR_SLIDER_BG = (100, 100, 100)
COLOR_SLIDER_HANDLE = (200, 200, 200)

# --- MAP EDITOR CLASS ---
class MapEditor:
    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height
        self.grid = [["Empty" for _ in range(height)] for _ in range(width)]
        self.current_selection = "HealthFacility"
        self.cell_size = 100
        
    def handle_click(self, pos, offset_x, offset_y, right_click=False):
        grid_x = (pos[0] - offset_x) // self.cell_size
        grid_y = (pos[1] - offset_y) // self.cell_size
        
        if 0 <= grid_x < self.width and 0 <= grid_y < self.height:
            if right_click:
                self.grid[grid_x][grid_y] = "Empty"
            else:
                if self.grid[grid_x][grid_y] == self.current_selection:
                    self.grid[grid_x][grid_y] = "Empty"
                else:
                    self.grid[grid_x][grid_y] = self.current_selection
    
    def resize_grid(self, new_width, new_height):
        new_grid = [["Empty" for _ in range(new_height)] for _ in range(new_width)]
        for x in range(min(self.width, new_width)):
            for y in range(min(self.height, new_height)):
                new_grid[x][y] = self.grid[x][y]
        self.width = new_width
        self.height = new_height
        self.grid = new_grid

    def save_map(self, filename="custom_map.json"):
        data = {
            "width": self.width,
            "height": self.height,
            "pharmacies": [], 
            "douars": [],
            "telecom_stations": [], 
            "obstacles": []
        }
        for x in range(self.width):
            for y in range(self.height):
                tile = self.grid[x][y]
                if tile == "HealthFacility": 
                    data["pharmacies"].append([x, y])
                elif tile == "Douar": 
                    data["douars"].append([x, y])
                elif tile == "ChargingStation": 
                    data["telecom_stations"].append([x, y])
                elif tile == "Obstacle": 
                    data["obstacles"].append([x, y])
        
        os.makedirs("maps", exist_ok=True)
        filepath = f"maps/{filename}"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Map saved to {filepath}")
        return data

# --- UI COMPONENTS ---

class Button:
    def __init__(self, x, y, width, height, text, callback, param=None, color=COLOR_BUTTON, hover_color=COLOR_BUTTON_HOVER):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.param = param
        self.base_color = color
        self.hover_color = hover_color
        self.is_hovered = False

    def draw(self, screen, font):
        color = self.hover_color if self.is_hovered else self.base_color
        pygame.draw.rect(screen, color, self.rect, border_radius=5)
        text_surf = font.render(self.text, True, COLOR_TEXT_WHITE)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def check_hover(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered:
                if self.param is not None: 
                    self.callback(self.param)
                else: 
                    self.callback()

class Slider:
    def __init__(self, x, y, width, min_val, max_val, initial, label):
        self.rect = pygame.Rect(x, y, width, 20)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial
        self.label = label
        self.dragging = False
        
    def draw(self, screen, font):
        label_surf = font.render(f"{self.label}: {self.value}", True, COLOR_TEXT_WHITE)
        screen.blit(label_surf, (self.rect.x, self.rect.y - 25))
        pygame.draw.rect(screen, COLOR_SLIDER_BG, self.rect, border_radius=5)
        handle_x = self.rect.x + (self.value - self.min_val) / (self.max_val - self.min_val) * self.rect.width
        handle_rect = pygame.Rect(handle_x - 10, self.rect.y - 5, 20, 30)
        pygame.draw.rect(screen, COLOR_SLIDER_HANDLE, handle_rect, border_radius=5)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            handle_x = self.rect.x + (self.value - self.min_val) / (self.max_val - self.min_val) * self.rect.width
            handle_rect = pygame.Rect(handle_x - 10, self.rect.y - 5, 20, 30)
            if handle_rect.collidepoint(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = event.pos[0] - self.rect.x
            ratio = max(0, min(1, rel_x / self.rect.width))
            self.value = int(self.min_val + ratio * (self.max_val - self.min_val))
            return True
        return False

# --- MAIN VISUALIZER ---

class AirDwaVisualizer:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("AirDwa: Autonomous Swarm Rescue Simulation")
        self.clock = pygame.time.Clock()
        
        self.font_main = pygame.font.SysFont("Arial", 42, bold=True)
        self.font_title = pygame.font.SysFont("Arial", 24, bold=True)
        self.font_ui = pygame.font.SysFont("Arial", 16)
        self.font_tiny = pygame.font.SysFont("Arial", 12, bold=True)
        
        self.state = STATE_MENU
        self.map_editor = MapEditor(20, 20)
        self.active_map_data = None
        self.model = None
        self.smooth_positions = {}
        self.paused = True
        self.needs_step = True
        
        self.n_robots = 5
        self.animation_speed = 0.15
        self.grid_width = 20
        self.grid_height = 20

        self.init_ui()
        self.update_layout(WINDOW_WIDTH, WINDOW_HEIGHT)

    def init_ui(self):
        mid_x = WINDOW_WIDTH // 2
        
        # Menu Buttons
        self.btn_new_map = Button(mid_x - 150, 400, 300, 60, "Create Custom Map", self.enter_editor)
        self.btn_default_map = Button(mid_x - 150, 480, 300, 60, "Use Default Layout", self.start_with_default)
        self.btn_load_saved = Button(mid_x - 150, 560, 300, 60, "Load Last Saved Map", self.load_saved_map)
        self.menu_buttons = [self.btn_new_map, self.btn_default_map, self.btn_load_saved]

        # Simulation Sidebar
        self.btn_back = Button(0, 0, 250, 40, "Return to Menu", self.return_to_menu, color=(100,100,100))
        self.btn_pause = Button(0, 0, 120, 40, "Pause/Play", self.toggle_pause)
        self.btn_reset = Button(0, 0, 120, 40, "Reset", self.reset_sim)
        self.btn_slower = Button(0, 0, 120, 40, "Slower", self.decrease_speed)
        self.btn_faster = Button(0, 0, 120, 40, "Faster", self.increase_speed)
        self.btn_fail = Button(0, 0, 250, 40, "FAIL RANDOM DRONE", self.trigger_fail, 
                               color=COLOR_BUTTON_ERROR, hover_color=COLOR_BUTTON_ERROR_HOVER)
        self.slider_robots = Slider(0, 0, 250, 1, 10, self.n_robots, "Drones")
        self.sim_buttons = [self.btn_back, self.btn_pause, self.btn_reset, 
                           self.btn_slower, self.btn_faster, self.btn_fail]

        # Editor Sidebar
        self.btn_editor_back = Button(0, 0, 250, 40, "Return to Menu", self.return_to_menu, color=(100,100,100))
        self.slider_width = Slider(0, 0, 250, 10, 100, self.grid_width, "Width")
        self.slider_height = Slider(0, 0, 250, 10, 100, self.grid_height, "Height")
        
        # Row 1
        self.btn_sel_health = Button(0, 0, 80, 40, "Health", self.set_tile, "HealthFacility", color=TILE_COLORS["HealthFacility"])
        self.btn_sel_douar = Button(0, 0, 80, 40, "Douar", self.set_tile, "Douar", color=TILE_COLORS["Douar"])
        self.btn_sel_charge = Button(0, 0, 80, 40, "Charge", self.set_tile, "ChargingStation", color=TILE_COLORS["ChargingStation"])
        
        # Row 2
        self.btn_sel_obs = Button(0, 0, 120, 40, "Obstacle", self.set_tile, "Obstacle", color=TILE_COLORS["Obstacle"])
        self.btn_clear_map = Button(0, 0, 120, 40, "Clear All", self.clear_map, color=(150, 50, 50))
        
        self.btn_launch = Button(0, 0, 250, 40, "Save and Launch", self.save_and_launch, color=COLOR_BUTTON_EDIT)
        self.editor_buttons = [self.btn_editor_back, self.btn_sel_health, self.btn_sel_douar, self.btn_sel_charge, 
                              self.btn_sel_obs, self.btn_clear_map, self.btn_launch]

    def update_layout(self, w, h):
        self.window_w, self.window_h = w, h
        mid_x = w // 2
        bx = w - SIDEBAR_WIDTH + 25
        
        self.btn_new_map.rect.topleft = (mid_x - 150, 400)
        self.btn_default_map.rect.topleft = (mid_x - 150, 480)
        self.btn_load_saved.rect.topleft = (mid_x - 150, 560)
        
        self.btn_back.rect.topleft = (bx, 100)
        self.slider_robots.rect.topleft = (bx, 220)
        self.btn_pause.rect.topleft = (bx, 280)
        self.btn_reset.rect.topleft = (bx + 130, 280)
        self.btn_slower.rect.topleft = (bx, 330)
        self.btn_faster.rect.topleft = (bx + 130, 330)
        self.btn_fail.rect.topleft = (bx, 390)
        
        self.btn_editor_back.rect.topleft = (bx, 140)
        self.slider_width.rect.topleft = (bx, 200)
        self.slider_height.rect.topleft = (bx, 260)
        
        self.btn_sel_health.rect.topleft = (bx, 330)
        self.btn_sel_douar.rect.topleft = (bx + 85, 330)
        self.btn_sel_charge.rect.topleft = (bx + 170, 330)
        
        self.btn_sel_obs.rect.topleft = (bx, 380)
        self.btn_clear_map.rect.topleft = (bx + 130, 380)
        
        self.btn_launch.rect.topleft = (bx, 440)

        if self.state == STATE_MENU:
            return
            
        if self.state == STATE_SIMULATION and self.model:
            grid_w = self.model.grid.width
            grid_h = self.model.grid.height
        else:
            grid_w = self.map_editor.width
            grid_h = self.map_editor.height
            
        available_width = w - (SIDEBAR_WIDTH if self.state != STATE_MENU else 0)
        
        scale_x = available_width // grid_w
        scale_y = h // grid_h
        self.cell_size = min(scale_x, scale_y)
        if self.cell_size < 1: self.cell_size = 1
        
        grid_pixel_width = self.cell_size * grid_w
        grid_pixel_height = self.cell_size * grid_h
        
        self.offset_x = (available_width - grid_pixel_width) // 2
        self.offset_y = (h - grid_pixel_height) // 2
        self.map_editor.cell_size = self.cell_size

    def reset_sim(self): self.launch_simulation()
    def enter_editor(self): 
        self.state = STATE_EDITOR
        self.update_layout(self.window_w, self.window_h)
    def return_to_menu(self): 
        self.state = STATE_MENU
        self.paused = True
        self.update_layout(self.window_w, self.window_h)
    def toggle_pause(self): self.paused = not self.paused
    def set_tile(self, ttype): self.map_editor.current_selection = ttype
    def clear_map(self):
        w = self.map_editor.width
        h = self.map_editor.height
        self.map_editor.grid = [["Empty" for _ in range(h)] for _ in range(w)]
    def decrease_speed(self): self.animation_speed = max(0.01, self.animation_speed - 0.05)
    def increase_speed(self): self.animation_speed = min(1.0, self.animation_speed + 0.05)
    def start_with_default(self):
        # Point directly to your custom map file
        path = "maps/custom_airdwa0.json"
        with open(path, "r") as f: 
            self.active_map_data = json.load(f)
        self.launch_simulation()

    def load_saved_map(self):
        path = "maps/custom_airdwa.json"
        if os.path.exists(path):
            with open(path, "r") as f: 
                self.active_map_data = json.load(f)
            print(f"✅ Loaded map from {path}")
            self.launch_simulation()
        else:
            print(f"❌ No saved map found at {path}")

    def save_and_launch(self):
        self.active_map_data = self.map_editor.save_map("custom_airdwa.json")
        self.launch_simulation()

    def launch_simulation(self):
        self.n_robots = self.slider_robots.value
        self.model = AirDwaModel(
            n_robots=self.n_robots, 
            map_data=self.active_map_data
        )
        self.smooth_positions = {}
        self.state = STATE_SIMULATION
        self.paused = False
        self.needs_step = True
        self.update_layout(self.window_w, self.window_h)

    def trigger_fail(self):
        if self.model: self.model.fail_random_robot()

    def draw_grid_lines(self):
        if self.cell_size < 4: return
        
        if self.state == STATE_SIMULATION and self.model:
            grid_w = self.model.grid.width
            grid_h = self.model.grid.height
        else:
            grid_w = self.map_editor.width
            grid_h = self.map_editor.height
        
        gw_pixels = grid_w * self.cell_size
        gh_pixels = grid_h * self.cell_size
        
        for x in range(grid_w + 1):
            px = self.offset_x + x * self.cell_size
            pygame.draw.line(self.screen, COLOR_GRID, (px, self.offset_y), (px, self.offset_y + gh_pixels))
            
        for y in range(grid_h + 1):
            py = self.offset_y + y * self.cell_size
            pygame.draw.line(self.screen, COLOR_GRID, (self.offset_x, py), (self.offset_x + gw_pixels, py))

    def draw_menu(self):
        self.screen.fill(COLOR_SIDEBAR)
        title = self.font_main.render("Smart AirDwa Control", True, COLOR_TEXT_WHITE)
        self.screen.blit(title, title.get_rect(center=(self.window_w // 2, 250)))
        subtitle = self.font_ui.render("Choose your simulation mode:", True, (200, 200, 200))
        self.screen.blit(subtitle, subtitle.get_rect(center=(self.window_w // 2, 330)))
        for b in self.menu_buttons: b.draw(self.screen, self.font_ui)

    def draw_editor(self):
        self.screen.fill(COLOR_BG)
        self.draw_grid_lines()
        
        render_size = max(16, self.cell_size) # Fixed UI Size
        
        for x in range(self.map_editor.width):
            for y in range(self.map_editor.height):
                tile = self.map_editor.grid[x][y]
                if tile != "Empty":
                    if tile == "Obstacle":
                        rect = (self.offset_x + x*self.cell_size, self.offset_y + y*self.cell_size, self.cell_size, self.cell_size)
                        pygame.draw.rect(self.screen, TILE_COLORS[tile], rect)
                        if self.cell_size > 4:
                            pygame.draw.rect(self.screen, (100, 100, 100), rect, 1)
                    else:
                        cx = self.offset_x + x * self.cell_size + self.cell_size / 2
                        cy = self.offset_y + y * self.cell_size + self.cell_size / 2
                        rect = (cx - render_size/2, cy - render_size/2, render_size, render_size)
                        pygame.draw.rect(self.screen, TILE_COLORS[tile], rect)
                        pygame.draw.rect(self.screen, (50, 50, 50), rect, 2)
        
        sidebar_rect = pygame.Rect(self.window_w - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, self.window_h)
        pygame.draw.rect(self.screen, COLOR_SIDEBAR, sidebar_rect)
        
        title = self.font_title.render("Map Designer", True, COLOR_TEXT_WHITE)
        self.screen.blit(title, (self.window_w - SIDEBAR_WIDTH + 25, 40))
        sel_surf = self.font_ui.render(f"Selected: {self.map_editor.current_selection}", True, COLOR_TEXT_WHITE)
        self.screen.blit(sel_surf, (self.window_w - SIDEBAR_WIDTH + 25, 90))
        size_surf = self.font_ui.render(f"Grid: {self.map_editor.width}x{self.map_editor.height}", True, (200, 200, 200))
        self.screen.blit(size_surf, (self.window_w - SIDEBAR_WIDTH + 25, 115))
        
        self.slider_width.draw(self.screen, self.font_ui)
        self.slider_height.draw(self.screen, self.font_ui)
        
        for b in self.editor_buttons: b.draw(self.screen, self.font_ui)

    def draw_simulation(self):
        self.screen.fill(COLOR_BG)
        self.draw_grid_lines()

        render_size = max(16, self.cell_size)  # Keep key spots visible
        drone_radius = max(8, int(self.cell_size/2.5)) # Keep drones visible

        # Draw static agents
        for x in range(self.model.grid.width):
            for y in range(self.model.grid.height):
                cell_contents = self.model.grid.get_cell_list_contents((x, y))
                
                cx = self.offset_x + x * self.cell_size + self.cell_size / 2
                cy = self.offset_y + y * self.cell_size + self.cell_size / 2
                fixed_rect = (cx - render_size/2, cy - render_size/2, render_size, render_size)
                
                for agent in cell_contents:
                    agent_type = type(agent).__name__
                    
                    if agent_type == "HealthFacilityAgent":
                        pygame.draw.rect(self.screen, TILE_COLORS["HealthFacility"], fixed_rect)
                        pygame.draw.rect(self.screen, (30, 150, 80), fixed_rect, max(1, int(render_size/8)))
                    elif agent_type == "DouarAgent":
                        pygame.draw.rect(self.screen, TILE_COLORS["Douar"], fixed_rect)
                        pygame.draw.rect(self.screen, (40, 120, 180), fixed_rect, max(1, int(render_size/8)))
                    elif agent_type == "ChargingStationAgent":
                        pygame.draw.rect(self.screen, TILE_COLORS["ChargingStation"], fixed_rect)
                        pygame.draw.rect(self.screen, (200, 150, 10), fixed_rect, max(1, int(render_size/8)))
                    elif agent_type == "ObstacleAgent": 
                        obs_rect = (self.offset_x + x*self.cell_size, self.offset_y + y*self.cell_size, self.cell_size, self.cell_size)
                        pygame.draw.rect(self.screen, TILE_COLORS["Obstacle"], obs_rect)
                        if self.cell_size > 4: pygame.draw.rect(self.screen, (100, 100, 100), obs_rect, 1)

        # Draw medical supply weights
        for mission in self.model.order_manager.missions:
            show_weight = False
            if mission.assigned_to is None:
                show_weight = True
            elif hasattr(mission.assigned_to, 'state') and mission.assigned_to.state == "TO_PICKUP":
                show_weight = True
            
            if show_weight:
                ox, oy = mission.pickup_pos
                px = int(self.offset_x + ox * self.cell_size + self.cell_size/2)
                py = int(self.offset_y + oy * self.cell_size + self.cell_size/2)
                
                w_surf = self.font_tiny.render(str(mission.priority), True, COLOR_TEXT_WHITE)
                w_rect = w_surf.get_rect(center=(px, py))
                bg_rect = w_rect.inflate(4, 4)
                pygame.draw.rect(self.screen, (0, 0, 0, 150), bg_rect, border_radius=2)
                self.screen.blit(w_surf, w_rect)

        # Draw drones with smooth animation
        for agent in self.model.drone_agents:
            if agent.unique_id not in self.smooth_positions:
                self.smooth_positions[agent.unique_id] = list(agent.pos)
            
            sx, sy = self.smooth_positions[agent.unique_id]
            tx, ty = agent.pos
            
            dx, dy = tx - sx, ty - sy
            if abs(dx) < 0.01 and abs(dy) < 0.01:
                self.smooth_positions[agent.unique_id] = [tx, ty]
            else:
                self.smooth_positions[agent.unique_id][0] += dx * self.animation_speed
                self.smooth_positions[agent.unique_id][1] += dy * self.animation_speed
            
            px = int(self.offset_x + self.smooth_positions[agent.unique_id][0] * self.cell_size + self.cell_size/2)
            py = int(self.offset_y + self.smooth_positions[agent.unique_id][1] * self.cell_size + self.cell_size/2)
            
            col = (100, 100, 100)
            if agent.state == "FAILED": col = (255, 0, 0)
            elif agent.battery < 20: col = (255, 255, 0)
            elif agent.state == "TO_DELIVER": col = (0, 200, 0)
            elif agent.state == "TO_PICKUP": col = (0, 0, 255)
            elif agent.state == "CHARGING": col = (255, 165, 0)
            elif agent.state == "TO_CHARGE": col = (255, 140, 0)
            
            pygame.draw.circle(self.screen, col, (px, py), drone_radius)
            pygame.draw.circle(self.screen, (0,0,0), (px, py), drone_radius, 1)
            
            bar_w = drone_radius * 2
            bar_h = 4
            fill = (agent.battery/100) * bar_w
            pygame.draw.rect(self.screen, (50, 50, 50), (px-bar_w//2, py-drone_radius-6, bar_w, bar_h))
            pygame.draw.rect(self.screen, (0, 255, 0), (px-bar_w//2, py-drone_radius-6, fill, bar_h))

        # Sidebar
        sidebar_rect = pygame.Rect(self.window_w - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, self.window_h)
        pygame.draw.rect(self.screen, COLOR_SIDEBAR, sidebar_rect)
        
        title = self.font_title.render("Control Center", True, COLOR_TEXT_WHITE)
        self.screen.blit(title, (self.window_w - SIDEBAR_WIDTH + 20, 20))
        
        status = "PAUSED" if self.paused else "RUNNING"
        col = (255, 100, 100) if self.paused else (100, 255, 100)
        status_surf = self.font_ui.render(f"Status: {status}", True, col)
        self.screen.blit(status_surf, (self.window_w - SIDEBAR_WIDTH + 25, 60))
        
        for b in self.sim_buttons: b.draw(self.screen, self.font_ui)
        self.slider_robots.draw(self.screen, self.font_ui)
        
        stats_y = 470
        active_robots = len([r for r in self.model.drone_agents if r.state not in ['IDLE', 'FAILED']])
        failed_robots = len([r for r in self.model.drone_agents if r.state == 'FAILED'])
        
        stats = [
            f"Speed: {int(self.animation_speed * 100)}%",
            f"Missions Done: {self.model.order_manager.completed_orders}",
            f"Active Drones: {active_robots}",
            f"Failed Drones: {failed_robots}"
        ]
        for line in stats:
            surf = self.font_ui.render(line, True, COLOR_TEXT_WHITE)
            self.screen.blit(surf, (self.window_w - SIDEBAR_WIDTH + 25, stats_y))
            stats_y += 30

    def update_robot_positions(self):
        all_arrived = True
        for agent in self.model.drone_agents:
            tx, ty = agent.pos
            if agent.unique_id not in self.smooth_positions:
                self.smooth_positions[agent.unique_id] = [tx, ty]
            
            cx, cy = self.smooth_positions[agent.unique_id]
            dx, dy = tx - cx, ty - cy
            
            if abs(dx) > 0.01 or abs(dy) > 0.01:
                all_arrived = False
        return all_arrived

    def run(self):
        running = True
        while running:
            mpos = pygame.mouse.get_pos()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT: 
                    running = False
                    
                if event.type == pygame.VIDEORESIZE: 
                    self.update_layout(event.w, event.h)
                
                if self.state == STATE_MENU:
                    for b in self.menu_buttons: b.handle_event(event)
                        
                elif self.state == STATE_EDITOR:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        self.map_editor.handle_click(mpos, self.offset_x, self.offset_y, event.button == 3)
                    for b in self.editor_buttons: b.handle_event(event)
                    if self.slider_width.handle_event(event):
                        if self.grid_width != self.slider_width.value:
                            self.grid_width = self.slider_width.value
                            self.map_editor.resize_grid(self.grid_width, self.grid_height)
                            self.update_layout(self.window_w, self.window_h)
                    if self.slider_height.handle_event(event):
                        if self.grid_height != self.slider_height.value:
                            self.grid_height = self.slider_height.value
                            self.map_editor.resize_grid(self.grid_width, self.grid_height)
                            self.update_layout(self.window_w, self.window_h)
                        
                elif self.state == STATE_SIMULATION:
                    for b in self.sim_buttons: b.handle_event(event)
                    if self.slider_robots.handle_event(event):
                        if self.n_robots != self.slider_robots.value:
                            self.n_robots = self.slider_robots.value
                            self.reset_sim()

            if self.state == STATE_MENU:
                for b in self.menu_buttons: b.check_hover(mpos)
            elif self.state == STATE_EDITOR:
                for b in self.editor_buttons: b.check_hover(mpos)
            elif self.state == STATE_SIMULATION:
                for b in self.sim_buttons: b.check_hover(mpos)

            if self.state == STATE_SIMULATION and not self.paused:
                if self.needs_step:
                    self.model.step()
                    self.needs_step = False
                if self.update_robot_positions():
                    self.needs_step = True

            if self.state == STATE_MENU: self.draw_menu()
            elif self.state == STATE_EDITOR: self.draw_editor()
            elif self.state == STATE_SIMULATION: self.draw_simulation()
            
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
        
if __name__ == "__main__":
    viz = AirDwaVisualizer()
    viz.run()