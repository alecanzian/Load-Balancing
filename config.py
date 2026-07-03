# config.py

import os

# ==============================================
# GLOBAL PARAMETERS
# ==============================================

SEED       = 42      # fixed seed for reproducibility
TIME_SCALE = 1e-3    # interarrival unit: 1=s, 1e-3=ms, 1e-6=µs
BASE_WORK  = 3000    # CPU iterations per unit of job size

SCALE_LABEL = {1: 's', 1e-3: 'ms', 1e-6: 'us', 1e-9: 'ns'}[TIME_SCALE]

OUTPUT_DIR = "output"

# ==============================================
# SIMULATION 1 — one-parameter-at-a-time sweeps
# (fix alpha, vary lambda; fix lambda, vary alpha)
# ==============================================

SIM1_N_JOBS      = 20000
SIM1_FIXED_ALPHA = 1.3                                  # used while lambda varies
SIM1_FIXED_LOAD  = 0.3                                  # used while alpha varies
SIM1_ALPHAS      = [1.1, 1.3, 1.5, 1.7, 1.9, 2.0, 2.5]
SIM1_LOAD_RATES  = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
SIM1_STRATEGIES  = ["random", "jsq", "age_aware_jsq"]

# ==============================================
# SIMULATION 2 — full (alpha, lambda) grid
# ==============================================

SIM2_N_JOBS     = 20000
SIM2_ALPHAS     = [1.1, 1.3, 1.5, 1.8]
SIM2_LOAD_RATES = [0.3, 0.6, 0.8]
SIM2_STRATEGIES = ["random", "jsq", "age_aware_jsq"]

# ==============================================
# OUTPUT PATHS
# ==============================================

def sim_paths(sim_name):
    """Return (data_dir, plots_dir, results_file) for a simulation, creating dirs."""
    data_dir  = os.path.join(OUTPUT_DIR, sim_name, "data")
    plots_dir = os.path.join(OUTPUT_DIR, sim_name, "plots")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)
    return data_dir, plots_dir, os.path.join(data_dir, "all_results.pkl")