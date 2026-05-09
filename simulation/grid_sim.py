"""
Queue-based simulation of the 2 x 2 grid used in the Semester 5 Webots world.

Geometry and the baseline follow webots/controllers/supervisor_controller.py:
four junctions at (+-25 m, +-25 m), vehicles enter at the eight outer
entrances and drive straight through two junctions, and the baseline is a
synchronised fixed-time cycle with 15 s green per axis. Webots moved the cars
and held them at stop lines; here each junction approach is a FIFO queue,
which makes waiting time, queue length and throughput directly measurable.

Time step 1 s. Per junction: two phases (NS green, EW green), 3 s yellow and
2 s all red between them (5 s of lost time per change, as at a real junction), a
2 s start-up loss when a green begins, then one vehicle discharged every 2 s
per approach (saturation flow 1,800 veh/h/lane). Travel time between the two
junctions on a street is 5 s (50 m at 10 m/s).
"""

from collections import deque
import numpy as np

DT = 1
HEADWAY = 2            # s between departures at saturation
STARTUP_LOSS = 2       # s lost when a green starts
YELLOW, ALL_RED = 3, 2
CLEARANCE = YELLOW + ALL_RED
LINK_TIME = 5          # s between junctions
FIXED_GREEN = 15       # Semester 5 baseline
MIN_GREEN, MAX_GREEN = 5, 40

JUNCTIONS = ["NW", "NE", "SW", "SE"]
# Eight streams: (entry name, direction, [junctions passed in order])
STREAMS = [
    ("E-top", "E", ["NW", "NE"]), ("E-bottom", "E", ["SW", "SE"]),
    ("W-top", "W", ["NE", "NW"]), ("W-bottom", "W", ["SE", "SW"]),
    ("N-left", "N", ["SW", "NW"]), ("N-right", "N", ["SE", "NE"]),
    ("S-left", "S", ["NW", "SW"]), ("S-right", "S", ["NE", "SE"]),
]
AXIS = {"N": "NS", "S": "NS", "E": "EW", "W": "EW"}

# Detector quality measured class-agnostically on the same 247 held-out BDD100K
# validation images (vision/evaluate_detectors.py, results/detector_comparison.csv),
# both at their count-optimal confidence threshold of 0.25.
DETECTORS = {
    "perfect": None,
    "yolo_v2": {"precision": 0.657, "recall": 0.545},   # baseline: 1-class model, 1,156 training images
    "yolo_v1": {"precision": 0.761, "recall": 0.660},   # improved: full-data model used class-agnostically
}


def observe(n, detector, rng):
    """Count a camera + detector would report for n queued vehicles.

    True vehicles are each found with probability = recall; false detections
    are added so that, on average, precision = TP / (TP + FP).
    """
    if detector is None or n == 0:
        return n
    tp = rng.binomial(n, detector["recall"])
    fp_mean = tp * (1 - detector["precision"]) / detector["precision"]
    return tp + rng.poisson(fp_mean)


class Junction:
    def __init__(self, name):
        self.name = name
        self.queues = {d: deque() for d in "NSEW"}      # vehicles waiting, by travel direction
        self.phase = "NS"                               # axis that has (or will get) green
        self.stage = "GREEN"
        self.t_stage = 0
        self.discharge_timer = {d: 0 for d in "NSEW"}
        self.green_seconds = {"NS": 0, "EW": 0}
        self.used_seconds = {"NS": 0, "EW": 0}
        self.next_phase = None

    def queue_len(self, axis):
        return sum(len(self.queues[d]) for d in "NSEW" if AXIS[d] == axis)


