# dispatcher.py

import random
import time
import numpy as np
from queue import Empty

from models import Job
from server import make_server


# ====================================================
# DISPATCHING STRATEGIES
# ====================================================

class Dispatcher:
    """Base class — all strategies must implement dispatch()."""
    def dispatch(self, job, servers):
        raise NotImplementedError


class RandomDispatcher(Dispatcher):
    def dispatch(self, job, servers):
        return random.randrange(len(servers))

    def __repr__(self):
        return "RandomDispatcher"


class RoundRobinDispatcher(Dispatcher):
    def __init__(self, counter=0):
        self.counter = counter

    def dispatch(self, job, servers):
        idx = self.counter % len(servers)
        self.counter += 1
        return idx

    def __repr__(self):
        return f"RoundRobinDispatcher(counter={self.counter})"


class JSQDispatcher(Dispatcher):
    """Join Shortest Queue — pick server with fewest pending jobs."""
    def dispatch(self, job, servers):
        queue_lens = [s.queue.qsize() for s in servers]
        min_len = min(queue_lens)
        candidates = [i for i, l in enumerate(queue_lens) if l == min_len]
        return random.choice(candidates)

    def __repr__(self):
        return "JSQDispatcher"


class JIQDispatcher(Dispatcher):
    """Join Idle Queue — pick an idle server, fall back to random."""
    def dispatch(self, job, servers):
        for i, s in enumerate(servers):
            if s.queue.empty():
                return i
        return random.randrange(len(servers))

    def __repr__(self):
        return "JIQDispatcher"


class PowerOfTwoDispatcher(Dispatcher):
    """Sample 2 random servers, pick the one with the shorter queue."""
    def dispatch(self, job, servers):
        idxs = random.sample(range(len(servers)), 2)
        queue_lens = [servers[i].queue.qsize() for i in idxs]
        return idxs[queue_lens.index(min(queue_lens))]

    def __repr__(self):
        return "PowerOfTwoDispatcher"


class AgeAwareJSQDispatcher(Dispatcher):
    """JSQ weighted by age of current job in service."""
    def __init__(self, age_weight=1.0):
        self.age_weight = age_weight

    def dispatch(self, job, servers):
        scores = [s.queue.qsize() + self.age_weight * get_age(s) for s in servers]
        min_score = min(scores)
        candidates = [i for i, sc in enumerate(scores) if sc == min_score]
        return random.choice(candidates)

    def __repr__(self):
        return f"AgeAwareJSQDispatcher(age_weight={self.age_weight})"


def get_age(server):
    t = server.current_service_start.value
    return (time.time() - t) if t > 0 else 0.0


def _age_weight_empirical(alpha):
    """Age weight growing continuously from 0.001 (alpha=1.1) to 1.0 (alpha>=2.0).
    """
    if alpha >= 2.0:
        return 1.0
    t = (alpha - 1.1) / (2.0 - 1.1)
    return 10 ** (-3 + 3 * t)


AVAILABLE_STRATEGIES = [
    "random", "round_robin", "jsq", "jiq",
    "power_of_two", "age_aware_jsq", "age_aware_empirical_jsq",
]


def make_dispatcher(name, alpha):
    """Instantiate a fresh dispatcher for one experiment.

    A new instance per experiment avoids state leaking across runs
    (e.g. the round-robin counter).
    """
    if name == "random":
        return RandomDispatcher()
    if name == "round_robin":
        return RoundRobinDispatcher()
    if name == "jsq":
        return JSQDispatcher()
    if name == "jiq":
        return JIQDispatcher()
    if name == "power_of_two":
        return PowerOfTwoDispatcher()
    if name == "age_aware_jsq":
        return AgeAwareJSQDispatcher()
    if name == "age_aware_empirical_jsq":
        return AgeAwareJSQDispatcher(age_weight=_age_weight_empirical(alpha))
    raise ValueError(f"Unknown strategy '{name}'. Available: {AVAILABLE_STRATEGIES}")


# ====================================================
# MAIN EXPERIMENT FUNCTION
# ====================================================

def run_experiment(pareto_param, load_rate, n_jobs, time_scale, strategy, seed=None):
    """Generate arrivals, route jobs to servers, collect results."""
    dispatcher = make_dispatcher(strategy, pareto_param)

    if seed is not None:
        random.seed(seed)
        rng = np.random.default_rng(seed)
    else:
        rng = np.random.default_rng()

    print(f"Experiment -> load: {load_rate}  alpha: {pareto_param}  "
          f"dispatcher: {dispatcher}  n_jobs: {n_jobs}  seed: {seed}")

    servers = [make_server(i, seed=seed + i if seed is not None else None) for i in range(3)]
    for s in servers:
        s.process.start()

    for _ in range(n_jobs):
        interarrival_time = rng.exponential(scale=1.0 / load_rate) * time_scale
        time.sleep(max(0, interarrival_time))

        x = rng.uniform(0.5, 2.0)
        job = Job(joining_time=0.0, x=x, pareto_param=pareto_param)
        idx = dispatcher.dispatch(job, servers)

        job['joining_time'] = time.time()
        servers[idx].queue.put(job)

    for s in servers:
        s.queue.put(None)

    jobs = []
    try:
        while any(s.process.is_alive() or not s.result_queue.empty() for s in servers):
            for s in servers:
                try:
                    result = s.result_queue.get(timeout=0.01)
                    jobs.append(result)
                except Empty:
                    continue
    except KeyboardInterrupt:
        print("Experiment interrupted by user. Shutting down servers...")
        time.sleep(0.7)

    return jobs, servers