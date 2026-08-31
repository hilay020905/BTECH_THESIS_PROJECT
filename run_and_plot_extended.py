"""
Extended version of run_and_plot.py that adds 8-bit and 16-bit to the
figure, and is robust to the fact that non-trivial multipliers at these
sizes can genuinely exhaust available RAM mid-run (this is not a bug --
it's the exact scalability wall the paper's Figure 1 is illustrating).

Each (width, kind) case runs in its own subprocess via run_case.py, which
checkpoints its monomial-count history to disk every N steps. If a case
gets killed (OOM) or times out, we still have its last checkpoint and plot
it as a dashed/truncated curve, clearly labeled as incomplete.

Usage:
    python3 run_and_plot_extended.py                     # widths 2,3,4,8,16
    python3 run_and_plot_extended.py 2 3 4 8 16           # same, explicit
    python3 run_and_plot_extended.py --timeout 300 4 8 16 # custom per-case timeout (s)
"""
import sys
import os
import json
import time
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CKPT_DIR = "checkpoints"


def run_case(n, kind, timeout_s):
    os.makedirs(CKPT_DIR, exist_ok=True)
    ckpt_path = os.path.join(CKPT_DIR, f"{n}_{kind}.json")
    print(f"\n=== Running {n}-bit {kind} (timeout {timeout_s}s) ===")
    try:
        subprocess.run(
            [sys.executable, "run_case.py", str(n), kind, ckpt_path, "25"],
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"  -> timed out after {timeout_s}s, using last checkpoint")

    if not os.path.exists(ckpt_path):
        print("  -> no checkpoint written (killed before first save)")
        return {"width": n, "kind": kind, "history": [], "complete": False,
                "correct": None, "gates": None}

    with open(ckpt_path) as f:
        data = json.load(f)
    status = "COMPLETE" if data["complete"] else "PARTIAL (killed/timed out)"
    print(f"  -> {status}: {len(data['history'])} steps logged, "
          f"peak = {max(data['history']) if data['history'] else 0} monomials")
    return data


def main():
    args = sys.argv[1:]
    timeout_s = 240
    if "--timeout" in args:
        i = args.index("--timeout")
        timeout_s = int(args[i + 1])
        del args[i:i + 2]
    widths = [int(x) for x in args] or [2, 3, 4, 8, 16]

    results = {}
    for n in widths:
        for kind in ["trivial", "nontrivial"]:
            data = run_case(n, kind, timeout_s)
            results[f"{n}_{kind}"] = data

    with open("results_extended.json", "w") as f:
        json.dump(results, f, indent=2)

    n_plots = len(widths)
    fig, axes = plt.subplots(1, n_plots, figsize=(5 * n_plots, 4), squeeze=False)
    axes = axes[0]
    for ax, n in zip(axes, widths):
        for kind, color in [("trivial", "blue"), ("nontrivial", "red")]:
            d = results[f"{n}_{kind}"]
            hist = d["history"]
            if not hist:
                continue
            style = "-" if d["complete"] else "--"
            label = f"{n}-bit {kind} mult" + ("" if d["complete"] else " (truncated: OOM/timeout)")
            ax.plot(range(len(hist)), hist, style, label=label, color=color)
        ax.set_xlabel("Substitution step")
        ax.set_ylabel("Number of monomials")
        ax.set_yscale("log")
        ax.set_title(f"{n}-bit multipliers")
        ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig("figure1_extended.png", dpi=150)
    print("\nSaved results_extended.json and figure1_extended.png")


if __name__ == "__main__":
    main()
