# Load Balancing with Heavy-Tailed Tasks

**Course:** Software Performance and Scalability
**University:** Ca' Foscari of Venice
**Group:** Mirgali Azhmukhambetov, Alessandro Canzian, Quinn Robertson

---

## 1. Introduction

This project evaluates and compare different strategies for dispatching requests which follow a heavy-tailed distribution. In many real-world systems most requests complete quickly, but a small fraction take disproportionately long. These so-called *stragglers* have an outsized impact on overall system performance, and naive dispatching policies struggle to contain the damage they cause.

The goal of this work is to design, implement, and evaluate dispatching strategies for a system of three identical servers, comparing them against a random baseline across a range of load levels and tail-heaviness parameters.

---

## 2. System Model

The simulated system consists of:

- **3 identical servers**, each running as an independent process (`multiprocessing.Process`).
- **A stream of incoming requests**, with interarrival times drawn from an exponential distribution with rate `λ` (Poisson arrivals).
- **Each request** carries a size parameter `x`, drawn uniformly from `[0.5, 2.0]`.
- **Processing time** is determined by `x`, a constant variable called `base_work`, and a random multiplicative factor drawn from a Pareto distribution with shape parameter `α`:

```
n = base_work × x × Pareto(α)
```

The CPU work is simulated by running `n` iterations of a floating-point loop (`sin`/`cos` accumulation), making the workload genuinely CPU-bound and processing times realistically variable.

Each server exposes:

- A **job queue** (`mp.Queue`) for incoming jobs.
- A **result queue** for completed jobs, containing measured response times.
- A shared **`current_service_start`** timestamp (used to compute job age).
- A shared **`load`** value (fraction of time the server was busy).

**Simulation parameters:** Two simulations have been run:
- `n = 50,000` jobs, `base_work = 3,000`, arrival time scale = `1 ms`
- `n = 10,000` jobs, `base_work = 3,000`, arrival time scale = `1 ms`.

---

## 3. Dispatching Strategies

Although the project required only a comparison between the custom dispatcher and the random baseline, we chose to implement and evaluate several additional strategies. Since random dispatching is a trivial policy with no load awareness, comparing against it alone would not provide meaningful insight into the relative merits of our approach.


### 3.1 Baseline: Random Dispatcher

The random dispatcher assigns each incoming job to a uniformly random server, with no awareness of queue state or job size. It serves as the baseline for all comparisons.

### 3.2 Join Shortest Queue (JSQ)

JSQ queries the queue length of each server at dispatch time and routes the job to whichever server has the fewest pending jobs, breaking ties randomly. 

### 3.3 Power-of-Two Dispatcher

Instead of querying all servers, Power-of-Two samples exactly two servers at random and routes the job to the one with the shorter queue. This reduces polling overhead while preserving much of JSQ's benefit. 

### 3.4 Age-Aware JSQ Dispatcher

This dispatcher augments JSQ with information about the *age* of the job currently in service on each server. Age is defined as the elapsed wall-clock time since the server began processing its current job, measured via the shared `current_service_start` timestamp.

The score assigned to each server is:

```
score(s) = queue_length(s) + age_weight × age(s)
```

*The server with the lowest score is chosen. The intuition is that a server occupied by a very old job is likely stuck on a straggler, so its effective backlog is higher than queue length alone suggests.*

### 3.5 Alpha-and-Load-Based Dispatcher (Custom Strategy)

This is the original strategy developed for this project. The core idea is that the optimal dispatching policy is not fixed, but it depends on how heavy-tailed the workload actually is. The dispatcher selects a sub-strategy at construction time based on the known Pareto shape parameter `α`:

| `α` range | Selected strategy | Rationale |
|---|---|---|
| `α <= 1.15` | Power-of-Two | Extremely heavy tail: variance is theoretically infinite; sampling avoids over-relying on stale queue state |
| `1.15 < α <= 1.50` | Age-Aware JSQ | Moderate heavy tail: age signal is meaningful and helps avoid routing behind known stragglers |
| `α > 1.50` | JSQ | Lighter tail: queue length is a reliable proxy for workload |

---

## 4. Experimental Setup

### 4.1 Parameter Space

Experiments were run across all combinations of:

