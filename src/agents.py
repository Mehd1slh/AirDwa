import mesa
import random
import heapq
import math

# --- Global Constants ---

# Battery Management
BATTERY_CAPACITY = 100
BATTERY_DRAIN_MOVE = 1       # Cost per step moved
BATTERY_DRAIN_IDLE = 0.1     # Cost per step while doing nothing
CHARGE_RATE = 100            # Amount recovered per step at a station
LOW_BATTERY_THRESHOLD = 40   # Point at which a drone prioritizes charging
RECOVERY_TIME = 25           # Steps a drone stays in 'FAILED' state before repair

# Drone States for Finite State Machine (FSM)
# Drone States for Finite State Machine (FSM)
STATE_IDLE = "IDLE"
STATE_TO_PICKUP = "TO_PICKUP"
STATE_TO_DELIVER = "TO_DELIVER"
STATE_CHARGING = "CHARGING"
STATE_TO_CHARGE = "TO_CHARGE"
STATE_FAILED = "FAILED"
STATE_RETURNING = "RETURNING"

# Physical Constraints
MIN_PACKAGE_PRIORITY = 1
MAX_PACKAGE_PRIORITY = 3
DRONE_SPEEDS = [1, 2, 3]

MEDICINE_DB = {
    # ── Routine (Priority 1) ──────────────────────────────────────────────────
    "doliprane": 1,        # Darija/French trade name for paracetamol
    "paracetamol": 1,      # English/international name
    "paracétamol": 1,      # French spelling
    "dalidol": 1,          # Common Moroccan brand
    "antibiotic": 1,       # Generic English term
    "antibiotique": 1,     # French/Darija term
    "amoxicillin": 1,      # Common antibiotic
    "amoxicilline": 1,     # French spelling
    "augmentin": 1,        # Brand name antibiotic common in Morocco
    "antalgique": 1,       # Darija/French: pain reliever
    "aspirine": 1,         # Aspirin (French spelling, common in Darija)
    "aspirin": 1,
    "vitamines": 1,        # Vitamins
    "vitamin": 1,
    "comprime": 1,         # Generic tablet/pill reference
    "antiparasitaire": 1,  # Antiparasitic

    # ── Urgent (Priority 2) ───────────────────────────────────────────────────
    "insulin": 2,          # English
    "insuline": 2,         # French/Darija
    "inhaler": 2,          # English
    "inhalateur": 2,       # French
    "pompe": 2,            # Darija: literally "pump" (asthma inhaler)
    "ventoline": 2,        # Brand-name inhaler common in Morocco
    "salbutamol": 2,       # Generic name for Ventolin
    "antihypertenseur": 2, # Blood pressure medication
    "antihypertensive": 2,
    "cardioaspirin": 2,    # Cardiac aspirin
    "diazepam": 2,         # Sedative
    "metformin": 2,        # Diabetes medication
    "metformine": 2,

    # ── Critical (Priority 3) ─────────────────────────────────────────────────
    "blood": 3,            # Blood / blood product
    "sang": 3,             # French/Darija for blood
    "plasma": 3,           # Blood plasma
    "antivenom": 3,        # Snake/scorpion antivenom
    "antivenin": 3,        # French variant
    "serum": 3,            # Antivenom serum (common Darija shorthand)
    "epipen": 3,           # Epinephrine auto-injector
    "epinephrine": 3,      # Generic name
    "adrenaline": 3,       # Alternative name (common in French-speaking contexts)
    "adrénaline": 3,       # French spelling
    "morphine": 3,         # Strong painkiller / post-trauma
    "naloxone": 3,         # Opioid overdose reversal
    "defibrillateur": 3,   # Defibrillator pads/gel (emergency)
    "glucagon": 3,         # Severe hypoglycemia kit
}


class Mission:
    """ Represents a delivery task from a pickup location (Pharmacy) to a dropoff location (Douar). """
    def __init__(self, order_id, pickup_pos, dropoff_pos, priority, medicine_name=None):
        self.order_id = order_id
        self.priority = priority
        self.pickup_pos = pickup_pos
        self.dropoff_pos = dropoff_pos
        self.medicine_name = medicine_name  # Set for voice-dispatched orders; None for auto-generated
        self.assigned_to = None 

