import mesa
import random
from agents import RobotAgent, ShelfAgent, PackingStationAgent, ChargingStationAgent, OrderManagerAgent

# Default environment constants
GRID_WIDTH = 20
GRID_HEIGHT = 20
NUM_ROBOTS = 3

def compute_gini(model):
    """
    Calculates the Gini coefficient to measure the statistical dispersion of 
    completed orders among robots. A lower value indicates better workload fairness.
    """
    agent_wealth = [agent.orders_completed for agent in model.robot_agents]
    x = sorted(agent_wealth)
    N = len(model.robot_agents)
    B = sum(x)
    if B == 0: return 0
    return (2 * sum((i + 1) * xi for i, xi in enumerate(x)) - (N + 1) * B) / (N * B)

def get_total_distance(model):
    """Sum of distance traveled by all robots in the simulation."""
    return sum([agent.distance_traveled for agent in model.robot_agents])

class WarehouseModel(mesa.Model):
    """
    The main warehouse simulation environment. Manages the grid, the schedule, 
    and handles global events like order generation and fault injection.
    """
    def __init__(self, coordination_type="cnp", n_robots=NUM_ROBOTS, order_rate=0.08, failure_step=-1, map_data=None):
        super().__init__()
        self.coordination_type = coordination_type # "greedy", "cnp", or "auction"
        self.num_robots = n_robots
        self.order_rate = order_rate
        self.running = True
        self.failure_step = failure_step # Specific step to trigger a manual failure (for benchmark.py)
        self.schedule = mesa.time.RandomActivation(self)

        # Determine dimensions: prefer custom map data, otherwise use defaults
        self.width = map_data.get("width", GRID_WIDTH) if map_data else GRID_WIDTH
        self.height = map_data.get("height", GRID_HEIGHT) if map_data else GRID_HEIGHT
        
        # MultiGrid allows multiple agents (e.g., a robot on a charging station) in one cell
        self.grid = mesa.space.MultiGrid(self.width, self.height, torus=False)
        
        # References for internal management and data collection
        self.robot_agents = []
        self.shelves = []
        self.packing_stations = []
        self.charging_stations = []
        
        # Initialize the environment structure
        if map_data:
            self._load_custom_layout(map_data)
        else:
            self._init_warehouse_layout()
        
        # Create the central dispatcher
        self.order_manager = OrderManagerAgent(999, self)
        self.schedule.add(self.order_manager)
        
        # Spawn the mobile fleet
        self._init_robots()

        # Data collection for real-time graphing and benchmark analysis
        self.datacollector = mesa.DataCollector(
            model_reporters={
                "Throughput": lambda m: m.order_manager.completed_orders,
                "Conflict_Rate": lambda m: m._get_conflict_rate(),
                "Idle_Time": lambda m: self._get_idle_time(),
                "Total_Distance": get_total_distance,
                "Fairness_Gini": compute_gini
            },
            agent_reporters={
                "Battery": lambda a: a.battery if isinstance(a, RobotAgent) else None,
                "State": lambda a: a.state if isinstance(a, RobotAgent) else None
            }
        )

    def step(self):
        """ Progresses the simulation by one tick. """
        self.datacollector.collect(self)
        self.schedule.step()

        # If a specific step was targeted for failure (used in experiments)
        if self.schedule.steps == self.failure_step:
            print(f"Scenario Trigger: Injecting failure at step {self.schedule.steps}")
            self.fail_random_robot()

    def _init_warehouse_layout(self):
        """ Default layout generator: places shelves in columns and stations at boundaries. """
        # Shelves: Organized in vertical clusters
        for x in range(3, GRID_WIDTH - 2, 3): 
            for y in range(2, GRID_HEIGHT - 2):
                pos = (x, y)
                self.shelves.append(pos)
                shelf = ShelfAgent(f"Shelf_{x}_{y}", self)
                self.grid.place_agent(shelf, pos)
        
        # Packing Stations: Placed along the left wall
        for y in range(0, GRID_HEIGHT, 2):
            pos = (0, y)
            self.packing_stations.append(pos)
            station = PackingStationAgent(f"Pack_{0}_{y}", self)
            self.grid.place_agent(station, pos)

        # Charging Stations: Placed at fixed corners
        self.charging_stations = [(GRID_WIDTH-1, GRID_HEIGHT-1), (GRID_WIDTH-1, 0)]
        for i, pos in enumerate(self.charging_stations):
            charger = ChargingStationAgent(f"Charge_{i}", self)
            self.grid.place_agent(charger, pos)

    def _load_custom_layout(self, data):
        """ Reconstructs the environment using coordinates provided by the Map Editor. """
        for x, y in data["shelves"]:
            shelf = ShelfAgent(f"Shelf_{x}_{y}", self)
            self.grid.place_agent(shelf, (x, y))
            self.shelves.append((x, y))
            
        for x, y in data["packing_stations"]:
            station = PackingStationAgent(f"Pack_{x}_{y}", self)
            self.grid.place_agent(station, (x, y))
            self.packing_stations.append((x, y))
            
        for x, y in data["charging_stations"]:
            charger = ChargingStationAgent(f"Charge_{x}_{y}", self)
            self.grid.place_agent(charger, (x, y))
            self.charging_stations.append((x, y))

    def _init_robots(self):
        """ Spawns the robot fleet at random available locations. """
        for i in range(self.num_robots):
            pos = self.get_random_free_cell()
            robot = RobotAgent(i, self, pos)
            self.grid.place_agent(robot, pos)
            self.schedule.add(robot)
            self.robot_agents.append(robot)

    def is_walkable(self, pos):
        """ Collision avoidance: checks if a cell is out of bounds or blocked by static objects/failed robots. """
        if self.grid.out_of_bounds(pos):
            return False
            
        cell_contents = self.grid.get_cell_list_contents(pos)
        for agent in cell_contents:
            # Static infrastructure blocks path
            if isinstance(agent, (ShelfAgent, PackingStationAgent)):
                return False
            # Working robots are handled by A*, but a FAILED robot becomes a permanent obstacle
            if isinstance(agent, RobotAgent):
                if agent.state == "FAILED":
                    return False
                return False # Treat other robots as obstacles to prevent stacking

        return True

    def fail_random_robot(self):
        """ Injects a fault into the system by picking an active robot and triggering its failure state. """
        active_robots = [r for r in self.robot_agents if r.state != "FAILED"]
        if active_robots:
            robot = self.random.choice(active_robots)
            robot.trigger_failure()

    def _get_conflict_rate(self):
        """ Metric: Number of broken robots currently acting as grid obstacles. """
        return sum(1 for r in self.robot_agents if r.state == "FAILED")

    def _get_idle_time(self):
        """ Metric: Number of robots currently in IDLE state. """
        return sum(1 for r in self.robot_agents if r.state == "IDLE")
    
    def get_random_shelf(self):
        """ Utility for order creation: returns a random shelf coordinate. """
        return random.choice(self.shelves) if self.shelves else None

    def get_random_packing_station(self):
        """ Utility for order creation: returns a random station coordinate. """
        return random.choice(self.packing_stations) if self.packing_stations else None

    def get_random_free_cell(self):
        """ Utility for robot spawning: finds an empty, walkable cell. """
        while True:
            x = random.randrange(self.grid.width)
            y = random.randrange(self.grid.height)
            if self.is_walkable((x, y)):
                return (x, y)

    def _get_avg_battery(self):
        """ Metric: Calculates the fleet's average battery health. """
        batteries = [r.battery for r in self.robot_agents]
        return sum(batteries) / len(batteries) if batteries else 0
    
    def _get_active_robot_count(self):
        """ Metric: Total robots currently processing a task. """
        return sum(1 for r in self.robot_agents if r.state != "IDLE")