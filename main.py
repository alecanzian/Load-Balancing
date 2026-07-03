# main.py

import argparse
import os
import pickle

import numpy as np

from dispatcher import run_experiment
from plotting import (
    plot_response_time_cdf, plot_server_loads, plot_response_time_boxplot,
    plot_sweep_metric, plot_sweep_cdf,
    plot_avg_load, plot_load_variance, plot_summary_table,
)
from config import (
    SEED, TIME_SCALE, BASE_WORK, SCALE_LABEL, sim_paths,
    SIM1_N_JOBS, SIM1_FIXED_ALPHA, SIM1_FIXED_LOAD,
    SIM1_ALPHAS, SIM1_LOAD_RATES, SIM1_STRATEGIES,
    SIM2_N_JOBS, SIM2_ALPHAS, SIM2_LOAD_RATES, SIM2_STRATEGIES,
)


# ----------------------------------------------------
# persistence
# ----------------------------------------------------

def load_results(results_file):
    if os.path.exists(results_file):
        print(f"Loading existing results from {results_file}")
        with open(results_file, 'rb') as f:
            return pickle.load(f)
    return {}


def save_results(all_results, results_file):
    with open(results_file, 'wb') as f:
        pickle.dump(all_results, f)


# ----------------------------------------------------
# experiment driver
# ----------------------------------------------------

def run_grid(points, strategies, n_jobs, results_file):
    """Run every (alpha, load, strategy) combination in `points`, resuming
    from previously saved results at strategy granularity."""
    all_results = load_results(results_file)

    for alpha, load in points:
        all_results.setdefault(load, {}).setdefault(alpha, {})
        for name in strategies:
            if name in all_results[load][alpha]:
                print(f"Skipping λ={load}, α={alpha}, {name} — already computed")
                continue
            jobs, servers = run_experiment(
                pareto_param=alpha,
                load_rate=load,
                n_jobs=n_jobs,
                time_scale=TIME_SCALE,
                strategy=name,
                seed=SEED,
            )
            all_results[load][alpha][name] = {
                # float32 halves storage vs float64
                "response_times": np.array([j['response_time'] for j in jobs], dtype=np.float32),
                "server_loads":   np.array([s.load.value for s in servers],   dtype=np.float32),
            }
            save_results(all_results, results_file)
            print(f"  Saved λ={load}, α={alpha}, {name}")

    return all_results


# ----------------------------------------------------
# simulation 1 — one-parameter-at-a-time sweeps
# ----------------------------------------------------

def sim1_points():
    load_sweep  = [(SIM1_FIXED_ALPHA, l) for l in SIM1_LOAD_RATES]
    alpha_sweep = [(a, SIM1_FIXED_LOAD) for a in SIM1_ALPHAS]
    # deduplicate (the point (SIM1_FIXED_ALPHA, SIM1_FIXED_LOAD) is in both sweeps)
    seen, points = set(), []
    for p in load_sweep + alpha_sweep:
        if p not in seen:
            seen.add(p)
            points.append(p)
    return points, load_sweep, alpha_sweep


