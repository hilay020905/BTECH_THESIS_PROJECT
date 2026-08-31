"""
Gate-level multiplier netlist builder.

Only primitive gates used are NOT / AND / OR / XOR — the exact gate set
whose polynomials are given explicitly in the paper (Eq. 3/4 of the
ICCAD'22 "Polynomial Formal Verification..." paper, and Eq. 3 of the
DDECS/BTP paper). Half-adders and full-adders are *not* primitives here;
they are built out of these four gates, again exactly as the paper does
it (see Fig. 2 / half-adder equations).

ASSUMPTIONS (paper does NOT specify exact circuit topology, only the
three-stage structure PPG -> PPA -> FSA, so these choices are ours):
  - PPG: simple partial product generator (AND gates), matching the
    "SP" architecture label used throughout the paper's Table I.
  - PPA: Wallace-tree-style column compression using HA/FA (3:2 and 2:1
    compressors), matching "WT" in the paper's Table I naming.
  - FSA "trivial":     ripple-carry adder (RCA) — paper explicitly calls
                        this the case where stage 2+3 are "only made of
                        half-adders and full-adders" (quoted in Thm 1's
                        proof and the RevSCA table notation).
  - FSA "non-trivial":  a full (non-block) carry-lookahead adder (CLA),
                        i.e. every carry bit expanded as a flattened
                        sum-of-products of generate/propagate signals.
                        This is explicitly the example the ICCAD'22
                        paper itself uses for its "non-trivial" 4x4 memory
                        plot: "it also uses a carry look-ahead adder
                        architecture in its final stage; thus, it is not
                        fully made of half-adders and full-adders."
"""

class Netlist:
    def __init__(self):
        self.gates = []          # list of (name, gtype, in1, in2_or_None) in creation (topo) order
        self._counter = 0

    def _new_name(self, prefix):
        self._counter += 1
        return f"{prefix}{self._counter}"

    def NOT(self, a):
        z = self._new_name("n")
        self.gates.append((z, "NOT", a, None))
        return z

    def AND(self, a, b):
        z = self._new_name("g")
        self.gates.append((z, "AND", a, b))
        return z

    def OR(self, a, b):
        z = self._new_name("g")
        self.gates.append((z, "OR", a, b))
        return z

    def XOR(self, a, b):
        z = self._new_name("g")
        self.gates.append((z, "XOR", a, b))
        return z

    def half_adder(self, a, b):
        s = self.XOR(a, b)
        c = self.AND(a, b)
        return s, c

    def full_adder(self, a, b, cin):
        s1 = self.XOR(a, b)
        s = self.XOR(s1, cin)
        c1 = self.AND(a, b)
        c2 = self.AND(s1, cin)
        cout = self.OR(c1, c2)
        return s, cout


def build_partial_products(net, a_bits, b_bits):
    """Simple PPG: AND gates only. Returns columns[k] = list of signals with weight k."""
    n = len(a_bits)
    m = len(b_bits)
    columns = [[] for _ in range(n + m)]
    for i in range(n):
        for j in range(m):
            columns[i + j].append(net.AND(a_bits[i], b_bits[j]))
    return columns


def wallace_reduce(net, columns):
    """Column-wise 3:2 / 2:1 compression down to at most 2 rows per column."""
    columns = [list(c) for c in columns]
    while max(len(c) for c in columns) > 2:
        new_columns = [[] for _ in range(len(columns) + 1)]
        for k, col in enumerate(columns):
            i = 0
            while i + 3 <= len(col):
                s, c = net.full_adder(col[i], col[i + 1], col[i + 2])
                new_columns[k].append(s)
                new_columns[k + 1].append(c)
                i += 3
            if i + 2 <= len(col):
                s, c = net.half_adder(col[i], col[i + 1])
                new_columns[k].append(s)
                new_columns[k + 1].append(c)
                i += 2
            while i < len(col):
                new_columns[k].append(col[i])
                i += 1
        columns = new_columns
    return columns


