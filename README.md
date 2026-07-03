# Load Balancing Simulator

A Python simulation of a multi-server load balancing system under heavy-tailed workloads, developed as a university project for the Software Performance and Scalability course.

## Project Structure
```

LoadBalancing/
├── main.py             # Entry point — runs simulation 1, 2, or both (CLI)
├── config.py           # All simulation constants and parameter grids
├── models.py           # Shared data structures: Job and Server
├── server.py           # Server process logic and process_request
├── dispatcher.py       # Dispatching strategies and experiment runner
├── plotting.py         # All visualization and output logic
└── output/             # Generated plots and results (git-ignored)
├── sim1/
│   ├── data/       # all_results.pkl (incremental cache)
│   └── plots/
└── sim2/
├── data/
└── plots/

---

## Architecture

The system simulates an **open queueing network** with:

- **1 dispatcher** — generates a Poisson arrival process and routes jobs to servers based on a dispatching policy
- **3 servers** — independent `multiprocessing.Process` instances, each with its own FIFO inbound queue and result queue
- **FCFS scheduling** at each server

```
Dispatcher (Poisson arrivals)
│
├──── queue[0] ───► Server 0 ───► result_queue[0]
├──── queue[1] ───► Server 1 ───► result_queue[1]
└──── queue[2] ───► Server 2 ───► result_queue[2]

All queues are backed by a single shared `multiprocessing.Manager`, so `qsize()` works on both Linux and macOS.
---

## Service Time Distribution

Each job's service time is determined by:

```python
def process_request(x, alpha, base_work):
    multiplier = random.paretovariate(alpha)   # heavy-tailed amplifier
    n = int(base_work * x * multiplier)        # total CPU iterations
    # ... CPU-bound loop
```

Where:
- `x ~ Uniform(0.5, 2.0)` — job size
- `multiplier ~ Pareto(α)` — heavy-tailed amplifier
- `base_work` — constant controlling baseline CPU intensity, defined in `config.py`

The resulting service time is a **product distribution** — General (G) in Kendall's notation. Under random dispatch each server sees a Poisson(λ/3) arrival process, making each server an **M/G/1** queue. Under all other strategies the arrival process at each server is non-Poisson (**G/G/1**).

With `BASE_WORK = 3000` and balanced dispatching, the system is stable (ρ < 1 per server)
across the entire explored parameter space, including the most demanding combination
(α = 1.1, λ = 0.9, ρ ≈ 0.62). Stability holds as long as no single server receives more
than ~61% of total traffic in the long run.

---

## Dispatching Strategies

Strategies are instantiated per-experiment via `make_dispatcher()` in `dispatcher.py`.

| Strategy | Status | Description |
|---|---|---|
| `random` | ✅ implemented | Baseline — uniform random server selection |
| `jsq` | ✅ implemented | Join Shortest Queue — pick server with fewest pending jobs |
| `power_of_two` | ✅ implemented | Sample 2 random servers, pick the shorter queue |
| `age_aware_jsq` | ✅ implemented | JSQ penalized by age of current job in service (weight = 1) |
| `age_aware_empirical_jsq` | ✅ implemented | Age-aware JSQ with α-dependent weight, from 0.001 (α = 1.1) to 1.0 (α ≥ 2.0) |
| `round_robin` | ✅ implemented, unused | Round-robin rotation |
| `jiq` | ✅ implemented, unused | Join Idle Queue — pick idle server, fall back to random |

Which strategies run in each simulation is controlled by `SIM1_STRATEGIES` and
`SIM2_STRATEGIES` in `config.py`.

---

## Simulations

Two independent experiment campaigns are defined:

**Simulation 1 — one-parameter-at-a-time sweeps.** Fixes `α = 1.3` and sweeps
`λ ∈ {0.1, …, 0.9}`, then fixes `λ = 0.3` and sweeps
`α ∈ {1.1, 1.3, 1.5, 1.7, 1.9, 2.0, 2.5}`. Strategies: random, JSQ,
power-of-two, age-aware JSQ.

**Simulation 2 — full (α, λ) grid.** All combinations of `λ ∈ {0.3, 0.6, 0.8}`
and `α ∈ {1.1, 1.3, 1.5, 1.8}`. Strategies: random, JSQ, age-aware JSQ,
age-aware empirical JSQ.

---

## Parameters

