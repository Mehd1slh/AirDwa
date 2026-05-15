import os
import sys
import subprocess

if __name__ == "__main__":
    server_file = os.path.join("src", "server.py")

    if not os.path.exists(server_file):
        print(f"Error: Could not find {server_file}")
        sys.exit(1)

    print("Launching Multi-Robot Delivery System via Solara...")
    print(f"Target: {server_file}")
    
    
    try:
        # shell=True to find the 'solara' command on winows
        subprocess.run(["solara", "run", server_file], shell=True, check=True)
    except KeyboardInterrupt:
        print("\nServer stopped.")