def two_rows_from_columns(columns):
    row0 = []
    row1 = []
    for col in columns:
        row0.append(col[0] if len(col) > 0 else None)
        row1.append(col[1] if len(col) > 1 else None)
    return row0, row1


def ripple_carry_adder(net, row0, row1):
    """Trivial FSA: plain ripple-carry chain of HA/FA over the two PPA output rows.
    None means 'no signal at this position' (constant 0)."""
    width = len(row0)
    outputs = [None] * width
    carry = None
    for k in range(width):
        a = row0[k]
        b = row1[k]
        present = [x for x in (a, b, carry) if x is not None]
        if len(present) == 0:
            outputs[k] = None
            carry = None
        elif len(present) == 1:
            outputs[k] = present[0]
            carry = None
        elif len(present) == 2:
            s, carry = net.half_adder(present[0], present[1])
            outputs[k] = s
        else:
            s, carry = net.full_adder(a, b, carry)
            outputs[k] = s
    if carry is not None:
        outputs.append(carry)
    return outputs


def carry_lookahead_adder(net, row0, row1):
    """
    Non-trivial FSA: full (flattened) carry-lookahead adder.
    g[k] = a[k] AND b[k]      (generate)
    p[k] = a[k] XOR b[k]      (propagate)
    c[k+1] = OR over j<=k of ( g[j] AND p[j+1] AND ... AND p[k] )   (sum of products, no
             recursive dependence on previously-computed carry signals — this is what
             makes it structurally different from the ripple-carry chain)
    s[k] = p[k] XOR c[k]
    """
    width = len(row0)
    a = [row0[k] if row0[k] is not None else None for k in range(width)]
    b = [row1[k] if row1[k] is not None else None for k in range(width)]

    def and2(net, x, y):
        # AND with a missing (=0) input is always 0 -- unlike xor2/or_chain,
        # None here must NOT pass through the other operand.
        if x is None or y is None:
            return None
        return net.AND(x, y)

    def xor2(net, x, y):
        if x is None and y is None:
            return None
        if x is None:
            return y
        if y is None:
            return x
        return net.XOR(x, y)

    def or_chain(net, sigs):
        sigs = [s for s in sigs if s is not None]
        if not sigs:
            return None
        acc = sigs[0]
        for s in sigs[1:]:
            acc = net.OR(acc, s)
        return acc

    def and_chain(net, sigs):
        # Any operand being None means that operand is the constant 0,
        # which makes the whole AND chain 0 -- must NOT be silently dropped.
        if any(s is None for s in sigs):
            return None
        if not sigs:
            return None
        acc = sigs[0]
        for s in sigs[1:]:
            acc = net.AND(acc, s)
        return acc

    g = [and2(net, a[k], b[k]) for k in range(width)]
    p = [xor2(net, a[k], b[k]) for k in range(width)]

    carries = [None] * (width + 1)  # carries[k] = carry INTO bit k
    for k in range(width):
        terms = []
        for j in range(k + 1):
            term = and_chain(net, [g[j]] + p[j + 1:k + 1])
            terms.append(term)
        carries[k + 1] = or_chain(net, terms)

    outputs = [None] * width
    for k in range(width):
        outputs[k] = xor2(net, p[k], carries[k])
    if carries[width] is not None:
        outputs.append(carries[width])
    return outputs


def build_multiplier(n, kind):
    """
    kind: 'trivial' (RCA final stage) or 'nontrivial' (full CLA final stage)
    Returns (net, a_bits, b_bits, output_bits)
    """
    net = Netlist()
    a_bits = [f"a{i}" for i in range(n)]
    b_bits = [f"b{i}" for i in range(n)]
    columns = build_partial_products(net, a_bits, b_bits)
    columns = wallace_reduce(net, columns)
    row0, row1 = two_rows_from_columns(columns)
    if kind == "trivial":
        out = ripple_carry_adder(net, row0, row1)
    elif kind == "nontrivial":
        out = carry_lookahead_adder(net, row0, row1)
    else:
        raise ValueError(kind)
    return net, a_bits, b_bits, out
