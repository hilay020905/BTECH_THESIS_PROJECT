"""
SCA-based backward rewriting, following Section II-B / Eq. (3)-(5) of the
BTP.pdf papers exactly:

  NOT: z = ~a  =>  p_g := z - 1 + a
  AND: z = a&b =>  p_g := z - a*b
  OR:  z = a|b =>  p_g := z - a - b + a*b
  XOR: z = a^b =>  p_g := z - a - b + 2*a*b

p_g is in the form z - tail(p_g). Dividing SP_i by p_g (i.e. substituting
z with tail(p_g) in SP_i) is the backward-rewriting step. Boolean
variables satisfy x^n = x for n>=1, so after every substitution we reduce
powers back to 1 (paper: "we always replace powers x_i^ai with ai>1 by x_i").

We process gates in REVERSE topological order (paper: "signals ... ordered
based on the reverse-topological order, i.e. from outputs toward inputs"),
substituting each gate's output variable if it still appears in the current
polynomial, and record the number of monomials (terms) after each step —
this is exactly what Figure 1 plots.
"""

from sympy import symbols, Poly, Add, expand, Symbol


def gate_tail(gtype, in1, in2, symtab):
    a = symtab[in1]
    if gtype == "NOT":
        return -1 + a  # tail(p_g) for z = -1 + a  (p_g = z - (a - 1))... see below
    b = symtab[in2]
    if gtype == "AND":
        return a * b
    if gtype == "OR":
        return a + b - a * b
    if gtype == "XOR":
        return a + b - 2 * a * b
    raise ValueError(gtype)


def reduce_boolean_powers(expr):
    """Replace x**k (k>=1) with x for every free symbol, per the paper's rule x_i^{a_i}=x_i."""
    expr = expand(expr)
    return expr.replace(
        lambda e: e.is_Pow and e.exp.is_Integer and e.exp >= 1,
        lambda e: e.base,
    )


def monomial_count(expr):
    expr = expand(expr)
    if expr == 0:
        return 0
    return len(Add.make_args(expr))


def specification_polynomial(a_bits, b_bits, out_bits, symtab):
    n = len(a_bits)
    A = sum(symtab[a_bits[i]] * (2 ** i) for i in range(n))
    B = sum(symtab[b_bits[i]] * (2 ** i) for i in range(n))
    OUT = sum(symtab[out_bits[k]] * (2 ** k) for k in range(len(out_bits)) if out_bits[k] is not None)
    return OUT - A * B


def backward_rewrite(net, a_bits, b_bits, out_bits, log_every=1, max_steps=None, progress=False):
    """
    net: Netlist (gates in topological/creation order)
    Returns: list of monomial counts (one entry per substitution step actually performed)
    """
    # build symbol table for every signal name that ever appears
    all_names = set(a_bits) | set(b_bits)
    for (z, gtype, i1, i2) in net.gates:
        all_names.add(z)
    symtab = {name: Symbol(name) for name in all_names}

    SP = specification_polynomial(a_bits, b_bits, out_bits, symtab)
    SP = reduce_boolean_powers(SP)

    history = [monomial_count(SP)]

    # reverse topological order = reverse of creation order
    steps_done = 0
    for (z, gtype, i1, i2) in reversed(net.gates):
        zs = symtab[z]
        if zs not in SP.free_symbols:
            continue  # this gate's output was never used (dead code) -- skip, no division needed
        tail = gate_tail(gtype, i1, i2, symtab)
        SP = SP.subs(zs, tail)
        SP = reduce_boolean_powers(SP)
        steps_done += 1
        if steps_done % log_every == 0:
            history.append(monomial_count(SP))
        if progress and steps_done % 200 == 0:
            print(f"  ... {steps_done} substitutions, current size = {monomial_count(SP)}")
        if max_steps is not None and steps_done >= max_steps:
            break

    return history, SP