All parameters are defined in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `SEED` | `42` | RNG seed for reproducibility |
| `TIME_SCALE` | `1e-3` | Interarrival time unit (1=s, 1e-3=ms, 1e-6=µs) |
| `BASE_WORK` | `3000` | CPU iterations per unit of job size — controls server speed |
| `SCALE_LABEL` | `'ms'` | Human-readable label for TIME_SCALE, used in plot axes |
| `OUTPUT_DIR` | `'output'` | Root directory for all results |
| `SIM1_N_JOBS` | `50000` | Jobs per experiment (simulation 1) |
| `SIM1_FIXED_ALPHA` | `1.3` | α held fixed while λ varies (simulation 1) |
| `SIM1_FIXED_LOAD` | `0.3` | λ held fixed while α varies (simulation 1) |
| `SIM1_ALPHAS` | `[1.1 … 2.5]` | α sweep values (simulation 1) |
| `SIM1_LOAD_RATES` | `[0.1 … 0.9]` | λ sweep values (simulation 1) |
| `SIM1_STRATEGIES` | see config | Strategies run in simulation 1 |
| `SIM2_N_JOBS` | `50000` | Jobs per experiment (simulation 2) |
| `SIM2_ALPHAS` | `[1.1, 1.3, 1.5, 1.8]` | α grid values (simulation 2) |
| `SIM2_LOAD_RATES` | `[0.3, 0.6, 0.8]` | λ grid values (simulation 2) |
| `SIM2_STRATEGIES` | see config | Strategies run in simulation 2 |

`TIME_SCALE` and `BASE_WORK` must be tuned together to achieve the desired server
utilization ρ = λ·E[S]/3 while keeping the per-job measurement overhead (~20–100µs)
small relative to the mean service time.

---

## Reproducibility

The seed controls:
- **Inter-arrival times** — same Poisson process across strategies
- **Job sizes x** — same uniform draws across strategies
- **Pareto multipliers** — each server seeded with `seed + server_id` for independence

This ensures fair comparison: the only variable between strategies is the dispatching decision itself.

> Note: due to different routing decisions across strategies, the order in which each server consumes its Pareto sequence may differ. Results are directionally valid but exact numerical comparisons should be treated with caution at α=1.1 due to infinite variance.

---

## Running

```bash
python main.py sim1    # run simulation 1 only
python main.py sim2    # run simulation 2 only
python main.py all     # run both sequentially
```

Results are cached incrementally at **strategy granularity** in
`output/sim{1,2}/data/all_results.pkl`: interrupted runs resume where they left off,
and already-computed (λ, α, strategy) triples are skipped. Delete the pickle to force
a full rerun (required after changing `BASE_WORK` or any other parameter that affects
service times — the cache does not detect parameter changes).

---

## Output

Plots are saved to `output/sim1/plots/` and `output/sim2/plots/`.

**Simulation 1** (per-strategy sweep plots and cross-strategy comparisons):

| File | Description |
|---|---|
| `{strategy}_response_time_vs_load.png` | Mean response time vs λ (α fixed) |
| `{strategy}_response_time_vs_alpha.png` | Mean response time vs α (λ fixed) |
| `{strategy}_avg_load_vs_load.png` | Average server load vs λ |
| `{strategy}_avg_load_vs_alpha.png` | Average server load vs α |
| `{strategy}_cdf_load_varied.png` | Response time CDFs across λ values |
| `{strategy}_cdf_alpha_varied.png` | Response time CDFs across α values |
| `load_variance_vs_load.png` | Load variance across servers vs λ, all strategies |
| `load_variance_vs_alpha.png` | Load variance across servers vs α, all strategies |
| `summary_table_*.png` | Mean, Median, P90, P99 per strategy |

**Simulation 2** (per-(α, λ) comparison plots and grid summaries):

| File | Description |
|---|---|
| `response_time_cdf_alpha{α}_load{λ}.png` | CDF of response time per strategy (log scale) |
| `boxplot_alpha{α}_load{λ}.png` | Box plot of response time distribution (log scale) |
| `server_loads_alpha{α}_load{λ}.png` | Server load distribution per strategy |
| `avg_load.png` | Average load vs α, one panel per λ |
| `load_variance.png` | Load variance vs α, one panel per λ |
| `summary_table.png` | Mean, Median, P90, P99 per strategy |

Filtered plots comparing only selected strategies are generated with a suffix:

response_time_cdf_alpha1_1_load0_8_age_aware_jsq_age_aware_empirical_jsq.png


---

## Results Cache Structure

`output/sim{1,2}/data/all_results.pkl` is a nested dictionary:

```python
all_results = {
    0.3: {                                   # load rate λ
        1.1: {                               # Pareto shape α
            "random": {
                "response_times": np.ndarray,  # float32, one value per job
                "server_loads":   np.ndarray,  # float32, load per server (3 entries)
            },
            "jsq":           { ... },
            "age_aware_jsq": { ... },
            ...
        },
        1.3: { ... },
    },
    0.6: { ... },
}
```