class DroneAgent(mesa.Agent):
    def __init__(self, unique_id, model, start_pos):
        super().__init__(model) 
        self.custom_id = unique_id
        self.pos = None
        self.battery = BATTERY_CAPACITY
        self.state = STATE_IDLE
        self.previous_state = None
        self.current_order = None
        self.orders_completed = 0
        self.distance_traveled = 0
        self.failure_timer = 0
        self.repairs_triggered = 0
        
        # REPLACED capacity with speed
        self.speed = random.choice(DRONE_SPEEDS)

    def step(self):
        """ Main logic loop executed at every simulation tick. """
        # Handle mechanical failure cooldown
        if self.state == STATE_FAILED:
            self.failure_timer -= 1
            if self.failure_timer <= 0:
                print(f"✅ Drone {self.unique_id} RECOVERED! Back to work.")
                self.state = STATE_IDLE
                self.battery = BATTERY_CAPACITY
            return

        self.update_battery()
        
        # Immediate failure if battery hits zero
        if self.battery <= 0 and self.state != STATE_FAILED:
            self.trigger_failure()
            return
        
        # Proactive charging: move to charger if battery is low, but remember what we were doing
        if self.battery < LOW_BATTERY_THRESHOLD and self.state not in [STATE_CHARGING, STATE_TO_CHARGE, STATE_FAILED]:
            if self.previous_state is None:
                self.previous_state = self.state if self.state in [STATE_TO_PICKUP, STATE_TO_DELIVER] else STATE_IDLE
            self.state = STATE_TO_CHARGE
            print(f"🟫 Drone {self.unique_id} charging. Holding Mission ID: {self.current_order.order_id if self.current_order else 'None'}")
                
        # --- State Machine Logic ---
        if self.state == STATE_TO_PICKUP:
            if self.current_order:
                target = self.current_order.pickup_pos # Go directly to the coordinates
                self.move_towards(target)
                if self.pos == target:
                    self.state = STATE_TO_DELIVER
                    print(f"📦 Drone {self.unique_id} picked up mission {self.current_order.order_id}")

        elif self.state == STATE_TO_DELIVER:
            if self.current_order:
                target = self.current_order.dropoff_pos 
                self.move_towards(target)
                if self.pos == target:
                    self.complete_order() # complete_order will now trigger RTB

        # --- NEW: Return to Base Protocol ---
        elif self.state == STATE_RETURNING:
            target = self.get_nearest_health_facility()
            self.move_towards(target)
            if self.pos == target:
                self.state = STATE_IDLE # Safe to idle at a hospital

        elif self.state == STATE_TO_CHARGE:
            target = self.get_nearest_charger()
            self.move_towards(target)
            if self.pos == target:
                self.state = STATE_CHARGING

        elif self.state == STATE_CHARGING:
            self.charge()
            if self.battery == BATTERY_CAPACITY:
                # PIT STOP RULE: Resume what it was doing, or go back to base
                if hasattr(self, 'previous_state') and self.previous_state:
                    self.state = self.previous_state
                    self.previous_state = None
                else:
                    self.state = STATE_RETURNING
            

    def trigger_failure(self):
        """ Simulates a breakdown, requiring a re-assignment of any current tasks. """
        print(f"💥 Drone {self.unique_id} FAILED at {self.pos}! State was: {self.state}")
        old_state = self.state
        self.state = STATE_FAILED
        self.failure_timer = RECOVERY_TIME
        self.repairs_triggered += 1
        if self.current_order:
            self.model.order_manager.handle_robot_failure(self, old_state)
    
        
        # Resume the task being held before the drone went to charge
        if hasattr(self, 'previous_state') and self.previous_state:
            self.state = self.previous_state
            self.previous_state = None
        else:
            self.state = STATE_IDLE

    def complete_order(self):
        """ Finalizes the delivery task and triggers Return to Base. """
        if self.current_order:
            print(f"✅ Drone {self.unique_id} completed mission {self.current_order.order_id}")
            self.model.order_manager.report_completion(self.current_order)
            
        self.current_order = None
        self.state = STATE_RETURNING # Do not idle at the Douar!
        self.orders_completed += 1

    def get_nearest_charger(self):
        """ Identifies the closest available charging station (telecom tower). """
        chargers = self.model.charging_stations
        if not chargers: return self.pos
        return min(chargers, key=lambda c: self.euclidean_distance(self.pos, c))
    
    def get_nearest_health_facility(self):
        facilities = self.model.health_facilities
        if not facilities: return self.pos
        return min(facilities, key=lambda f: self.euclidean_distance(self.pos, f))

    def move_towards(self, target_pos):
        """ Executes steps toward a goal based on the drone's speed. """
        for _ in range(self.speed):
            if self.pos == target_pos: 
                break # Reached destination
                
            path = self.a_star_search(self.pos, target_pos)
            if path and len(path) > 0:
                next_step = path[0] 
                if self.model.is_walkable(next_step):
                    self.model.grid.move_agent(self, next_step)
                    self.distance_traveled += 1
                    self.battery -= BATTERY_DRAIN_MOVE
                else:
                    break

    def a_star_search(self, start, goal):
        """ Classic A* implementation to find the shortest path while avoiding obstacles. """
        frontier = []
        heapq.heappush(frontier, (0, start))
        came_from = {start: None}
        cost_so_far = {start: 0}
        found_goal = False

        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                found_goal = True
                break

            for next_pos in self.get_neighbors(current):
                # Calculate the exact cost to step to the next node (1 for straight, ~1.414 for diagonal)
                step_cost = self.euclidean_distance(current, next_pos)
                new_cost = cost_so_far[current] + step_cost 
                
                if not self.model.is_walkable(next_pos): continue
                if next_pos not in cost_so_far or new_cost < cost_so_far[next_pos]:
                    cost_so_far[next_pos] = new_cost
                    priority = new_cost + self.euclidean_distance(next_pos, goal)
                    heapq.heappush(frontier, (priority, next_pos))
                    came_from[next_pos] = current
        
        if found_goal: return self.reconstruct_path(came_from, start, goal)
        return []

    def get_neighbors(self, pos):
        """ Returns all 8 adjacent cells (Moore neighborhood). """
        x, y = pos
        candidates = [
            (x+1, y), (x-1, y), (x, y+1), (x, y-1),        # orthogonal
            (x+1, y+1), (x+1, y-1), (x-1, y+1), (x-1, y-1) # diagonals
        ]
        valid_neighbors = []
        for (cx, cy) in candidates:
            if not self.model.grid.out_of_bounds((cx, cy)):
                valid_neighbors.append((cx, cy))
        return valid_neighbors

    def reconstruct_path(self, came_from, start, goal):
        """ Trace back from goal to start to generate the movement list. """
        current = goal
        path = []
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse() 
        return path

    def euclidean_distance(self, pos1, pos2):
        """ Euclidean heuristic for grid-based distance including diagonals. """
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def charge(self):
        """ Increases battery level until capacity is reached. """
        self.battery = min(self.battery + CHARGE_RATE, BATTERY_CAPACITY)

    def update_battery(self):
        """ Passive battery drain while the drone is active or waiting. """
        if self.state == STATE_IDLE: 
            self.battery -= BATTERY_DRAIN_IDLE



    def calculate_auction_bid(self, mission):
        """ Bid for the Auction mechanism (lower is better, represents 'cost'). """
        if self.current_order is not None:
            return float('inf')
        if self.state != STATE_IDLE or self.battery < LOW_BATTERY_THRESHOLD:
            return float('inf')
        
        dist = self.calculate_distance(mission.pickup_pos)
        
        # Faster drones will have a lower time_cost
        time_cost = dist / self.speed 
        
        # Multiply priority by speed to give fast drones a massive bidding advantage on urgent tasks
        priority_bonus = mission.priority * self.speed 
        
        return time_cost + ((BATTERY_CAPACITY - self.battery) * 0.1) - priority_bonus

    def calculate_distance(self, target):
        return self.euclidean_distance(self.pos, target)

