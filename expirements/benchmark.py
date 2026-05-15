import sys
import os
import pandas as pd
import mesa

# --- PATH CONFIGURATION ---
# 1. Get the path to the current folder (experiments)
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Get the Project Root (MultiRobot_Delivery_Project)
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# 3. Get the src folder
src_dir = os.path.join(project_root, 'src')

# 4. Add BOTH to sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
# -----------------------------------------

from src.model import WarehouseModel

# Define the Scenarios
scenarios = {
    "1_Light_Load": {
        "n_robots": 5, 
        "order_rate": 0.05,
        "failure_step": -1
    },
    "2_Heavy_Load": {
        "n_robots": 5, 
        "order_rate": 0.30,
        "failure_step": -1
    },
    "3_Robot_Failure": {
        "n_robots": 5,
        "order_rate": 0.1,
        "failure_step": 50 # Fail a robot at step 50
    }
}

def run_benchmark():
    results = []
    
    # Compare the 3 mechanisms
    mechanisms = ["greedy", "cnp", "auction"]
    
    total_runs = len(mechanisms) * len(scenarios)
    current_run = 0

    print(f"🚀 Starting Benchmark: {total_runs} combinations...")

    for mech in mechanisms:
        for scenario_name, params in scenarios.items():
            current_run += 1
            print(f"[{current_run}/{total_runs}] Running {scenario_name} | Mechanism: {mech}...")
            
            # Prepare parameters
            run_params = params.copy()
            run_params["coordination_type"] = mech
            
            # Run Batch: 5 iterations per setting, 200 steps each
            try:
                batch_results = mesa.batch_run(
                    WarehouseModel,
                    parameters=run_params,
                    iterations=5,      
                    max_steps=200,     
                    number_processes=1, 
                    data_collection_period=1,
                    display_progress=False
                )
                
                df = pd.DataFrame(batch_results)
                df["Mechanism"] = mech
                df["Scenario"] = scenario_name
                results.append(df)
            except Exception as e:
                print(f"❌ Error in {scenario_name}: {e}")
                print("Tip: Did you update src/model.py with the new metrics and failure_step?")
                return

    # Save results
    output_file = os.path.join(current_dir, "simulation_results.csv")
    final_df = pd.concat(results)
    final_df.to_csv(output_file)
    print(f"✅ Done! Results saved to: {output_file}")

if __name__ == "__main__":
    run_benchmark()