- **`α ∈ {1.1, 1.3, 2.0, 2.5}`** - covering very heavy to moderately heavy tails
- **`λ ∈ {0.3, 0.5, 0.7}`** - low, medium, and high arrival rates

Each `(α, λ)` combination was evaluated under all dispatching strategies described in Section 3, for a total of `4 × 3 × 5 = 60` independent experiments. 

### 4.2 Reproducibility

All experiments used a fixed random seed (`42`) to ensure partial reproducibility across runs:

- **Inter-arrival times** - drawn from an exponential distribution seeded with `42`, guaranteeing the same Poisson arrival process for all strategies
- **Job sizes `x`** - drawn from `Uniform(0.5, 2.0)` using the same seed, so all strategies receive identical job sizes in the same order
- **Pareto multipliers** - each server process is seeded with `seed + server_id` (42, 43, 44), making multiplier draws reproducible within a single run

However, since different dispatching decisions route jobs to different servers in different orders, each server consumes its Pareto sequence differently across strategies. This means the actual service time a job experiences may vary between strategies even for the same job. Full cross-strategy reproducibility of service times would require pre-assigning Pareto multipliers to jobs before dispatching, which was not implemented. Response time rankings between strategies are therefore directionally valid but exact numerical values should be interpreted with caution, especially at α=1.1 where infinite variance amplifies this effect.


### 4.3 Response Time Measurement

Response time was measured as wall-clock time from the moment the job was placed in the server's inbound queue to the moment its processing completed:

```
response_time = service_end - joining_time
```

This includes both waiting time in the queue and actual service time, matching the standard definition of sojourn time in queueing theory.


### 4.4 Server Load Measurement

Server load (utilization) is computed per server at the end of each experiment as the fraction of time the server spent actively processing jobs:

```
load = total_busy_time / total_elapsed_time
```

Where:
- `total_busy_time` - sum of all service times for jobs processed by that server
- `total_elapsed_time` - wall-clock time from when the server processed its first job to when it received the shutdown sentinel


### 4.5 Output Metrics

The following plots were produced for each `(α, λ)` combination:

- **Boxplots** of response time on a log scale
- **Empirical CDFs** of response time on a log scale
- **Server load distribution** bar charts which show load per server per strategy
- **Average server load** line plots which show how utilization varies with `α` across load rates
- **Server load variance** line plots which show how balanced the load distribution is across servers
- **Summary table** - reports mean, median, P90, and P99 response times for all strategies and all `(α, λ)` combinations
---

## 5. Results

### 5.1 Effect of `α`: How Tail Heaviness Changes Everything

The most striking result across all experiments is how dramatically `α` shapes system behavior for all strategies.

**At `α = 1.1`** (very heavy tail, Pareto variance theoretically infinite), the gap between random dispatching and all queue-aware strategies is extreme. The full-strategy boxplots (Figures A1–A3) show that random dispatching produces a wide IQR and whiskers that extend to hundreds of thousands of milliseconds - in the `λ = 0.5` and `λ = 0.7` cases, the y-axis reaches the order of `10⁶ ms`. By contrast, JSQ, Age-Aware JSQ, Power-of-Two, and the custom dispatcher all produce dramatically tighter boxes.

The summary table confirms this numerically. At `α = 1.1`, `λ = 0.3`, the random dispatcher achieves a mean response time of roughly `1,137 ms` and a P99 of `~194,410 ms`. JSQ reduces the mean to `~28 ms` and the P99 to `~50 ms`. Age-Aware JSQ achieves a mean of `~43 ms` (P99 `~44 ms`), Power-of-Two `~34 ms` (P99 `~104 ms`), and the custom dispatcher - which selects Power-of-Two at this `α` - achieves a mean of `~713 ms` and a P99 of `~374 ms`.

A notable result at `α = 1.1`, `λ = 0.5` and `λ = 0.7` is the behavior of the custom dispatcher relative to the other smart strategies. The CDF plots (Figures B2–B3) clearly show that at very high load with an extremely heavy tail, JSQ and Age-Aware JSQ substantially outperform both Power-of-Two and the custom dispatcher. At `α = 1.1`, `λ = 0.5`, the summary table shows JSQ achieves a mean of `~1,063 ms` while the custom dispatcher (Power-of-Two) reaches `~28,117 ms` - a 26× difference. Age-Aware JSQ (`~1,499 ms` mean) also substantially beats Power-of-Two (`~5,301 ms` mean) here.

