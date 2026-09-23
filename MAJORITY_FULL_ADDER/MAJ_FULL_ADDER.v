module maj(
    input  w,
    input  x,
    input  y,
    output z
);

assign z = (w & x) | (x & y) | (y & w);

endmodule


module majority_full_adder(
    input  A,
    input  B,
    input  Ci,
    output Sum,
    output Co
);

wire nCi;
wire nCo;
wire m1;
wire m2;

// Invert Ci
assign nCi = ~Ci;

// First majority gate: Co = MAJ(A, B, Ci)
maj M1 (
    .w(A),
    .x(B),
    .y(Ci),
    .z(Co)
);

// Invert Co
assign nCo = ~Co;

// Second majority gate: M2 = MAJ(A, B, ~Ci)
maj M2 (
    .w(A),
    .x(B),
    .y(nCi),
    .z(m2)
);

// Final majority gate: Sum = MAJ(~Co, Ci, M2)
maj M3 (
    .w(nCo),
    .x(Ci),
    .y(m2),
    .z(Sum)
);

endmodule