class MissionControlAgent(mesa.Agent):
    """ The central 'dispatcher' responsible for mission creation and task allocation. """
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.missions = []
        self.completed_orders = 0
        self.next_order_id = 0

    def step(self):
        """ Generates new tasks and initiates the global allocation process. """
        if random.random() < self.model.order_rate: 
            self.create_new_order()
            
        unassigned = self.get_unassigned_orders()
        if not unassigned: 
            return
            
        # Dispatch using the sole allowed protocol: Auction
        self.run_auction_allocation(unassigned)

    def handle_robot_failure(self, failed_robot, old_state):
        """ Patient-First Rescue Logic: Abandon the crashed supply and order a fresh one. """
        mission = failed_robot.current_order
        if not mission:
            return
        
        if old_state == "TO_PICKUP":
            # The drone broke before securing the package. Put the mission back in the pool.
            mission.assigned_to = None
            print(f"🔄 Drone {failed_robot.unique_id} failed before pickup. Mission {mission.order_id} re-released.")
            
        elif old_state in ["TO_DELIVER", "TO_CHARGE"]:
            # The drone broke while carrying the medical supply.
            print(f"🚨 CRASH DETECTED! Drone {failed_robot.unique_id} crashed at {failed_robot.pos}")
            print(f"⚠️ Abandoning original package for mission {mission.order_id}. Initiating Patient-First Protocol...")
            
            # Find the nearest health facility to the PATIENT
            nearest_facility = min(
                self.model.health_facilities, 
                key=lambda p: abs(p[0] - mission.dropoff_pos[0]) + abs(p[1] - mission.dropoff_pos[1])
            )
            
            # Re-route the mission to pick up fresh supplies
            mission.pickup_pos = nearest_facility
            mission.assigned_to = None
            
            if not str(mission.order_id).startswith("URGENT_RESCUE_"):
                mission.order_id = f"URGENT_RESCUE_{mission.order_id}"
                
            print(f"🏥 Fresh supply ordered from Health Facility at {nearest_facility} for patient at {mission.dropoff_pos}")

        failed_robot.current_order = None
        
        # Instantly run the auction to dispatch a fresh drone
        unassigned = [mission]
        self.run_auction_allocation(unassigned)

    def create_new_order(self):
        """ Spawns a mission at a random pharmacy with a target packing station. """
        pickup = self.model.get_random_health_facility()
        dropoff = self.model.get_random_packing_station()
        if pickup and dropoff:
            priority = random.randint(MIN_PACKAGE_PRIORITY, MAX_PACKAGE_PRIORITY)
            new_order = Mission(self.next_order_id, pickup, dropoff, priority)
            self.next_order_id += 1
            self.missions.append(new_order)

    def run_auction_allocation(self, unassigned_orders):
        """ Allocates tasks by awarding them to the agent with the lowest cost. """
        idle_robots = [a for a in self.model.schedule.agents 
                      if isinstance(a, DroneAgent) and a.state == STATE_IDLE]
        if not idle_robots: 
            return
            
        for mission in unassigned_orders:
            if not idle_robots:
                break
                
            bids = {r: r.calculate_auction_bid(mission) for r in idle_robots}
            valid_bids = {r: c for r, c in bids.items() if c != float('inf')}
            
            if valid_bids:
                winner = min(valid_bids, key=valid_bids.get)
                if self.assign_order_specifically(winner, mission):
                    print(f"💰 Auction: Drone {winner.unique_id} won mission {mission.order_id}")
                    idle_robots.remove(winner)

    def assign_order_specifically(self, drone, mission):
        """ Links the drone and mission together. """
        if mission.assigned_to is None:
            mission.assigned_to = drone
            drone.current_order = mission
            drone.state = STATE_TO_PICKUP
            return True
        return False

    def get_unassigned_orders(self): 
        return [o for o in self.missions if o.assigned_to is None]
    
    def report_completion(self, mission): 
        self.completed_orders += 1
        if mission in self.missions:
            self.missions.remove(mission)

    def create_specific_order(self, medicine_name, station_id):
        """ Explicitly triggers an order from the Voice Assistant / ASR """
        # Normalize medicine name to find priority
        med_key = str(medicine_name).lower()
        priority = MEDICINE_DB.get(med_key, 1) # Default to 1 if unknown
        
        # Find the target Douar coordinates by its Station ID
        dropoff_pos = self.model.get_douar_by_station_id(station_id)
        pickup_pos = self.model.get_random_health_facility()
        
        if pickup_pos and dropoff_pos:
            new_order = Mission(self.next_order_id, pickup_pos, dropoff_pos, priority, medicine_name=medicine_name)
            self.next_order_id += 1
            self.missions.append(new_order)
            print(f"🎙️ VOICE COMMAND ACCEPTED: Dispatching {medicine_name} (Priority {priority}) to Station {station_id}")
            
            # Immediately run auction to dispatch
            self.run_auction_allocation([new_order])
            return True
        else:
            print(f"❌ Error: Station {station_id} not found in environment!")
            return False

# --- Passive Environmental Agents ---

class HealthFacilityAgent(mesa.Agent):
    """ Represents merged Hospitals and Pharmacies. """
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.type_name = "HealthFacility"
        self.color = "#2ECC71" # Green

class ChargingStationAgent(mesa.Agent):
    """ Telecom towers serving as mid-flight pit stops. """
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.type_name = "ChargingStation"
        self.color = "#F1C40F" # Yellow


class DouarAgent(mesa.Agent):
    """ Represents the target destination for goods. Non-walkable. """
    def __init__(self, unique_id, model, station_id):
        super().__init__(model)
        self.type_name = "Douar"
        self.color = "#3498DB"
        self.station_id = str(station_id)


class ObstacleAgent(mesa.Agent):
    """ Represents hard terrain (e.g., mountains, cliffs). Non-walkable. """
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.type_name = "Obstacle"
        self.color = "#808080"