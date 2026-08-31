"""
Runs ONE (width, kind) case and checkpoints the monomial-count history to
a JSON file every `checkpoint_every` steps. Meant to be launched as its own
subprocess so that if the OS OOM-kills it (which happens for non-trivial
multipliers >= 8 bits — the polynomial genuinely blows up to millions of
monomials mid-verification, exactly like Fig. 1 in the paper), the
checkpoint file on disk still has whatever progress was made, instead of
losing everything.

Usage: python3 run_case.py <width> <trivial|nontrivial> <out_checkpoint.json> [checkpoint_every]
"""
import sys
import json
import time

from netlist import build_multiplier
import fast_sca_engine as E


def main():
    n = int(sys.argv[1])
    kind = sys.argv[2]
    out_path = sys.argv[3]
    checkpoint_every = int(sys.argv[4]) if len(sys.argv) > 4 else 25

    net, a, b, out = build_multiplier(n, kind)
    print(f"[{n}-bit {kind}] {len(net.gates)} gates", flush=True)

    SP = E.specification_polynomial(a, b, out)
    history = [E.monomial_count(SP)]
    steps_done = 0
    total_gates_used = sum(
        1 for (z, gtype, i1, i2) in net.gates if True
    )  # not used, just for info

    t0 = time.time()

    def dump(complete, correct=None):
        with open(out_path, "w") as f:
            json.dump(
                {
                    "width": n,
                    "kind": kind,
                    "gates": len(net.gates),
                    "history": history,
                    "steps_done": steps_done,
                    "complete": complete,
                    "correct": correct,
                    "elapsed_s": time.time() - t0,
                },
                f,
            )

    dump(complete=False)  # initial checkpoint before any work, in case of instant OOM

    for (z, gtype, i1, i2) in reversed(net.gates):
        used = any(z in mono for mono in SP)
        if not used:
            continue
        tail = E.gate_tail_poly(gtype, i1, i2)
        SP = E.substitute(SP, z, tail)
        steps_done += 1
        history.append(E.monomial_count(SP))
        if steps_done % checkpoint_every == 0:
            dump(complete=False)
            print(f"  step {steps_done}: {history[-1]} monomials "
                  f"(peak so far: {max(history)})", flush=True)

    ok = (SP == {})
    dump(complete=True, correct=ok)
    print(f"[{n}-bit {kind}] DONE in {time.time()-t0:.2f}s, "
          f"max monomials = {max(history)}, correct = {ok}", flush=True)


if __name__ == "__main__":
    main()
