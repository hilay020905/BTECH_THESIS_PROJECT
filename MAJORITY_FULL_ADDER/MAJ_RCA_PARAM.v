// N-bit ripple-carry adder built from your majority_full_adder (defined in MAJ_FULL_ADDER.v)
module maj_rca #(parameter N = 4)(
    input  [N-1:0] a,
    input  [N-1:0] b,
    input          cin,
    output [N-1:0] sum,
    output         cout
);
    wire [N:0] c;
    assign c[0] = cin;
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : stage
            majority_full_adder FA (.A(a[i]), .B(b[i]), .Ci(c[i]), .Sum(sum[i]), .Co(c[i+1]));
        end
    endgenerate
    assign cout = c[N];
endmodule
