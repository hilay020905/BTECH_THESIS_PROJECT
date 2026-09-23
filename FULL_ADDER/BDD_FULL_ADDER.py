#!/usr/bin/env python3
"""
BDD-based formal verification of the FULL ADDER (Yosys AIG) and of n chained full adders.

  python3 -B BDD_FULL_ADDER.py FULL_ADDER.aag      -> verify your 1-bit full adder (.aag or .aig)
  python3 -B BDD_FULL_ADDER.py                     -> scaling: n = 1..128 full adders in a chain
  python3 -B BDD_FULL_ADDER.py 8 16 32             -> scaling for the widths you choose

Method: build ROBDDs (ITE) for every gate, then for the outputs; build a reference adder in the same
BDD manager; BDDs are canonical, so the circuit is correct iff the output BDDs are the SAME nodes.
Variable order: cin, a0, b0, a1, b1, ...
"""
import sys, os, re, time, threading, subprocess
sys.dont_write_bytecode = True

# ------------------------- AIGER parser (.aag / .aig) -------------------------
class AIG: pass

def _uvarint(d, p):
    x = s = 0
    while True:
        b = d[p]; p += 1
        x |= (b & 0x7F) << s
        if not b & 0x80: return x, p
        s += 7

def parse_aiger(path):
    d = open(path, "rb").read()
    nl = d.index(b"\n"); h = d[:nl].decode().split()
    g = AIG(); g.M, g.I, g.L, g.O, g.A = map(int, h[1:6])
    if g.L: raise ValueError("latches not supported")
    g.inputs, g.outputs, g.ands, g.in_names, g.out_names = [], [], [], {}, {}
    pos = nl + 1
    if h[0] == "aag":
        ln = d[pos:].decode().splitlines(); k = 0
        for _ in range(g.I): g.inputs.append(int(ln[k])); k += 1
        for _ in range(g.O): g.outputs.append(int(ln[k])); k += 1
        for _ in range(g.A): g.ands.append(tuple(map(int, ln[k].split()))); k += 1
        rest = ln[k:]
    else:
        g.inputs = [2 * (i + 1) for i in range(g.I)]
        for _ in range(g.O):
            e = d.index(b"\n", pos); g.outputs.append(int(d[pos:e])); pos = e + 1
        for i in range(g.A):
            lhs = 2 * (g.I + 1 + i)
            d0, pos = _uvarint(d, pos); d1, pos = _uvarint(d, pos)
            g.ands.append((lhs, lhs - d0, lhs - d0 - d1))
        rest = d[pos:].decode(errors="ignore").splitlines()
    for line in rest:
        if line.startswith("c"): break
        p = line.split(None, 1)
        if len(p) == 2 and p[0][0] in "io":
            (g.in_names if p[0][0] == "i" else g.out_names)[int(p[0][1:])] = p[1]
    g.ands.sort(key=lambda x: x[0])
    return g

def bus(names, base):
    found = {}
    for nm in names:
        m = re.fullmatch(re.escape(base) + r"\[(\d+)\]", nm)
        if m: found[int(m.group(1))] = nm
    return [found[i] for i in sorted(found)]

def detect(g):
    """Find the adder signals: a,b,cin -> s,cout | A,B,Ci -> Sum,Co | buses a[i],b[i],sum[i]."""
    in_name = {l >> 1: g.in_names.get(i, f"i{i}") for i, l in enumerate(g.inputs)}
    out = {g.out_names.get(i, f"o{i}"): l for i, l in enumerate(g.outputs)}
    names, onames = list(in_name.values()), list(out)
    A, B, S = bus(names, "a"), bus(names, "b"), bus(onames, "sum")
    if A: cin, cout = "cin", "cout"
    else:
        pick = lambda pool, c: next((x for x in pool if x.lower() in c), None)
        cin = pick(names, ("cin", "ci")); cout = pick(onames, ("cout", "co"))
        A, B, S = [pick(names, ("a",))], [pick(names, ("b",))], [pick(onames, ("s", "sum"))]
    assert A and len(A) == len(B) == len(S) and None not in A + B + S + [cin, cout], \
        "could not identify adder signals"
    return dict(n=len(A), A=A, B=B, S=S, cin=cin, cout=cout, in_name=in_name, out=out)

# ------------------------------- BDD package -------------------------------
class BDD:
    """ROBDD with unique table + computed table; ITE algorithm (Brace/Rudell/Bryant)."""
    def __init__(self, nvars):
        self.var = [nvars, nvars]; self.lo = [0, 1]; self.hi = [0, 1]      # ids 0,1 = terminals
        self.uniq, self.cache, self.calls = {}, {}, 0
    def mk(self, v, lo, hi):
        if lo == hi: return lo
        k = (v, lo, hi); r = self.uniq.get(k)
        if r is None:
            r = len(self.var); self.var.append(v); self.lo.append(lo); self.hi.append(hi); self.uniq[k] = r
        return r
    def ite(self, f, g, h):
        if f == 1: return g
        if f == 0: return h
        if g == h: return g
        if g == 1 and h == 0: return f
        k = (f, g, h); r = self.cache.get(k)
        if r is not None: return r
        self.calls += 1
        var, lo, hi = self.var, self.lo, self.hi
        v = min(var[f], var[g], var[h])
        t = self.ite(hi[f] if var[f] == v else f, hi[g] if var[g] == v else g, hi[h] if var[h] == v else h)
        e = self.ite(lo[f] if var[f] == v else f, lo[g] if var[g] == v else g, lo[h] if var[h] == v else h)
        r = self.mk(v, e, t); self.cache[k] = r
        return r
    def size(self, root):                       # nodes reachable from root (terminals included)
        seen, st = {root}, [root]
        while st:
            x = st.pop()
            if x > 1:
                for y in (self.lo[x], self.hi[x]):
                    if y not in seen: seen.add(y); st.append(y)
        return len(seen)

