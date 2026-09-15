module maj_kogge_stone_adder #(
    parameter int N = 16
) (
    input  logic [N-1:0] a,
    input  logic [N-1:0] b,
    input  logic         cin,
    output logic [N-1:0] sum,
    output logic         cout
);

  localparam int LOG2N = $clog2(N);

  logic [N-1:0] stageA [0:LOG2N];
  logic [N-1:0] stageB [0:LOG2N];

  genvar s, i;

  generate
    for (i = 0; i < N; i++) begin : g_leaf
      assign stageA[0][i] = a[i];
      assign stageB[0][i] = b[i];
    end

    for (s = 0; s < LOG2N; s++) begin : g_stage
      for (i = 0; i < N; i++) begin : g_pos
        if (i >= (1 << s)) begin : g_combine

          assign {stageA[s+1][i], stageB[s+1][i]} =
              maj_pkg::bullet(stageA[s][i],        stageB[s][i],
                     stageA[s][i-(1<<s)], stageB[s][i-(1<<s)]);
        end else begin : g_pass
          assign stageA[s+1][i] = stageA[s][i];
          assign stageB[s+1][i] = stageB[s][i];
        end
      end
    end
  endgenerate

  logic [N:0] carry;
  assign carry[0] = cin;
  generate
    for (i = 0; i < N; i++) begin : g_carry
      assign carry[i+1] = maj_pkg::maj3(stageA[LOG2N][i], stageB[LOG2N][i], cin);
    end
  endgenerate

  generate
    for (i = 0; i < N; i++) begin : g_sum
      assign sum[i] = maj_pkg::maj3(~carry[i+1],
                           maj_pkg::maj3(a[i], b[i], ~carry[i+1]),
                           carry[i]);
    end
  endgenerate

  assign cout = carry[N];

endmodule