This reveals a structural limitation of the Power-of-Two selection in this regime: when load is high and `α` is near `1`, sampling only two servers is insufficient to reliably avoid overloaded ones, whereas a full scan (JSQ) has a much better chance of finding a free server. This is a concrete direction for refinement: the threshold logic should condition on both `α` and `λ` jointly, switching to JSQ at high load even when `α <= 1.15`.

**At `α = 1.3`** (moderately heavy tail), the custom dispatcher selects Age-Aware JSQ. Here the strategy performs well across all load levels. The boxplots (Figures A4–A6) show the custom dispatcher's IQR is among the tightest of all strategies, and the CDF plots (Figures B4–B6) confirm that JSQ, Age-Aware JSQ, and the custom dispatcher all substantially outperform random, while remaining close to each other. At `λ = 0.5` (Figure B5), the random CDF reaches only `~80%` by `100 ms`, while all queue-aware strategies have completed over `90%` of jobs by the same point.

**At `α = 2.0` and `α = 2.5`** (lighter tails), all five strategies converge. The CDF plots (Figures B7–B8 and corresponding `α = 2.5` plots) show the curves nearly overlapping, and the boxplots (Figures A7–A12) reveal minimal differences in IQR or outlier extent. The summary table confirms this: at `α = 2.0`, `λ = 0.3`, mean response times range from `~2.3 ms` (JSQ) to `~2.4 ms` (random), a negligible difference. This is expected and validates the design rationale of the custom dispatcher: above `α = 1.5`, the tail is light enough that queue length is a reliable backlog estimate and any queue-aware policy performs equivalently to more sophisticated ones.

### 5.2 Server Load Distribution

The all-strategy server load charts reveal an important and somewhat counterintuitive phenomenon in the heavy-tailed regime: at `α = 1.1` and `α = 1.3`, queue-aware strategies produce *more unequal* server load than random dispatching - not less.

At `α = 1.1`, `λ = 0.3` (Figure E1), random dispatching yields loads of roughly `0.25 / 0.57 / 0.50` across the three servers. JSQ raises these to approximately `0.28 / 0.62 / 0.42`, Age-Aware JSQ to `0.30 / 0.76 / 0.48`, and the custom dispatcher (Power-of-Two at this `α`) to `0.29 / 0.76 / 0.49`. The pattern sharpens at higher load: at `α = 1.1`, `λ = 0.5` (Figure E2), random gives roughly `0.52 / 0.84 / 0.97`, while Age-Aware JSQ reaches `0.70 / 0.92 / 0.81` - higher total utilization but more evenly spread across the three servers, indicating all servers are being kept busy rather than one sitting idle while another queues up jobs behind a straggler.

At `α = 1.3` (Figures E4–E6), the imbalance is less extreme but the same pattern holds. JSQ and the custom dispatcher both concentrate more load on Server 2 (the server that caught stragglers in this seed), while Power-of-Two keeps a more balanced distribution at the cost of slightly worse response time tail behavior.

This load imbalance is not a flaw - it is the correct and expected behavior of queue-aware dispatchers under heavy-tailed workloads. When a straggler ties up one server, the dispatcher correctly avoids routing new jobs to it, so that server accumulates a high busy fraction (it is occupied processing a disproportionately long job) while the other two absorb the arriving stream. The result is better response times for the majority of jobs at the cost of unequal utilization.

At `α = 2.0` and `α = 2.5` (Figures E7–E12), all five strategies produce nearly perfectly balanced load distributions - for example, approximately `0.16 / 0.16 / 0.16` at `α = 2.0`, `λ = 0.3`, and `~0.14 / 0.15 / 0.15` at `α = 2.5`, `λ = 0.3`. This is fully consistent with the response time convergence observed in that regime: when the tail is light, stragglers are rare enough that all dispatchers behave similarly and the load naturally spreads evenly.

### 5.3 Effect of Load

Across all `α` values, higher `λ` amplifies the differences between strategies. At `λ = 0.3` the system is lightly loaded and all servers drain their queues between arrivals, so even random dispatching performs reasonably well. As `λ` increases to `0.5` and `0.7`, queues begin to build and the risk of a straggler monopolizing a server grows. In this regime, smarter dispatching pays off most.

