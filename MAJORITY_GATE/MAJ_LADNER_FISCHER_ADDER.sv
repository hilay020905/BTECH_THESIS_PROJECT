module lf_prefix_tree #(
    parameter int N = 16
) (
    input  logic [N-1:0] inA,
    input  logic [N-1:0] inB,
    output logic [N-1:0] outA,
    output logic [N-1:0] outB
);

  generate
    if (N == 1) begin : g_base
      assign outA[0] = inA[0];
      assign outB[0] = inB[0];
    end else begin : g_recurse
      localparam int H = N / 2;

      logic [H-1:0] loA, loB;
      lf_prefix_tree #(.N(H)) u_lo (
          .inA (inA[H-1:0]),
          .inB (inB[H-1:0]),
          .outA(loA),
          .outB(loB)
      );

      logic [H-1:0] hiA_local, hiB_local;
      lf_prefix_tree #(.N(H)) u_hi (
          .inA (inA[N-1:H]),
          .inB (inB[N-1:H]),
          .outA(hiA_local),
          .outB(hiB_local)
      );

      assign outA[H-1:0] = loA;
      assign outB[H-1:0] = loB;

      genvar j;
      for (j = 0; j < H; j++) begin : g_combine_high
        assign {outA[H+j], outB[H+j]} =
            maj_pkg::bullet(hiA_local[j], hiB_local[j], loA[H-1], loB[H-1]);
      end
    end
  endgenerate

endmodule

module maj_ladner_fischer_adder #(
    parameter int N = 16
) (
    input  logic [N-1:0] a,
    input  logic [N-1:0] b,
    input  logic         cin,
    output logic [N-1:0] sum,
    output logic         cout
);

  logic [N-1:0] prefA, prefB;

  lf_prefix_tree #(.N(N)) u_tree (
      .inA (a),
      .inB (b),
      .outA(prefA),
      .outB(prefB)
  );

  logic [N:0] carry;
  assign carry[0] = cin;

  genvar i;
  generate
    for (i = 0; i < N; i++) begin : g_carry
      assign carry[i+1] = maj_pkg::maj3(prefA[i], prefB[i], cin);
    end
    for (i = 0; i < N; i++) begin : g_sum
      assign sum[i] = maj_pkg::maj3(~carry[i+1],
                           maj_pkg::maj3(a[i], b[i], ~carry[i+1]),
                           carry[i]);
    end
  endgenerate

  assign cout = carry[N];

endmodule
