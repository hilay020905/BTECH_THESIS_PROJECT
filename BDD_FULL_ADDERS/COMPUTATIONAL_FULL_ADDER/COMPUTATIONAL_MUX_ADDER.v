module mux2 (
    input  sel,
    input  d1,
    input  d0,
    output y
);
    assign y = sel ? d1 : d0;
endmodule

// COMPUTATIONAL_MUX_ADDER
//
// Reduced-computation MUX-based full adder.
// Instead of building sum and cout from 5 independent 2:1 muxes
// (XOR, XOR, AND, OR, MAJ-mux as in MUX_FULL_ADDER), this version
// reuses a single shared term  p = a XOR b  and computes both
// outputs directly from it with only 2 further muxes:
//
//      p    = a XOR b
//      Cout = ITE(p, Ci, A)      i.e.  p ? cin : a
//      S    = ITE(p, ~Ci, Ci)    i.e.  p ? ~cin : cin
//
// Total: 3 muxes (1 for p, 1 for sum, 1 for cout) instead of 5,
// which lowers gate/AND-count after mux->AND/inverter expansion
// (9 AND gates here vs 15 for MUX_FULL_ADDER).
module computational_mux_adder (
    input  a,
    input  b,
    input  cin,
    output sum,
    output cout
);

    wire p;      // p = a XOR b, shared by both outputs

    // p = a XOR b = MUX(a, ~b, b)
    mux2 M_P (.sel(a), .d1(~b), .d0(b), .y(p));

    // S = ITE(p, ~Ci, Ci) = MUX(p, ~cin, cin)
    mux2 M_SUM (.sel(p), .d1(~cin), .d0(cin), .y(sum));

    // Cout = ITE(p, Ci, A) = MUX(p, cin, a)
    mux2 M_COUT (.sel(p), .d1(cin), .d0(a), .y(cout));

endmodule