def _run_big(fn, *a):                           # ITE recursion is as deep as the number of variables
    sys.setrecursionlimit(1_000_000)
    threading.stack_size(256 * 1024 * 1024)
    res, exc = [], []
    def w():
        try: res.append(fn(*a))
        except BaseException as e: exc.append(e)
    t = threading.Thread(target=w); t.start(); t.join()
    if exc: raise exc[0]
    return res[0]

def _bdd_verify(g):
    d = detect(g); n = d["n"]
    order = [d["cin"]] + [x for i in range(n) for x in (d["A"][i], d["B"][i])]   # cin, a0, b0, a1, b1, ...
    lev = {nm: i for i, nm in enumerate(order)}
    m = BDD(len(order)); t0 = time.perf_counter()
    f = {v: m.mk(lev[nm], 0, 1) for v, nm in d["in_name"].items()}
    notc = {}
    def lit(l):
        if l < 2: return l
        x = f[l >> 1]
        if l & 1:
            r = notc.get(x)
            if r is None: r = notc[x] = m.ite(x, 0, 1)
            return r
        return x
    for lhs, a, b in g.ands: f[lhs >> 1] = m.ite(lit(a), lit(b), 0)          # AND = ITE(a, b, 0)
    # reference adder built with ITE in the same manager; BDDs are canonical -> compare node ids
    Aid = [m.mk(lev[x], 0, 1) for x in d["A"]]; Bid = [m.mk(lev[x], 0, 1) for x in d["B"]]
    c, ok = m.mk(lev[d["cin"]], 0, 1), True
    for i in range(n):
        p = m.ite(Aid[i], m.ite(Bid[i], 0, 1), Bid[i])                        # a xor b
        s = m.ite(p, m.ite(c, 0, 1), c)                                        # sum bit
        cy = m.ite(p, c, Aid[i])                                               # carry
        if lit(d["out"][d["S"][i]]) != s: ok = False
        c = cy
    if lit(d["out"][d["cout"]]) != c: ok = False
    return dict(ok=ok, n=n, time=time.perf_counter() - t0, nodes=len(m.var) - 2, ops=m.calls,
                cout_size=m.size(lit(d["out"][d["cout"]])))

def bdd_verify(g): return _run_big(_bdd_verify, g)

def scaling_table(make_aig, widths):
    print(f"{'n':>4} {'AND gates':>10} {'BDD nodes':>10} {'ITE ops':>9} {'cout BDD size':>14} {'3(n+1)':>7} {'time (s)':>9}  result")
    for n in widths:
        g = make_aig(n); r = bdd_verify(g)
        print(f"{n:>4} {g.A:>10} {r['nodes']:>10} {r['ops']:>9} {r['cout_size']:>14} {3*(n+1):>7} {r['time']:>9.4f}  {'VERIFIED' if r['ok'] else 'FAILED'}")

def single_file(path):
    g = parse_aiger(path); r = bdd_verify(g)
    print(f"Parsed {path}: inputs={g.I} outputs={g.O} AND gates={g.A}, adder width n={r['n']}")
    print(f"BDD verification : {'PASSED (circuit BDDs identical to reference adder BDDs)' if r['ok'] else 'FAILED (BDDs differ -> bug)'}")
    print(f"  BDD nodes created = {r['nodes']},  ITE operations = {r['ops']},  cout BDD size = {r['cout_size']},  time = {r['time']:.4f} s")

def yosys_aig(files, top, n, flow="proc; flatten; opt_clean; techmap; opt_clean; aigmap; opt_clean", out="tmp_bdd.aag"):
    script = (f"read_verilog {files}; chparam -set N {n} {top}; hierarchy -top {top}; {flow}; "
              f"write_aiger -ascii -symbols {out}")
    r = subprocess.run(["yosys", "-q", "-p", script], capture_output=True, text=True)
    if r.returncode != 0:
        print("\nYosys failed. Its message:\n" + (r.stderr or r.stdout)); sys.exit(1)
    return parse_aiger(out)

# Chain of n full adders built directly as an AIG (9 AND gates per full adder).
def build_chain(n):
    g = AIG(); g.ands = []; nxt = [1]
    def new():
        v = nxt[0]; nxt[0] += 1; return 2 * v
    A = [new() for _ in range(n)]; B = [new() for _ in range(n)]; cin = new()
    g.inputs = A + B + [cin]
    g.in_names = {i: f"a[{i}]" for i in range(n)}
    g.in_names.update({n + i: f"b[{i}]" for i in range(n)}); g.in_names[2 * n] = "cin"
    def AND(x, y): o = new(); g.ands.append((o, x, y)); return o
    def XOR(x, y):
        t1 = AND(x, y ^ 1) ^ 1; t2 = AND(x ^ 1, y) ^ 1
        return AND(t1, t2) ^ 1
    def OR(x, y): return AND(x ^ 1, y ^ 1) ^ 1
    outs, c = [], cin
    for i in range(n):
        p = XOR(A[i], B[i]); outs.append(XOR(p, c)); c = OR(AND(A[i], B[i]), AND(p, c))
    outs.append(c)
    g.outputs = outs; g.out_names = {i: f"sum[{i}]" for i in range(n)}; g.out_names[n] = "cout"
    g.I, g.O, g.A = len(g.inputs), len(outs), len(g.ands)
    return g

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0].lower().endswith((".aag", ".aig")): single_file(args[0])
    else: scaling_table(build_chain, [int(x) for x in args] or [1, 2, 4, 8, 16, 32, 64, 128, 256, 512])