The most extreme case is `α = 1.1`, `λ = 0.7` (Figure A3 boxplot, Figure B3 CDF): the random dispatcher's CDF stalls well below `70%` at `1,000 ms` - meaning over `30%` of jobs are still waiting - while JSQ and Age-Aware JSQ complete over `90%` of jobs by the same threshold.

### 5.4 Tail Behavior

Even the best dispatcher cannot eliminate the tail entirely. With `α = 1.1`, extreme outliers reaching `300,000+ ms` appear under all strategies. This is a fundamental property of Pareto distributions with `α` close to `1`: a single unlucky job can take arbitrarily long. The benefit of smarter dispatching is not eliminating these extreme events, but ensuring they are isolated - preventing a straggler on one server from inflating response times for all jobs queued behind it.

The summary table makes this vivid: at `α = 1.1`, `λ = 0.3`, random dispatching produces a P99 of `~194,410 ms`. JSQ reduces this to `~50 ms` - a reduction of over three orders of magnitude - by simply avoiding routing new jobs to the server stuck on the outlier.

---

## 6. Discussion

### Why do heavy-tailed tasks make load balancing difficult?

Under light-tailed workloads, queue length is a reliable predictor of how long a server will take to drain its backlog. Under heavy-tailed workloads, this reasoning breaks down: the job currently in service might take orders of magnitude longer than the average, making the queue length uninformative about actual waiting time. A server with an empty queue and a straggler in service is effectively unavailable, but a queue-length-only policy cannot distinguish it from a genuinely idle server.

This uncertainty is fundamental: no dispatcher with limited observability can fully account for it. What good policies can do is use richer signals (job age, queue length combined) to make better-informed decisions most of the time.

### Which strategy performs best and why?

No single strategy dominates across all conditions. The key findings are:

- **At `α <= 1.15` with low load:** Power-of-Two performs comparably to JSQ.
- **At `α <= 1.15` with high load:** JSQ and Age-Aware JSQ outperform Power-of-Two, suggesting the `α` threshold for switching strategies should be tuned more carefully - or that at high load even the most extreme tail regime benefits from a full server scan.
- **At `1.15 < α <= 1.5`:** Age-Aware JSQ and JSQ perform similarly and both substantially outperform random. The age signal provides a useful margin when the tail is moderately heavy.
- **At `α > 1.5`:** All queue-aware strategies, including JSQ, converge to similar performance, and the advantage over random is minimal.

The Alpha-and-Load-Based dispatcher successfully captures most of these gains across the full parameter space. Its main identified weakness - Power-of-Two underperforming at `α = 1.1` under high load - could be addressed in at least two ways. The first is incorporating `λ` into the threshold logic, switching to JSQ at high load even when `α <= 1.15`. The second, and arguably more nuanced, approach would be to replace Power-of-Two with Age-Aware JSQ at very low `α`, but using a very small `age_weight`. The intuition is that when `α` is near `1`, stragglers are so extreme that even a tiny age penalty is enough to steer the dispatcher away from a server stuck on a multi-hour job, while a very small `age_weight` avoids over-penalizing servers that are simply running a moderately long but not catastrophic job. This would preserve the full-scan benefit of JSQ while keeping sensitivity to job age. Due to the computational cost of running `50,000`-job experiments across the full parameter grid, this variant was not evaluated empirically, but it remains a compelling direction for future tuning.

### How do stragglers affect system performance?

A straggler blocks all jobs queued behind it on the same server, effectively removing that server from the system for the duration of its execution. Under random dispatching, if one server catches a straggler, new jobs continue to be routed to it with probability `1/3`, compounding the backlog. Under queue-aware policies, the congestion is detected (via queue length or job age) and traffic is shifted to the other two servers until the straggler completes.

The server load plots at `α = 1.1` make this mechanism visible: the queue-aware dispatcher concentrates load on two servers while the third processes its straggler, resulting in unequal load but dramatically better response times for the majority of jobs.

---

## 7. Conclusion

This project demonstrates that dispatching policy has a significant impact on system performance under heavy-tailed workloads, and that the magnitude of this impact grows with both tail heaviness and arrival rate. A simple random policy, while easy to implement, leaves substantial performance on the table when `α` is small - in the most extreme cases, the difference in P99 response time between random and JSQ exceeds three orders of magnitude.

