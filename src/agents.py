import mesa
import random
import heapq

# --- Global Constants ---

# Battery Management
BATTERY_CAPACITY = 100
BATTERY_DRAIN_MOVE = 1       # Cost per step moved
BATTERY_DRAIN_IDLE = 0.1     # Cost per step while doing nothing
CHARGE_RATE = 100            # Amount recovered per step at a station
LOW_BATTERY_THRESHOLD = 25   # Point at which a drone prioritizes charging
RECOVERY_TIME = 40           # Steps a drone stays in 'FAILED' state before repair

# Drone States for Finite State Machine (FSM)
STATE_IDLE = "IDLE"
STATE_TO_PICKUP = "TO_PICKUP"
STATE_TO_DELIVER = "TO_DELIVER"
STATE_CHARGING = "CHARGING"
STATE_TO_CHARGE = "TO_CHARGE"
STATE_FAILED = "FAILED"

# Physical Constraints
ROBOT_CAPACITIES = [20, 30, 40]
MIN_PACKAGE_WEIGHT = 5
MAX_PACKAGE_WEIGHT = 40

# Colors used to highlight pharmacies/stations associated with active missions
VISUALIZATION_COLORS = [
    "#00FFFF", "#FF00FF", "#FF1493", "#32CD32", "#008080", 
    "#000080", "#800000", "#808000", "#FFD700", "#4B0082"
]

class Mission:
    """ Represents a delivery task from a pickup location (Pharmacy) to a dropoff location (Douar). """
    def __init__(self, order_id, pickup_pos, dropoff_pos, weight):
        self.order_id = order_id
        self.weight = weight
        self.pickup_pos = pickup_pos
        self.dropoff_pos = dropoff_pos
        self.assigned_to = None # Reference to the DroneAgent handling the mission

