import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

def run_script(script_name):
    print(f"Running {script_name}...")
    try:
        python_exe = str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable))
        result = subprocess.run([python_exe, script_name], capture_output=True, text=True, check=True, cwd=str(ROOT))
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}:")
        print(e.stderr)
        return False

def main():
    print("--- ParkSense Data Pipeline Execution ---")

    # 1. Run Core Pipeline (Generates junction, station, and location summaries)
    if not run_script("src/pipeline.py"):
        print("Critical Failure: Core pipeline failed. Aborting.")
        sys.exit(1)

    # 2. Run Hotspot Detection (Runs DBSCAN and creates hotspot_clusters.csv)
    if not run_script("src/hotspot.py"):
        print("Critical Failure: Hotspot detection failed. Aborting.")
        sys.exit(1)

    print("\n--- Pipeline Successfully Completed ---")
    print("All derived datasets updated: junction_summary.csv, police_station_summary.csv, location_cluster_input.csv, hotspot_clusters.csv")

if __name__ == "__main__":
    main()
