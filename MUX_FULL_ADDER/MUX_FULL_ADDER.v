module mux2 (
    input  sel,
    input  d1,     
    input  d0,     
    output y
);
    assign y = sel ? d1 : d0;
endmodule

module mux_full_adder (
    input  a,
    input  b,
    input  cin,
    output sum,
    output cout
);

    wire p;        // a XOR b
    wire ab;       // a AND b
    wire aorb;     // a OR  b

    // p = a XOR b = MUX(a, ~b, b)
    mux2 M_XOR1 (.sel(a), .d1(~b), .d0(b), .y(p));

    // sum = p XOR cin = MUX(cin, ~p, p)
    mux2 M_XOR2 (.sel(cin), .d1(~p), .d0(p), .y(sum));

    // a AND b = MUX(a, b, 0)
    mux2 M_AND (.sel(a), .d1(b), .d0(1'b0), .y(ab));

    // a OR b = MUX(a, 1, b)
    mux2 M_OR (.sel(a), .d1(1'b1), .d0(b), .y(aorb));

    // cout = MAJ(a, b, cin) = MUX(cin, a|b, a&b)
    mux2 M_COUT (.sel(cin), .d1(aorb), .d0(ab), .y(cout));

endmodule