class GridSim:
    def __init__(self, arrivals, controller, detector="perfect", seed=0, horizon=3600, warmup=300):
        """arrivals: dict stream name -> sorted array of arrival times (s)."""
        self.arrivals = {k: deque(v) for k, v in arrivals.items()}
        self.controller = controller
        self.detector = DETECTORS[detector]
        self.rng = np.random.default_rng(seed + 10_000)
        self.horizon, self.warmup = horizon, warmup
        self.J = {n: Junction(n) for n in JUNCTIONS}
        self.in_transit = []                    # (arrival_time, vehicle, junction)
        self.completed = []                     # total delay of vehicles that left the grid
        self.queue_trace = []
        self.exits = 0

    # ---------------------------------------------------------------- control
    def decide(self, j, t):
        """Return the axis this junction wants green now."""
        if self.controller == "fixed":
            cycle = 2 * (FIXED_GREEN + CLEARANCE)
            return "NS" if (t % cycle) < FIXED_GREEN + CLEARANCE else "EW"

        green_for = t - j.t_stage
        if green_for < MIN_GREEN:
            return j.phase
        if green_for >= MAX_GREEN:
            return "EW" if j.phase == "NS" else "NS"
        cur, oth = j.phase, ("EW" if j.phase == "NS" else "NS")

        if self.controller == "adaptive":
            q_cur = sum(observe(len(j.queues[d]), self.detector, self.rng) for d in "NSEW" if AXIS[d] == cur)
            q_oth = sum(observe(len(j.queues[d]), self.detector, self.rng) for d in "NSEW" if AXIS[d] == oth)
            return oth if q_oth > q_cur + 2 else cur

        if self.controller == "max_pressure":
            def pressure(axis):
                p = 0
                for d in "NSEW":
                    if AXIS[d] != axis:
                        continue
                    up = observe(len(j.queues[d]), self.detector, self.rng)
                    down_j = self.downstream(j.name, d)
                    down = observe(len(down_j.queues[d]), self.detector, self.rng) if down_j else 0
                    p += up - down
                return p
            return oth if pressure(oth) > pressure(cur) + 2 else cur
        raise ValueError(self.controller)

    def downstream(self, jname, direction):
        for _, d, path in STREAMS:
            if d == direction and jname in path:
                i = path.index(jname)
                return self.J[path[i + 1]] if i + 1 < len(path) else None
        return None

    # ---------------------------------------------------------------- run
    def run(self):
        stream_info = {name: (d, path) for name, d, path in STREAMS}
        for t in range(self.horizon):
            # 1. new vehicles enter at the outer edge of the grid
            for name, q in self.arrivals.items():
                while q and q[0] <= t:
                    q.popleft()
                    d, path = stream_info[name]
                    veh = {"dir": d, "path": path, "leg": 0, "delay": 0, "t0": t}
                    self.J[path[0]].queues[d].append(veh)
            # 2. vehicles finishing the 50 m link join the next queue
            still = []
            for (ta, veh, jn) in self.in_transit:
                if ta <= t:
                    self.J[jn].queues[veh["dir"]].append(veh)
                else:
                    still.append((ta, veh, jn))
            self.in_transit = still

            # 3. signals and discharge
            for j in self.J.values():
                self.step_junction(j, t)

            # 4. waiting vehicles accumulate delay
            total_q = 0
            for j in self.J.values():
                for d in "NSEW":
                    for veh in j.queues[d]:
                        veh["delay"] += DT
                    total_q += len(j.queues[d])
            self.queue_trace.append(total_q)
        return self.metrics()

    def step_junction(self, j, t):
        if j.stage == "GREEN":
            want = self.decide(j, t)
            if want != j.phase:
                j.stage, j.t_stage, j.next_phase = "CLEAR", t, want
            else:
                green_for = t - j.t_stage
                if t >= self.warmup:
                    j.green_seconds[j.phase] += 1
                if green_for >= STARTUP_LOSS:
                    used = False
                    for d in "NSEW":
                        if AXIS[d] != j.phase or not j.queues[d]:
                            continue
                        j.discharge_timer[d] -= DT
                        if j.discharge_timer[d] <= 0:
                            veh = j.queues[d].popleft()
                            j.discharge_timer[d] = HEADWAY
                            used = True
                            self.depart(veh, j, t)
                    if used and t >= self.warmup:
                        j.used_seconds[j.phase] += 1
        elif j.stage == "CLEAR" and t - j.t_stage >= CLEARANCE:
            j.stage, j.phase, j.t_stage = "GREEN", j.next_phase, t
            for d in "NSEW":
                j.discharge_timer[d] = 0

    def depart(self, veh, j, t):
        veh["leg"] += 1
        if veh["leg"] < len(veh["path"]):
            self.in_transit.append((t + LINK_TIME, veh, veh["path"][veh["leg"]]))
        else:
            if veh["t0"] >= self.warmup:
                self.completed.append(veh["delay"])
            if t >= self.warmup:
                self.exits += 1

    def metrics(self):
        dur_h = (self.horizon - self.warmup) / 3600
        green = sum(sum(j.green_seconds.values()) for j in self.J.values())
        used = sum(sum(j.used_seconds.values()) for j in self.J.values())
        q = np.array(self.queue_trace[self.warmup:])
        return {
            "avg_delay_s": float(np.mean(self.completed)) if self.completed else float("nan"),
            "p95_delay_s": float(np.percentile(self.completed, 95)) if self.completed else float("nan"),
            "avg_queue_veh": float(q.mean()),
            "max_queue_veh": int(q.max()),
            "throughput_veh_per_h": self.exits / dur_h,
            "green_utilisation": used / green if green else float("nan"),
            "left_in_network": int(sum(sum(len(x) for x in j.queues.values()) for j in self.J.values())
                                   + len(self.in_transit)),
        }


def make_arrivals(rates, horizon, seed):
    """Poisson arrivals. rates: dict stream -> function(t) giving veh/s (piecewise constant)."""
    rng = np.random.default_rng(seed)
    out = {}
    for name, _, _ in STREAMS:
        times, t = [], 0.0
        lam_max = max(rates[name](s) for s in range(0, horizon, 60))
        while True:                                  # thinning for time-varying rates
            t += rng.exponential(1 / lam_max)
            if t >= horizon:
                break
            if rng.random() < rates[name](t) / lam_max:
                times.append(t)
        out[name] = np.array(times)
    return out
