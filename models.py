# models.py

import multiprocessing as mp

_manager = None

def get_manager():
    """Single shared Manager for all queues (instead of one per queue).

    Manager queues support qsize() on macOS too, unlike raw mp.Queue.
    """
    global _manager
    if _manager is None:
        _manager = mp.Manager()
    return _manager


def Job(joining_time, x, pareto_param):
    """Job represented as a plain dict for simplicity."""
    return {
        'joining_time':  joining_time,
        'x':             x,
        'pareto_param':  pareto_param,
        'start_time':    None,
        'finish_time':   None,
        'response_time': None,
    }


class Server:
    def __init__(self, server_id, seed=None):
        m = get_manager()
        self.server_id             = server_id
        self.seed                  = int(seed) if seed is not None else None
        self.queue                 = m.Queue()
        self.result_queue          = m.Queue()
        self.load                  = mp.Value('d', 0.0)  # written by server, read at the end
        self.current_service_start = mp.Value('d', 0.0)  # 0.0 means idle
        self.process               = None                # assigned by server.make_server