class DroneAgent(mesa.Agent):
    """ The primary autonomous agent capable of moving, picking up missions, and managing battery levels. """
    def __init__(self, unique_id, model, start_pos):
        super().__init__(model) 
        self.custom_id = unique_id
        self.pos = None
        self.battery = BATTERY_CAPACITY
        self.state = STATE_IDLE
        self.previous_state = None  # Stores state before charging to resume task later
        self.current_order = None
        self.orders_completed = 0
        self.distance_traveled = 0
        self.failure_timer = 0
        self.repairs_triggered = 0
        self.capacity = random.choice(ROBOT_CAPACITIES) # Randomized drone strength

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
                target_access = self.get_access_point(self.current_order.pickup_pos)
                if target_access:
                    self.move_towards(target_access)
                    if self.pos == target_access:
                        self.reset_shelf_color(self.current_order.pickup_pos)
                        self.state = STATE_TO_DELIVER
                        print(f"📦 Drone {self.unique_id} picked up mission {self.current_order.order_id}")

        elif self.state == STATE_TO_DELIVER:
            if self.current_order:
                target_access = self.get_access_point(self.current_order.dropoff_pos)
                if target_access:
                    self.move_towards(target_access)
                    if self.pos == target_access:
                        self.complete_order()
            else:
                self.state = STATE_IDLE

        elif self.state == STATE_TO_CHARGE:
            target = self.get_nearest_charger()
            self.move_towards(target)
            if self.pos == target:
                self.state = STATE_CHARGING

        elif self.state == STATE_CHARGING:
            self.charge()
            if self.battery == BATTERY_CAPACITY:
                self.vacate_station() # Clear the charger for other drones
            
        elif self.state == STATE_IDLE:
            # Under greedy coordination, drones seek their own tasks without a central manager
            if self.model.coordination_type == "greedy":
                self.behavior_greedy()

    def trigger_failure(self):
        """ Simulates a breakdown, requiring a re-assignment of any current tasks. """
        print(f"💥 Drone {self.unique_id} FAILED at {self.pos}! State was: {self.state}")
        old_state = self.state
        self.state = STATE_FAILED
        self.failure_timer = RECOVERY_TIME
        self.repairs_triggered += 1
        if self.current_order:
            self.model.order_manager.handle_robot_failure(self, old_state)
    
    def vacate_station(self):
        """ Unblocks a charging station by moving to a neighboring walkable cell. """
        neighbors = self.model.grid.get_neighborhood(self.pos, moore=False, include_center=False)
        moved = False
        
        for neighbor in neighbors:
            cell_contents = self.model.grid.get_cell_list_contents(neighbor)
            is_station = any(isinstance(c, DroneBaseAgent) for c in cell_contents)
            if not is_station and self.model.is_walkable(neighbor):
                self.model.grid.move_agent(self, neighbor)
                moved = True
                break
        
        # Resume the task being held before the drone went to charge
        if hasattr(self, 'previous_state') and self.previous_state:
            self.state = self.previous_state
            self.previous_state = None
        else:
            self.state = STATE_IDLE

    def reset_shelf_color(self, pos):
        """ Reverts a pharmacy to its default color once a medical supply is removed. """
        if self.model.grid.out_of_bounds(pos): return
        cell_contents = self.model.grid.get_cell_list_contents(pos)
        for agent in cell_contents:
            if isinstance(agent, PharmacyAgent):
                agent.color = "brown"

    def reset_station_color(self, pos):
        """ Reverts a packing station to black once the mission delivery is finished. """
        if self.model.grid.out_of_bounds(pos): return
        cell_contents = self.model.grid.get_cell_list_contents(pos)
        for agent in cell_contents:
            if isinstance(agent, DouarAgent):
                agent.color = "black"

    def complete_order(self):
        """ Finalizes the delivery task and resets drone state. """
        if self.current_order:
            print(f"✅ Drone {self.unique_id} completed mission {self.current_order.order_id}")
            self.reset_station_color(self.current_order.dropoff_pos)
            self.model.order_manager.report_completion(self.current_order)
            
        self.current_order = None
        self.state = STATE_IDLE
        self.orders_completed += 1

    def get_access_point(self, target_pos):
        """ Finds an adjacent walkable cell to a target (pharmacy/station) since targets are non-walkable. """
        x, y = target_pos
        potential_access_points = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
        
        if self.pos in potential_access_points:
            return self.pos

        valid_points = [p for p in potential_access_points if self.model.is_walkable(p)]
        if not valid_points: return None 
        return min(valid_points, key=lambda p: self.manhattan_distance(self.pos, p))

    def get_nearest_charger(self):
        """ Identifies the closest available charging station. """
        chargers = self.model.drone_bases
        if not chargers: return self.pos
        return min(chargers, key=lambda c: self.manhattan_distance(self.pos, c))

    def move_towards(self, target_pos):
        """ Executes a single step toward a goal using pathfinding. """
        if self.pos == target_pos: return
        path = self.a_star_search(self.pos, target_pos)
        if path and len(path) > 0:
            next_step = path[0] 
            if self.model.is_walkable(next_step):
                self.model.grid.move_agent(self, next_step)
                self.distance_traveled += 1
                self.battery -= BATTERY_DRAIN_MOVE

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
                new_cost = cost_so_far[current] + 1 
                if not self.model.is_walkable(next_pos): continue
                if next_pos not in cost_so_far or new_cost < cost_so_far[next_pos]:
                    cost_so_far[next_pos] = new_cost
                    priority = new_cost + self.manhattan_distance(next_pos, goal)
                    heapq.heappush(frontier, (priority, next_pos))
                    came_from[next_pos] = current
        
        if found_goal: return self.reconstruct_path(came_from, start, goal)
        return []

    def get_neighbors(self, pos):
        """ Returns orthogonal adjacent cells. """
        x, y = pos
        candidates = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
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

    def manhattan_distance(self, pos1, pos2):
        """ Simple heuristic for grid-based distance. """
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def charge(self):
        """ Increases battery level until capacity is reached. """
        self.battery = min(self.battery + CHARGE_RATE, BATTERY_CAPACITY)

    def update_battery(self):
        """ Passive battery drain while the drone is active or waiting. """
        if self.state == STATE_IDLE: 
            self.battery -= BATTERY_DRAIN_IDLE

    def behavior_greedy(self):
        """ Simple behavior: pick the nearest task that fits within carrying capacity. """
        available_orders = self.model.order_manager.get_unassigned_orders()
        if not available_orders: return
        feasible_orders = [o for o in available_orders if o.weight <= self.capacity]
        if not feasible_orders: return

        best_order = min(feasible_orders, key=lambda o: self.calculate_distance(o.pickup_pos))
        if self.model.order_manager.assign_order_specifically(self, best_order):
            self.current_order = best_order
            self.state = STATE_TO_PICKUP

    def calculate_cnp_bid(self, mission):
        """ Bid for the Contract Net Protocol based on distance, battery, and fitness. """
        if self.current_order is not None:
            return -1 # Already busy
        if self.state != STATE_IDLE or self.battery < LOW_BATTERY_THRESHOLD:
            return -1 # Not fit for work
        if mission.weight > self.capacity:
            return -1 # Task too heavy
        
        dist = self.calculate_distance(mission.pickup_pos)
        # Score calculation: High battery is good, high distance is bad
        base_score = (self.battery * 0.5) - (dist * 2.0)
        wasted_space = self.capacity - mission.weight
        penalty = wasted_space * 1.0 # Prefer drones whose capacity matches the weight
        
        return max(0, base_score - penalty)

    def calculate_auction_bid(self, mission):
        """ Bid for the Auction mechanism (lower is better, represents 'cost'). """
        if self.current_order is not None:
            return float('inf')
        if self.state != STATE_IDLE or self.battery < LOW_BATTERY_THRESHOLD:
            return float('inf')
        if mission.weight > self.capacity:
            return float('inf')
        
        dist = self.calculate_distance(mission.pickup_pos)
        wasted_space = self.capacity - mission.weight
        opportunity_cost = wasted_space * 1.0 # Penalize taking small items with large drones
        
        return dist + ((BATTERY_CAPACITY - self.battery) * 0.1) + opportunity_cost

    def calculate_distance(self, target):
        return self.manhattan_distance(self.pos, target)


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
            
        # Dispatch based on the model's global coordination setting
        if self.model.coordination_type == "cnp": 
            self.run_cnp_allocation(unassigned)
        elif self.model.coordination_type == "auction": 
            self.run_auction_allocation(unassigned)

    def handle_robot_failure(self, failed_robot, old_state):
        """ Rescue Logic: If a drone breaks, recover the medical supply and re-issue the task. """
        mission = failed_robot.current_order
        if not mission:
            return
        
        if old_state == "TO_PICKUP":
            # Just put it back in the pool
            mission.assigned_to = None
            print(f"🔄 Drone {failed_robot.unique_id} failed before pickup. Mission {mission.order_id} re-released.")
            
        elif old_state in ["TO_DELIVER", "TO_CHARGE"]:
            # Drop the medical supply where the drone died; it must be picked up from there now
            print(f"🚨 PACKAGE DROPPED! Drone {failed_robot.unique_id} dropped mission {mission.order_id} at {failed_robot.pos}")
            mission.pickup_pos = failed_robot.pos
            mission.assigned_to = None
            
            if not str(mission.order_id).startswith("RESCUE_"):
                mission.order_id = f"RESCUE_{mission.order_id}"

        failed_robot.current_order = None
        
        # Immediate attempt to find a healthy drone to finish the job
        if self.model.coordination_type in ["cnp", "auction"]:
            unassigned = [mission]
            if self.model.coordination_type == "cnp":
                self.run_cnp_allocation(unassigned)
            elif self.model.coordination_type == "auction":
                self.run_auction_allocation(unassigned)

    def create_new_order(self):
        """ Spawns an mission at a random pharmacy with a target packing station. """
        pickup = self.model.get_random_shelf()
        dropoff = self.model.get_random_packing_station()
        if pickup and dropoff:
            weight = random.randint(MIN_PACKAGE_WEIGHT, MAX_PACKAGE_WEIGHT)
            new_order = Mission(self.next_order_id, pickup, dropoff, weight)
            self.next_order_id += 1
            self.missions.append(new_order)
            
            # Change colors of the pharmacy and station so we can see which task is linked
            highlight_color = random.choice(VISUALIZATION_COLORS)
            cell_contents_pickup = self.model.grid.get_cell_list_contents(pickup)
            for agent in cell_contents_pickup:
                if isinstance(agent, PharmacyAgent): 
                    agent.color = highlight_color
            cell_contents_dropoff = self.model.grid.get_cell_list_contents(dropoff)
            for agent in cell_contents_dropoff:
                if isinstance(agent, DouarAgent): 
                    agent.color = highlight_color

    def run_cnp_allocation(self, unassigned_orders):
        """ Allocates tasks by awarding them to the agent with the highest bid. """
        idle_robots = [a for a in self.model.schedule.agents 
                      if isinstance(a, DroneAgent) and a.state == STATE_IDLE]
        if not idle_robots: 
            return
            
        for mission in unassigned_orders:
            if not idle_robots:
                break
                
            bids = {r: r.calculate_cnp_bid(mission) for r in idle_robots}
            valid_bids = {r: s for r, s in bids.items() if s >= 0}
            
            if valid_bids:
                winner = max(valid_bids, key=valid_bids.get)
                if self.assign_order_specifically(winner, mission):
                    print(f"🤝 CNP: Drone {winner.unique_id} won mission {mission.order_id}")
                    idle_robots.remove(winner)

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

# --- Passive Environmental Agents ---

class PharmacyAgent(mesa.Agent):
    """ Represents static airdwa shelving. Non-walkable. """
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.type_name = "Pharmacy"
        self.color = "brown" 


class DouarAgent(mesa.Agent):
    """ Represents the target destination for goods. Non-walkable. """
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.type_name = "Douar"
        self.color = "black" 


class DroneBaseAgent(mesa.Agent):
    """ Represents a location where drones can recover battery energy. Walkable by drones only. """
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.type_name = "DroneBase"