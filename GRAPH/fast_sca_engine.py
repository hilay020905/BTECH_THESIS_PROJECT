"""
Same SCA backward-rewriting method as sca_engine.py (verified correct
against sympy on n<=4 above), reimplemented with a hand-rolled sparse
polynomial representation for speed:

  polynomial = dict: frozenset(variable_names) -> int coefficient

Booleans satisfy x^2 = x, so a monomial is fully described by the *set*
of variables in it (no exponents needed) -- this is exactly the paper's
own justification for dropping powers ("we always replace powers x_i^ai
with ai>1 by x_i"), just exploited for speed instead of doing it via
sympy's generic expand().
"""

from collections import defaultdict


def const_poly(c):
    return {frozenset(): c} if c != 0 else {}


def var_poly(name):
    return {frozenset([name]): 1}


def add_poly(p1, p2):
    out = defaultdict(int, p1)
    for k, v in p2.items():
        out[k] += v
    return {k: v for k, v in out.items() if v != 0}


def scale_poly(p, c):
    if c == 0:
        return {}
    return {k: v * c for k, v in p.items()}


def mul_poly(p1, p2):
    out = defaultdict(int)
    for k1, v1 in p1.items():
        for k2, v2 in p2.items():
            k = k1 | k2  # union == idempotent multiplication of booleans
            out[k] += v1 * v2
    return {k: v for k, v in out.items() if v != 0}


def monomial_count(p):
    return len(p)


def gate_tail_poly(gtype, a_name, b_name):
    """Returns tail(p_g) as a sparse polynomial, per Eq. 3/4 of the paper."""
    a = var_poly(a_name)
    if gtype == "NOT":
        # z = ~a => p_g = z - 1 + a  => tail = 1 - a
        return add_poly(const_poly(1), scale_poly(a, -1))
    b = var_poly(b_name)
    ab = mul_poly(a, b)
    if gtype == "AND":
        # tail = a*b
        return ab
    if gtype == "OR":
        # tail = a + b - a*b
        return add_poly(add_poly(a, b), scale_poly(ab, -1))
    if gtype == "XOR":
        # tail = a + b - 2*a*b
        return add_poly(add_poly(a, b), scale_poly(ab, -2))
    raise ValueError(gtype)


def substitute(poly, var_name, tail_poly):
    """Substitute var_name -> tail_poly in poly. Returns new poly."""
    out = defaultdict(int)
    tail_items = list(tail_poly.items())
    for mono, coeff in poly.items():
        if var_name in mono:
            rest = mono - {var_name}
            rest_poly = {rest: coeff}
            # multiply rest_poly by tail_poly
            for k2, v2 in tail_items:
                k = rest | k2
                out[k] += coeff * v2
        else:
            out[mono] += coeff
    return {k: v for k, v in out.items() if v != 0}


def specification_polynomial(a_bits, b_bits, out_bits):
    n = len(a_bits)
    A = {}
    for i in range(n):
        A = add_poly(A, scale_poly(var_poly(a_bits[i]), 2 ** i))
    B = {}
    for i in range(len(b_bits)):
        B = add_poly(B, scale_poly(var_poly(b_bits[i]), 2 ** i))
    AB = mul_poly(A, B)
    OUT = {}
    for k, name in enumerate(out_bits):
        if name is None:
            continue
        OUT = add_poly(OUT, scale_poly(var_poly(name), 2 ** k))
    return add_poly(OUT, scale_poly(AB, -1))


def backward_rewrite(net, a_bits, b_bits, out_bits, log_every=1, progress_every=None):
    SP = specification_polynomial(a_bits, b_bits, out_bits)
    history = [monomial_count(SP)]

    all_vars_in_SP = set()
    for mono in SP:
        all_vars_in_SP |= mono

    steps_done = 0
    for (z, gtype, i1, i2) in reversed(net.gates):
        # quick membership check across current polynomial's monomials
        used = any(z in mono for mono in SP)
        if not used:
            continue
        tail = gate_tail_poly(gtype, i1, i2)
        SP = substitute(SP, z, tail)
        steps_done += 1
        if steps_done % log_every == 0:
            history.append(monomial_count(SP))
        if progress_every and steps_done % progress_every == 0:
            print(f"    step {steps_done}: {monomial_count(SP)} monomials")

    return history, SP
