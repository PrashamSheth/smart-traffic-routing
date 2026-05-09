"""
Compare signal control strategies on the 2 x 2 grid and write the graphs.

    python run_experiments.py

Every controller sees exactly the same random arrivals (same seeds), so the
differences come from the control strategy only. Outputs:
    results/per_run.csv, results/summary.csv
    ../assets/graphs/*.png
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from grid_sim import GridSim, make_arrivals, STREAMS, DETECTORS

HORIZON, WARMUP, SEEDS = 3600, 300, list(range(10))
HERE = os.path.dirname(os.path.abspath(__file__))
GRAPHS = os.path.join(HERE, "..", "assets", "graphs")
RESULTS = os.path.join(HERE, "results")


def const(v):
    return lambda t: v


def scenario_rates(name):
    """Arrival rate (veh/s) for each of the 8 entry streams."""
    ns = [s for s, d, _ in STREAMS if d in "NS"]
    if name == "light":
        return {s: const(0.05) for s, _, _ in STREAMS}
    if name == "moderate":
        return {s: const(0.10) for s, _, _ in STREAMS}
    if name == "unbalanced":
        return {s: const(0.04 if s in ns else 0.20) for s, _, _ in STREAMS}
    if name == "shifting_peak":
        return {s: (lambda t, n=(s in ns): (0.18 if t < 1800 else 0.05) if n else (0.05 if t < 1800 else 0.18))
                for s, _, _ in STREAMS}
    raise ValueError(name)


SCENARIOS = ["light", "moderate", "unbalanced", "shifting_peak"]
SCEN_LABEL = {"light": "Light\n(180 veh/h per entry)", "moderate": "Moderate\n(360 veh/h per entry)",
              "unbalanced": "Unbalanced\n(E-W 720, N-S 144 veh/h)",
              "shifting_peak": "Shifting peak\n(N-S then E-W heavy)"}
CONFIGS = [("fixed", "perfect"),
           ("adaptive", "perfect"), ("adaptive", "yolo_v2"), ("adaptive", "yolo_v1"),
           ("max_pressure", "perfect"), ("max_pressure", "yolo_v2"), ("max_pressure", "yolo_v1")]
CFG_LABEL = {("fixed", "perfect"): "Fixed time 15 s / 15 s (Sem 5 baseline)",
             ("adaptive", "perfect"): "Adaptive, exact counts",
             ("adaptive", "yolo_v2"): "Adaptive, baseline detector counts (v2)",
             ("adaptive", "yolo_v1"): "Adaptive, improved detector counts (v1)",
             ("max_pressure", "perfect"): "Max-pressure, exact counts",
             ("max_pressure", "yolo_v2"): "Max-pressure, baseline detector counts (v2)",
             ("max_pressure", "yolo_v1"): "Max-pressure, improved detector counts (v1)"}
COLOURS = {("fixed", "perfect"): "#7f7f7f",
           ("adaptive", "perfect"): "#1f77b4", ("adaptive", "yolo_v1"): "#6baed6", ("adaptive", "yolo_v2"): "#c6dbef",
           ("max_pressure", "perfect"): "#d62728", ("max_pressure", "yolo_v1"): "#fb6a4a",
           ("max_pressure", "yolo_v2"): "#fcbba1"}


def main():
    os.makedirs(GRAPHS, exist_ok=True)
    os.makedirs(RESULTS, exist_ok=True)
    rows, traces, green_share = [], {}, {}
    for scen in SCENARIOS:
        for seed in SEEDS:
            arrivals = make_arrivals(scenario_rates(scen), HORIZON, seed)
            for ctrl, det in CONFIGS:
                sim = GridSim(arrivals, ctrl, det, seed=seed, horizon=HORIZON, warmup=WARMUP)
                m = sim.run()
                ew_green = sum(j.green_seconds["EW"] for j in sim.J.values())
                all_green = sum(sum(j.green_seconds.values()) for j in sim.J.values())
                m["ew_green_share"] = ew_green / all_green
                m["arrivals"] = int(sum(len(v) for v in arrivals.values()))
                rows.append({"scenario": scen, "seed": seed, "controller": ctrl, "counts": det, **m})
                if seed == 0:
                    traces[(scen, ctrl, det)] = np.array(sim.queue_trace)
        print("done", scen)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS, "per_run.csv"), index=False)
    cols = ["avg_delay_s", "p95_delay_s", "avg_queue_veh", "throughput_veh_per_h",
            "green_utilisation", "ew_green_share", "left_in_network"]
    summary = df.groupby(["scenario", "controller", "counts"])[cols].agg(["mean", "std"])
    summary.columns = [f"{a}_{b}" for a, b in summary.columns]
    summary = summary.reset_index()
    summary.to_csv(os.path.join(RESULTS, "summary.csv"), index=False, float_format="%.3f")

    pd.set_option("display.width", 200)
    show = summary[["scenario", "controller", "counts", "avg_delay_s_mean", "avg_delay_s_std",
                    "avg_queue_veh_mean", "throughput_veh_per_h_mean", "green_utilisation_mean",
                    "ew_green_share_mean", "left_in_network_mean"]]
    print(show.round(2).to_string(index=False))

    def get(scen, cfg, col):
        r = summary[(summary.scenario == scen) & (summary.controller == cfg[0]) & (summary.counts == cfg[1])]
        return float(r[f"{col}_mean"].iloc[0]), float(r[f"{col}_std"].iloc[0])

    # ---- 1. average waiting time per vehicle -------------------------------------------
    main_cfgs = [("fixed", "perfect"), ("adaptive", "perfect"), ("max_pressure", "perfect")]
    x = np.arange(len(SCENARIOS)); w = 0.26
    fig, ax = plt.subplots(figsize=(11, 5))
    for i, cfg in enumerate(main_cfgs):
        m = [get(s, cfg, "avg_delay_s") for s in SCENARIOS]
        ax.bar(x + (i - 1) * w, [a for a, _ in m], w, yerr=[b for _, b in m], capsize=3,
               color=COLOURS[cfg], label=CFG_LABEL[cfg])
    ax.set_xticks(x); ax.set_xticklabels([SCEN_LABEL[s] for s in SCENARIOS])
    ax.set_ylabel("Average waiting time per vehicle (s)")
    ax.set_title("Average waiting time: fixed-time baseline vs adaptive control (simulated, 10 seeds each)")
    ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(GRAPHS, "average_waiting_time.png"), dpi=130)

    # ---- 2. queue length over time -------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6), sharey=True)
    for ax, scen in zip(axes, ["unbalanced", "shifting_peak"]):
        for cfg in main_cfgs:
            tr = traces[(scen, cfg[0], cfg[1])]
            sm = pd.Series(tr).rolling(60, min_periods=1).mean()
            ax.plot(np.arange(len(tr)) / 60, sm, color=COLOURS[cfg], lw=2, label=CFG_LABEL[cfg])
        ax.axvspan(0, WARMUP / 60, color="grey", alpha=0.1, label="Warm-up (not scored)")
        ax.set_title(f"{SCEN_LABEL[scen].splitlines()[0]} demand (seed 0)")
        ax.set_xlabel("Time (min)")
    axes[0].set_ylabel("Vehicles queued in the grid (1-min average)")
    axes[1].legend(fontsize=8)
    fig.suptitle("Queue length over time (simulated)")
    fig.tight_layout(); fig.savefig(os.path.join(GRAPHS, "queue_length_over_time.png"), dpi=130)

    # ---- 3. throughput --------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for i, cfg in enumerate(main_cfgs):
        m = [get(s, cfg, "throughput_veh_per_h") for s in SCENARIOS]
        ax.bar(x + (i - 1) * w, [a for a, _ in m], w, yerr=[b for _, b in m], capsize=3,
               color=COLOURS[cfg], label=CFG_LABEL[cfg])
    demand = [df[(df.scenario == s) & (df.controller == "fixed")]["arrivals"].mean() for s in SCENARIOS]
    ax.scatter(x, [d * 3600 / HORIZON for d in demand], marker="_", s=900, color="black", zorder=3,
               label="Vehicles arriving per hour (demand)")
    ax.set_xticks(x); ax.set_xticklabels([SCEN_LABEL[s] for s in SCENARIOS])
    ax.set_ylabel("Vehicles leaving the grid per hour")
    ax.set_title("Throughput under different traffic conditions (simulated)")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(os.path.join(GRAPHS, "throughput.png"), dpi=130)

    # ---- 4. signal time allocation and utilisation ----------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for i, cfg in enumerate(main_cfgs):
        m = [get(s, cfg, "ew_green_share") for s in SCENARIOS]
        axes[0].bar(x + (i - 1) * w, [100 * a for a, _ in m], w, color=COLOURS[cfg], label=CFG_LABEL[cfg])
        u = [get(s, cfg, "green_utilisation") for s in SCENARIOS]
        axes[1].bar(x + (i - 1) * w, [100 * a for a, _ in u], w, color=COLOURS[cfg], label=CFG_LABEL[cfg])
    for ax in axes:
        ax.set_xticks(x); ax.set_xticklabels([SCEN_LABEL[s].splitlines()[0] for s in SCENARIOS])
    axes[0].axhline(50, color="black", lw=0.8, ls=":")
    axes[0].set_ylabel("% of green time given to East-West")
    axes[0].set_title("Green time allocation")
    axes[1].set_ylabel("% of green seconds that discharged a vehicle")
    axes[1].set_title("Green time utilisation")
    axes[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(GRAPHS, "signal_allocation_and_utilisation.png"), dpi=130)

    # ---- 5. effect of vehicle-count accuracy (detector) -------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=False)
    for ax, ctrl in zip(axes, ["adaptive", "max_pressure"]):
        cfgs = [("fixed", "perfect"), (ctrl, "perfect"), (ctrl, "yolo_v1"), (ctrl, "yolo_v2")]
        ww = 0.2
        for i, cfg in enumerate(cfgs):
            m = [get(s, cfg, "avg_delay_s") for s in SCENARIOS]
            ax.bar(x + (i - 1.5) * ww, [a for a, _ in m], ww, yerr=[b for _, b in m], capsize=2,
                   color=COLOURS[cfg], label=CFG_LABEL[cfg])
        ax.set_xticks(x); ax.set_xticklabels([SCEN_LABEL[s].splitlines()[0] for s in SCENARIOS])
        ax.set_ylabel("Average waiting time (s)")
        ax.set_title(f"{'Queue-based adaptive' if ctrl == 'adaptive' else 'Max-pressure'} control: "
                     f"exact vs detector-based counts")
        ax.legend(fontsize=8)
    fig.suptitle("Baseline vs improved detector: how vehicle-count accuracy changes waiting time (simulated)")
    fig.tight_layout(); fig.savefig(os.path.join(GRAPHS, "detector_accuracy_effect.png"), dpi=130)

    # ---- 6. traffic volume per entry ---------------------------------------------------------
    vol = {}
    for scen in SCENARIOS:
        arr = make_arrivals(scenario_rates(scen), HORIZON, 0)
        vol[scen] = [len(arr[s]) for s, _, _ in STREAMS]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ww = 0.2
    xs = np.arange(len(STREAMS))
    for i, scen in enumerate(SCENARIOS):
        ax.bar(xs + (i - 1.5) * ww, vol[scen], ww, label=SCEN_LABEL[scen].splitlines()[0])
    ax.set_xticks(xs); ax.set_xticklabels([s for s, _, _ in STREAMS])
    ax.set_ylabel("Vehicles in one hour (seed 0)")
    ax.set_title("Randomized traffic volume per entry lane (Poisson arrivals)")
    ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(GRAPHS, "traffic_volume_by_lane.png"), dpi=130)
    print("graphs written to", os.path.abspath(GRAPHS))


if __name__ == "__main__":
    main()
