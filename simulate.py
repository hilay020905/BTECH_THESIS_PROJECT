def simulate(net, input_values):
    """input_values: dict signal_name -> 0/1. Returns dict of all signal values."""
    vals = dict(input_values)
    for (z, gtype, i1, i2) in net.gates:
        if gtype == "NOT":
            vals[z] = 1 - vals[i1]
        elif gtype == "AND":
            vals[z] = vals[i1] & vals[i2]
        elif gtype == "OR":
            vals[z] = vals[i1] | vals[i2]
        elif gtype == "XOR":
            vals[z] = vals[i1] ^ vals[i2]
    return vals


def bits_to_int(vals, bits):
    n = 0
    for k, name in enumerate(bits):
        if name is None:
            bit = 0
        else:
            bit = vals[name]
        n |= (bit << k)
    return n
