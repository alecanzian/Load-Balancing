# server.py

import time
import random
import math
import multiprocessing as mp
from models import Server
from config import BASE_WORK


def process_request(x, alpha, base_work=BASE_WORK):
    multiplier = random.paretovariate(alpha)
    n = int(base_work * x * multiplier)
    acc = 0.0
    for i in range(n):
        acc += math.sin(i) * math.cos(i)
    return acc


def _server_loop(server_id, queue, result_queue, load, current_service_start, seed=None):
    try:
        if seed is not None:
            random.seed(seed)
        total_busy = 0.0
        start_time = None

        while True:
            job = queue.get()
            if job is None:
                break
            if start_time is None:
                start_time = time.time()   # start clock on first job, not at process start
            job['start_time'] = time.time()
            current_service_start.value = job['start_time']   # server is now busy
            process_request(job['x'], job['pareto_param'])
            job['finish_time'] = time.time()
            current_service_start.value = 0.0                 # server is now idle
            job['response_time'] = job['finish_time'] - job['joining_time']
            total_busy          += job['finish_time'] - job['start_time']
            result_queue.put(job)

        end_time      = time.time()
        total_elapsed = end_time - start_time if start_time else 1.0
        load.value    = total_busy / total_elapsed
    except KeyboardInterrupt:
        print(f"Server {server_id} interrupted by user. Shutting down...")
        time.sleep(0.7)


def make_server(server_id, seed=None):
    s = Server(server_id, seed)
    s.process = mp.Process(
        target=_server_loop,
        args=(server_id, s.queue, s.result_queue, s.load, s.current_service_start, s.seed),
        daemon=True
    )
    return s