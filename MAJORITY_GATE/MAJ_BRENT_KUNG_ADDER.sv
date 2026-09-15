module maj_brent_kung_adder #(
    parameter int N = 16
) (
    input  logic [N-1:0] a,
    input  logic [N-1:0] b,
    input  logic         cin,
    output logic [N-1:0] sum,
    output logic         cout
);

  localparam int LOG2N = $clog2(N);

  localparam int NLEVELS = 2 * LOG2N;
  logic [N-1:0] levelA [0:NLEVELS-1];
  logic [N-1:0] levelB [0:NLEVELS-1];

  genvar i;
  generate
    for (i = 0; i < N; i++) begin : g_leaf
      assign levelA[0][i] = a[i];
      assign levelB[0][i] = b[i];
    end
  endgenerate

  genvar d, k;
  generate
    for (d = 0; d < LOG2N; d++) begin : g_up
      localparam int STRIDE = 1 << d;
      localparam int LVL_IN  = d;
      localparam int LVL_OUT = d + 1;
      for (k = 0; k < N; k++) begin : g_up_pos
        if ((k >= (2*STRIDE - 1)) && (((k - (2*STRIDE - 1)) % (2*STRIDE)) == 0)) begin : g_up_combine
          assign {levelA[LVL_OUT][k], levelB[LVL_OUT][k]} =
              maj_pkg::bullet(levelA[LVL_IN][k],          levelB[LVL_IN][k],
                     levelA[LVL_IN][k-STRIDE],   levelB[LVL_IN][k-STRIDE]);
        end else begin : g_up_pass
          assign levelA[LVL_OUT][k] = levelA[LVL_IN][k];
          assign levelB[LVL_OUT][k] = levelB[LVL_IN][k];
        end
      end
    end
  endgenerate

  generate
    if (LOG2N >= 2) begin : g_down_needed
      for (d = LOG2N - 2; d >= 0; d--) begin : g_down
        localparam int STRIDE  = 1 << d;

        localparam int STEP_NO = (LOG2N - 2) - d;
        localparam int LVL_IN  = LOG2N + STEP_NO;
        localparam int LVL_OUT = LOG2N + STEP_NO + 1;
        for (k = 0; k < N; k++) begin : g_down_pos
          if ((k >= (3*STRIDE - 1)) && (((k - (3*STRIDE - 1)) % (2*STRIDE)) == 0)) begin : g_down_combine
            assign {levelA[LVL_OUT][k], levelB[LVL_OUT][k]} =
                maj_pkg::bullet(levelA[LVL_IN][k],        levelB[LVL_IN][k],
                       levelA[LVL_IN][k-STRIDE], levelB[LVL_IN][k-STRIDE]);
          end else begin : g_down_pass
            assign levelA[LVL_OUT][k] = levelA[LVL_IN][k];
            assign levelB[LVL_OUT][k] = levelB[LVL_IN][k];
          end
        end
      end
    end
  endgenerate

  localparam int LVL_FINAL = NLEVELS - 1;

  logic [N:0] carry;
  assign carry[0] = cin;
  generate
    for (i = 0; i < N; i++) begin : g_carry
      assign carry[i+1] = maj_pkg::maj3(levelA[LVL_FINAL][i], levelB[LVL_FINAL][i], cin);
    end
    for (i = 0; i < N; i++) begin : g_sum
      assign sum[i] = maj_pkg::maj3(~carry[i+1],
                           maj_pkg::maj3(a[i], b[i], ~carry[i+1]),
                           carry[i]);
    end
  endgenerate

  assign cout = carry[N];

endmodule