The Age-Aware JSQ, JSQ, and Power-of-Two dispatchers all substantially improve over the baseline in heavy-tailed regimes. The custom Alpha-and-Load-Based dispatcher adds a further layer of adaptability by selecting the appropriate sub-policy based on known workload characteristics. Its primary limitation - the choice of Power-of-Two at very heavy tails under high load - is a concrete direction for future refinement, specifically by conditioning the strategy selection on both `α` and `λ` jointly rather than on `α` alone.

Future extensions could also explore settings where `α` is not known in advance (requiring online estimation), limited observability scenarios, and replication or hedged request strategies to further reduce tail latency.

---

## Appendix: Figures

### All-Strategy Comparisons - Boxplots

| Figure | Description |
|---|---|
| A1 | Boxplot all strategies: `α=1.1`, `λ=0.3` |
| A2 | Boxplot all strategies: `α=1.1`, `λ=0.5` |
| A3 | Boxplot all strategies: `α=1.1`, `λ=0.7` |
| A4 | Boxplot all strategies: `α=1.3`, `λ=0.3` |
| A5 | Boxplot all strategies: `α=1.3`, `λ=0.5` |
| A6 | Boxplot all strategies: `α=1.3`, `λ=0.7` |
| A7 | Boxplot all strategies: `α=2.0`, `λ=0.3` |
| A8 | Boxplot all strategies: `α=2.0`, `λ=0.5` |
| A9 | Boxplot all strategies: `α=2.0`, `λ=0.7` |
| A10 | Boxplot all strategies: `α=2.5`, `λ=0.3` |
| A11 | Boxplot all strategies: `α=2.5`, `λ=0.5` |
| A12 | Boxplot all strategies: `α=2.5`, `λ=0.7` |

### All-Strategy Comparisons - CDFs

| Figure | Description |
|---|---|
| B1 | CDF all strategies: `α=1.1`, `λ=0.3` |
| B2 | CDF all strategies: `α=1.1`, `λ=0.5` |
| B3 | CDF all strategies: `α=1.1`, `λ=0.7` |
| B4 | CDF all strategies: `α=1.3`, `λ=0.3` |
| B5 | CDF all strategies: `α=1.3`, `λ=0.5` |
| B6 | CDF all strategies: `α=1.3`, `λ=0.7` |
| B7 | CDF all strategies: `α=2.0`, `λ=0.3` |
| B8 | CDF all strategies: `α=2.0`, `λ=0.5` |
| B9 | CDF all strategies: `α=2.0`, `λ=0.7` *(placeholder)* |
| B10 | CDF all strategies: `α=2.5`, `λ=0.3` *(placeholder)* |
| B11 | CDF all strategies: `α=2.5`, `λ=0.5` *(placeholder)* |
| B12 | CDF all strategies: `α=2.5`, `λ=0.7` *(placeholder)* |

### Random vs. Custom Dispatcher - Boxplots

| Figure | Description |
|---|---|
| C1–C12 | Boxplots `random` vs. `alpha_and_load_based` for all `(α, λ)` combinations |

### Random vs. Custom Dispatcher - CDFs

| Figure | Description |
|---|---|
| D1–D12 | CDFs `random` vs. `alpha_and_load_based` for all `(α, λ)` combinations |

### Server Load Distribution

| Figure | Description |
|---|---|
| E1 | Server load: `α=1.1`, `λ=0.3` |
| E2 | Server load: `α=1.1`, `λ=0.5` |
| E3 | Server load: `α=1.1`, `λ=0.7` |
| E4 | Server load: `α=1.3`, `λ=0.3` |
| E5 | Server load: `α=1.3`, `λ=0.5` |
| E6 | Server load: `α=1.3`, `λ=0.7` |
| E7 | Server load: `α=2.0`, `λ=0.3` |
| E8 | Server load: `α=2.0`, `λ=0.5` |
| E9 | Server load: `α=2.0`, `λ=0.7` |
| E10 | Server load: `α=2.5`, `λ=0.3` |
| E11 | Server load: `α=2.5`, `λ=0.5` |
| E12 | Server load: `α=2.5`, `λ=0.7` |

### Summary Table

| Figure | Description |
|---|---|
| F1 | Response time summary: mean, median, P90, P99 for all strategies and conditions |