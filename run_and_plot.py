"""
One-shot script: build trivial vs non-trivial multipliers for a list of
bit-widths, run SCA backward rewriting, log monomial counts, and plot --
reproducing the style of Figure 1 in the ICCAD'22 paper.

Usage:
    python run_and_plot.py            # runs n = 2,3,4 (safe on any machine)
    python run_and_plot.py 4 8        # runs n = 4 and 8 (needs a few GB RAM)
    python run_and_plot.py 4 8 16     # needs a lot of RAM/time for 16-nontrivial
"""
import sys
import json
import time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from netlist import build_multiplier
from fast_sca_engine import backward_rewrite


def main():
    widths = [int(x) for x in sys.argv[1:]] or [2, 3, 4]
    results = {}

    for n in widths:
        for kind in ["trivial", "nontrivial"]:
            print(f"Building {n}-bit {kind} multiplier...")
            net, a, b, out = build_multiplier(n, kind)
            print(f"  {len(net.gates)} gates. Running backward rewriting...")
            t0 = time.time()
            hist, SP = backward_rewrite(net, a, b, out, progress_every=100)
            t1 = time.time()
            ok = (SP == {})
            print(f"  done in {t1-t0:.2f}s, max monomials = {max(hist)}, "
                  f"remainder_zero (correct) = {ok}")
            results[f"{n}_{kind}"] = {"history": hist, "gates": len(net.gates), "correct": ok}

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)

    n_plots = len(widths)
    fig, axes = plt.subplots(1, n_plots, figsize=(5 * n_plots, 4), squeeze=False)
    axes = axes[0]
    for ax, n in zip(axes, widths):
        trivial = results[f"{n}_trivial"]["history"]
        nontrivial = results[f"{n}_nontrivial"]["history"]
        ax.plot(range(len(trivial)), trivial, label=f"{n}-bit trivial mult", color="blue")
        ax.plot(range(len(nontrivial)), nontrivial, label=f"{n}-bit non-trivial mult", color="red")
        ax.set_xlabel("Substitution step")
        ax.set_ylabel("Number of monomials")
        ax.set_title(f"{n}-bit multipliers")
        ax.legend()
    plt.tight_layout()
    plt.savefig("figure1_reproduction.png", dpi=150)
    print("\nSaved results.json and figure1_reproduction.png")


if __name__ == "__main__":
    main()
