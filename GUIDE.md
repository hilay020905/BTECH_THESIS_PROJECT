# Complete guide: reproducing the RevSCA-2.0 runs and the Figure-1-style graph on your own laptop

This covers two *separate* things we did, because they're different tools with different purposes:

1. **RevSCA-2.0** — the real, official verifier from the paper's authors. Gives you
   correctness + peak-polynomial-size stats on real large multipliers (16-bit to
   512-bit). No graph — just a text report per run.
2. **Our custom SCA engine** (`sca_repro_code/`) — what actually *produced the graph*
   (`figure1_reproduction.png`). It's a from-scratch reimplementation of the paper's
   backward-rewriting method, instrumented to log the monomial count at every single
   step, which RevSCA-2.0 does not do (it only reports the peak, `#MaxPoly`).

Do both if you want the full picture: RevSCA-2.0 for "does it verify, and how fast",
our code for "the actual step-by-step curve like Figure 1."

---

## Part 0 — Concepts, briefly

- **AIG (And-Inverter Graph)**: a circuit represented using only 2-input AND gates
  and inverters. It's the standard interchange format for gate-level formal
  verification tools (the `.aig` files in RevSCA-2.0's `Benchmarks/` folder).
- **PPG / PPA / FSA**: the three stages of a multiplier — Partial Product Generator
  (the AND gates that multiply each input bit pair), Partial Product Accumulator
  (adds up all the partial products, e.g. via a Wallace tree), Final Stage Adder
  (adds the last two numbers together to get the final result).
- **"Trivial" vs "non-trivial" multiplier** (paper's own terminology): trivial = the
  whole multiplier is built only from half-adders/full-adders (e.g. final stage is a
  plain ripple-carry adder). Non-trivial = the final stage uses a faster adder
  (carry-lookahead, Brent-Kung, etc.) that isn't just a chain of HA/FA.
- **SCA (Symbolic Computer Algebra) verification**: represent the circuit's expected
  behavior as one big polynomial (the "specification polynomial"), then repeatedly
  substitute each gate's output variable with an equivalent expression in terms of
  its inputs ("backward rewriting"), working from the outputs back to the primary
  inputs. If you end up with the polynomial `0`, the circuit is correct.
- **Monomial**: one term of that polynomial (e.g. `4*a1*b0`). The paper's Figure 1
  tracks *how many terms the polynomial has* at each substitution step — this is a
  direct measure of the peak memory the verification method needs.
- **Why trivial vs non-trivial matters**: for trivial multipliers, the polynomial
  stays small throughout (backward rewriting is well-behaved). For non-trivial ones,
  it can balloon into thousands/millions of terms mid-way before collapsing back to
  0 — that blow-up is exactly what limits scalability, and exactly what Figure 1
  shows.

---

## Part 1 — Running the official RevSCA-2.0 tool

RevSCA-2.0 ships as a prebuilt Linux x86-64 binary, so it needs a Linux environment.

### If you're on Linux
Nothing special needed, just a terminal.

### If you're on Windows
Install **WSL2** (Windows Subsystem for Linux) first:
```powershell
wsl --install
```
Reboot if prompted, then open the "Ubuntu" app from your Start menu — that gives you
a Linux terminal to run the rest of these commands in.

### If you're on macOS
The binary is Linux-only, so it won't run natively. Easiest options: a Docker
container running Ubuntu, or a free Linux VM (UTM, Multipass), or just do Part 2
only (the Python code is cross-platform and works fine on macOS directly).

### Steps (inside your Linux/WSL terminal)
```bash
git clone https://github.com/amahzoon/RevSCA-2.0.git
cd RevSCA-2.0
chmod +x revsca
./revsca                     # no args -> prints usage, confirms it runs
```

Run it on a benchmark (all of them live in `Benchmarks/unsigned_multipliers/` and
`Benchmarks/signed_multipliers/`, already named after the paper's own Table I rows):
```bash
./revsca Benchmarks/unsigned_multipliers/16bit-SP-WT-CL.aig out.txt -u
cat out.txt
```
`-u` = unsigned multiplier, `-s` = signed. Output file has run-time breakdown and
`#MaxPoly` (peak monomial count) — the closest single-number summary to what
Figure 1 plots as a full curve.

Try bigger ones as your RAM allows:
```bash
./revsca Benchmarks/unsigned_multipliers/64bit-SP-DT-LF.aig out64.txt -u
./revsca Benchmarks/unsigned_multipliers/128bit-SP-DT-LF.aig out128.txt -u
./revsca Benchmarks/unsigned_multipliers/256bit-SP-WT-BK.aig out256.txt -u   # needs several GB RAM
```
(In our sandbox, limited to ~4 GB RAM, 128-bit worked but 256-bit timed out and
512-bit ran out of memory. A modern laptop with 8–16 GB RAM should comfortably clear
128-bit and likely 256-bit; 512-bit is genuinely heavy even for the paper's own
32 GB test machine, per their reported ~827s run-time for it.)

---

## Part 2 — Generating the actual Figure-1-style graph

This is pure Python, and works the same on Windows, macOS, or Linux.

### Requirements
- Python 3.9+ 
- `sympy` and `matplotlib`

### Setup
```bash
python3 -m venv venv
# Windows:  venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install sympy matplotlib
```

### Get the code
Download the `sca_repro_code/` folder (attached alongside this guide) and `cd` into it.
It contains:
- `netlist.py` — builds the multiplier circuit (array PPG + Wallace-tree PPA +
  ripple-carry-adder "trivial" or full carry-lookahead "non-trivial" final stage),
  using only NOT/AND/OR/XOR gates.
- `simulate.py` — a numeric gate-level simulator, used to double-check the circuits
  actually compute correct multiplication before trusting the polynomial results.
- `sca_engine.py` — reference implementation of the paper's backward-rewriting
  method (Eq. 3/4) using sympy. Slower, but easy to read/audit.
- `fast_sca_engine.py` — same method, ~1000x faster (sparse polynomial
  representation exploiting that Boolean variables satisfy x²=x). Cross-validated
  against `sca_engine.py` — identical results on every case we checked.
- `run_and_plot.py` — the one-shot script that ties it together and makes the plot.

### Run it
```bash
python3 run_and_plot.py            # safe default: 2,3,4-bit, finishes in <1 second
```
This produces `results.json` (raw monomial-count-per-step data) and
`figure1_reproduction.png` (the graph, one panel per bit-width, trivial vs
non-trivial curves overlaid).

To push further (needs more RAM/time — non-trivial multipliers are the expensive
ones, exactly like in the paper):
```bash
python3 run_and_plot.py 4 8        # try 8-bit; may take a while / need several GB
python3 run_and_plot.py 4 8 16     # 16-bit non-trivial is genuinely heavy;
                                    # in our 4GB sandbox this didn't finish —
                                    # a laptop with more RAM has a real shot at it
```
It prints live progress every 100 substitution steps so you can watch it grow (or
stall) rather than wondering if it's hung.

### If 8-bit/16-bit non-trivial still doesn't finish on your machine
That's not a bug — it's the same wall the paper's authors hit with naive backward
rewriting, which is *why* they built RevSCA-2.0's optimized version (reverse
engineering + "local vanishing removal" to prune the polynomial as it grows,
instead of letting it balloon unchecked). If you want the actual large-scale
numbers rather than the full step-by-step curve, that's what Part 1 is for.

---

## Quick sanity check that both are working correctly
- RevSCA-2.0 should print `The multiplier is correct!` for every benchmark.
- `run_and_plot.py` prints `remainder_zero (correct) = True` for every case —
  this confirms the specification polynomial fully collapsed to 0, exactly the
  paper's own correctness criterion (Section II-B, "the multiplier is bug-free
  iff the remainder is zero").

If either ever reports "incorrect" or the remainder isn't 0, something's wrong
with the setup (wrong file, wrong `-u`/`-s` flag, or a bug) — the multipliers
themselves are provably correct constructions, so a non-zero remainder means an
error in how you're running it, not a real bug in the circuit.