def run_sim1():
    _, plots_dir, results_file = sim_paths("sim1")
    points, load_sweep, alpha_sweep = sim1_points()
    all_results = run_grid(points, SIM1_STRATEGIES, SIM1_N_JOBS, results_file)

    # per-strategy sweep plots (mean response time, avg load) + CDFs
    for name in SIM1_STRATEGIES:
        plot_sweep_metric(all_results, load_sweep, SIM1_LOAD_RATES, "λ (arrival rate)",
                          'mean_response_time', plots_dir,
                          f"Mean response time vs λ — α={SIM1_FIXED_ALPHA} — {name}",
                          f"{name}_response_time_vs_load.png", [name], SCALE_LABEL)
        plot_sweep_metric(all_results, load_sweep, SIM1_LOAD_RATES, "λ (arrival rate)",
                          'avg_load', plots_dir,
                          f"Average server load vs λ — α={SIM1_FIXED_ALPHA} — {name}",
                          f"{name}_avg_load_vs_load.png", [name])
        plot_sweep_metric(all_results, alpha_sweep, SIM1_ALPHAS, "α (Pareto shape)",
                          'mean_response_time', plots_dir,
                          f"Mean response time vs α — λ={SIM1_FIXED_LOAD} — {name}",
                          f"{name}_response_time_vs_alpha.png", [name], SCALE_LABEL)
        plot_sweep_metric(all_results, alpha_sweep, SIM1_ALPHAS, "α (Pareto shape)",
                          'avg_load', plots_dir,
                          f"Average server load vs α — λ={SIM1_FIXED_LOAD} — {name}",
                          f"{name}_avg_load_vs_alpha.png", [name])
        plot_sweep_cdf(all_results, load_sweep, [f"λ={l}" for l in SIM1_LOAD_RATES],
                       name, plots_dir,
                       f"Response time CDFs, λ varied — α={SIM1_FIXED_ALPHA} — {name}",
                       f"{name}_cdf_load_varied.png", SCALE_LABEL)
        plot_sweep_cdf(all_results, alpha_sweep, [f"α={a}" for a in SIM1_ALPHAS],
                       name, plots_dir,
                       f"Response time CDFs, α varied — λ={SIM1_FIXED_LOAD} — {name}",
                       f"{name}_cdf_alpha_varied.png", SCALE_LABEL)

    # cross-strategy comparisons on each sweep (distinct filenames — the old
    # version saved both variance plots to the same file)
    plot_sweep_metric(all_results, load_sweep, SIM1_LOAD_RATES, "λ (arrival rate)",
                      'load_variance', plots_dir,
                      f"Load variance vs λ — α={SIM1_FIXED_ALPHA}",
                      "load_variance_vs_load.png", SIM1_STRATEGIES)
    plot_sweep_metric(all_results, alpha_sweep, SIM1_ALPHAS, "α (Pareto shape)",
                      'load_variance', plots_dir,
                      f"Load variance vs α — λ={SIM1_FIXED_LOAD}",
                      "load_variance_vs_alpha.png", SIM1_STRATEGIES)
    plot_summary_table(all_results, plots_dir, SIM1_N_JOBS, BASE_WORK,
                       SCALE_LABEL, SIM1_STRATEGIES)


# ----------------------------------------------------
# simulation 2 — full (alpha, lambda) grid
# ----------------------------------------------------

def run_sim2():
    _, plots_dir, results_file = sim_paths("sim2")
    points = [(a, l) for l in SIM2_LOAD_RATES for a in SIM2_ALPHAS]
    all_results = run_grid(points, SIM2_STRATEGIES, SIM2_N_JOBS, results_file)

    for alpha, load in points:
        plot_response_time_cdf(all_results, alpha, load, plots_dir,
                               SCALE_LABEL, SIM2_N_JOBS, BASE_WORK)
        plot_server_loads(all_results, alpha, load, plots_dir, SIM2_N_JOBS, BASE_WORK)
        plot_response_time_boxplot(all_results, alpha, load, plots_dir,
                                   SIM2_N_JOBS, BASE_WORK, SCALE_LABEL)

    plot_avg_load(all_results, plots_dir)
    plot_load_variance(all_results, plots_dir)
    plot_summary_table(all_results, plots_dir, SIM2_N_JOBS, BASE_WORK, SCALE_LABEL)

# ----------------------------------------------------
# simulation 3 — fine tuning age weight
# ----------------------------------------------------

def run_sim3():
    _, plots_dir, results_file = sim_paths("sim3")
    points = [(1.1,0.8)]
    all_results = run_grid(points, ["age_aware_jsq", "age_aware_empirical_jsq"], SIM2_N_JOBS, results_file)

    for alpha, load in points:
        plot_response_time_cdf(all_results, alpha, load, plots_dir, SCALE_LABEL,
                           SIM2_N_JOBS, BASE_WORK,
                           strategies=["age_aware_jsq", "age_aware_empirical_jsq"])
        

# ----------------------------------------------------
# entry point
# ----------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Load balancing simulations")
    parser.add_argument("simulation", choices=["sim1", "sim2", "all"],
                        help="which simulation to run")
    args = parser.parse_args()

    if args.simulation in ("sim1", "all"):
        run_sim1()
    if args.simulation in ("sim2", "all"):
        run_sim2()
        run_sim3()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExperiment interrupted by user. Exiting gracefully.")