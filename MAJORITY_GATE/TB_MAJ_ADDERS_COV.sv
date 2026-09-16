`timescale 1ns/1ps
module tb_maj_adders_cov;

  localparam int N = 16;

  logic [N-1:0] a, b;
  logic         cin;
  logic [N-1:0] sum_ks, sum_lf, sum_bk;
  logic         cout_ks, cout_lf, cout_bk;

  maj_kogge_stone_adder    #(.N(N)) dut_ks (.a(a), .b(b), .cin(cin), .sum(sum_ks), .cout(cout_ks));
  maj_ladner_fischer_adder #(.N(N)) dut_lf (.a(a), .b(b), .cin(cin), .sum(sum_lf), .cout(cout_lf));
  maj_brent_kung_adder     #(.N(N)) dut_bk (.a(a), .b(b), .cin(cin), .sum(sum_bk), .cout(cout_bk));

  int unsigned NUM_RANDOM_TESTS = 2000;

  class maj_txn;
    rand bit [N-1:0] a;
    rand bit [N-1:0] b;
    rand bit         cin;

    constraint c_a   { a dist { 16'h0000 := 1, 16'hFFFF := 1, [16'h0001:16'hFFFE] :/ 8 }; }
    constraint c_b   { b dist { 16'h0000 := 1, 16'hFFFF := 1, [16'h0001:16'hFFFE] :/ 8 }; }
    constraint c_cin { cin dist { 1'b0 := 1, 1'b1 := 1 }; }
  endclass

  maj_txn txn;

  covergroup cg_adders;
    option.per_instance = 1;

    cp_a : coverpoint a {
      bins zero = {16'h0000};
      bins max  = {16'hFFFF};
      bins low  = {[16'h0001 : 16'h3FFF]};
      bins mid  = {[16'h4000 : 16'hBFFF]};
      bins high = {[16'hC000 : 16'hFFFE]};
    }

    cp_b : coverpoint b {
      bins zero = {16'h0000};
      bins max  = {16'hFFFF};
      bins low  = {[16'h0001 : 16'h3FFF]};
      bins mid  = {[16'h4000 : 16'hBFFF]};
      bins high = {[16'hC000 : 16'hFFFE]};
    }

    cp_cin : coverpoint cin {
      bins zero = {1'b0};
      bins one  = {1'b1};
    }

    cp_cout : coverpoint cout_ks {
      bins no_ovf = {1'b0};
      bins ovf    = {1'b1};
    }

    cx_ab_cin : cross cp_a, cp_b, cp_cin;
  endgroup

  cg_adders cg_h;

  typedef enum {BIN_ZERO, BIN_MAX, BIN_LOW, BIN_MID, BIN_HIGH} opbin_e;

  function automatic opbin_e classify(logic [N-1:0] v);
    if (v == 16'h0000)                classify = BIN_ZERO;
    else if (v == 16'hFFFF)           classify = BIN_MAX;
    else if (v <= 16'h3FFF)           classify = BIN_LOW;
    else if (v <= 16'hBFFF)           classify = BIN_MID;
    else                              classify = BIN_HIGH;
  endfunction

  bit cp_a_hit   [BIN_ZERO:BIN_HIGH];
  bit cp_b_hit   [BIN_ZERO:BIN_HIGH];
  bit cp_cin_hit [0:1];
  bit cp_cout_hit[0:1];
  bit cx_hit     [BIN_ZERO:BIN_HIGH][BIN_ZERO:BIN_HIGH][0:1];

  // ---------------- extra metrics ----------------
  int unsigned vectors_run     = 0;
  int unsigned corner_zero_cnt = 0;   // either operand == 0
  int unsigned corner_max_cnt  = 0;   // either operand == all-ones
  int unsigned cin0_cnt        = 0, cin1_cnt = 0;
  int unsigned overflow_cnt    = 0;   // cout_ks == 1

  int errors     = 0;
  int errors_ks  = 0, errors_lf = 0, errors_bk = 0;

  logic [N:0] min_sum, max_sum;
  bit         minmax_init = 0;

  task automatic sample_all();
    opbin_e ca, cb;
    ca = classify(a);
    cb = classify(b);

    cp_a_hit[ca]         = 1'b1;
    cp_b_hit[cb]         = 1'b1;
    cp_cin_hit[cin]      = 1'b1;
    cp_cout_hit[cout_ks] = 1'b1;
    cx_hit[ca][cb][cin]  = 1'b1;

    cg_h.sample();   // native covergroup sample (currently a no-op re: data)

    vectors_run++;
    if (a == '0 || b == '0)  corner_zero_cnt++;
    if (a == '1 || b == '1)  corner_max_cnt++;
    if (cin == 0) cin0_cnt++; else cin1_cnt++;
    if (cout_ks)  overflow_cnt++;

    begin
      logic [N:0] s = a + b + cin;
      if (!minmax_init) begin
        min_sum = s; max_sum = s; minmax_init = 1;
      end else begin
        if (s < min_sum) min_sum = s;
        if (s > max_sum) max_sum = s;
      end
    end
  endtask

  function automatic real manual_coverage();
    int hit, total, i, j, k;
    hit = 0; total = 0;

    for (i = BIN_ZERO; i <= BIN_HIGH; i++) begin
      total++; if (cp_a_hit[opbin_e'(i)]) hit++;
      total++; if (cp_b_hit[opbin_e'(i)]) hit++;
    end
    total += 2; if (cp_cin_hit[0])  hit++;
                if (cp_cin_hit[1])  hit++;
    total += 2; if (cp_cout_hit[0]) hit++;
                if (cp_cout_hit[1]) hit++;

    for (i = BIN_ZERO; i <= BIN_HIGH; i++)
      for (j = BIN_ZERO; j <= BIN_HIGH; j++)
        for (k = 0; k <= 1; k++) begin
          total++;
          if (cx_hit[opbin_e'(i)][opbin_e'(j)][k]) hit++;
        end

    manual_coverage = 100.0 * hit / total;
  endfunction

 
  task automatic check(string name, logic [N-1:0] sum_dut, logic cout_dut, ref int err_cnt);
    logic [N:0] expected = a + b + cin;
    if (sum_dut !== expected[N-1:0] || cout_dut !== expected[N]) begin
      errors++;
      err_cnt++;
      $display("FAIL[%s] a=%0d b=%0d cin=%0d got=%0d/%0b exp=%0d/%0b",
                name, a, b, cin, sum_dut, cout_dut, expected[N-1:0], expected[N]);
    end
  endtask

  task automatic run_one(logic [N-1:0] ta, logic [N-1:0] tb, logic tcin);
    a = ta; b = tb; cin = tcin;
    #1;
    check("KS", sum_ks, cout_ks, errors_ks);
    check("LF", sum_lf, cout_lf, errors_lf);
    check("BK", sum_bk, cout_bk, errors_bk);
    sample_all();
  endtask

  initial begin
    real t_start, t_end;

    txn  = new();
    cg_h = new();
    t_start = $realtime;

    // directed corner cases
    run_one('0, '0, 1'b0);
    run_one('1, '1, 1'b1);
    run_one(16'hFFFF, 16'h0001, 1'b0);
    run_one(16'h8000, 16'h8000, 1'b0);

    // constrained-random stimulus
    for (int i = 0; i < NUM_RANDOM_TESTS; i++) begin
      if (!txn.randomize())
        $display("RANDOMIZE FAILED at iter %0d", i);
      run_one(txn.a, txn.b, txn.cin);
    end

    t_end = $realtime;

    $display("====================================================");
    $display(" TEST SUMMARY");
    $display("====================================================");
    $display(" Vectors run                : %0d", vectors_run);
    $display(" Total errors               : %0d", errors);
    $display("   - Kogge-Stone errors      : %0d", errors_ks);
    $display("   - Ladner-Fischer errors   : %0d", errors_lf);
    $display("   - Brent-Kung errors       : %0d", errors_bk);
    $display("----------------------------------------------------");
    $display(" Stimulus distribution");
    $display("   - a or b == 0             : %0d (%0.1f%%)", corner_zero_cnt, 100.0*corner_zero_cnt/vectors_run);
    $display("   - a or b == all-ones      : %0d (%0.1f%%)", corner_max_cnt,  100.0*corner_max_cnt/vectors_run);
    $display("   - cin == 0                : %0d (%0.1f%%)", cin0_cnt, 100.0*cin0_cnt/vectors_run);
    $display("   - cin == 1                : %0d (%0.1f%%)", cin1_cnt, 100.0*cin1_cnt/vectors_run);
    $display("   - cout (overflow) == 1    : %0d (%0.1f%%)", overflow_cnt, 100.0*overflow_cnt/vectors_run);
    $display(" Result range                : min_sum=%0d  max_sum=%0d", min_sum, max_sum);
    $display("----------------------------------------------------");
    $display(" Coverage (native covergroup): %0.2f %%   <- currently unreliable on this Verilator build (see #7099)", cg_h.get_coverage());
    $display(" Coverage (manual, same bins): %0.2f %%", manual_coverage());
    $display("----------------------------------------------------");
    $display(" Sim walltime                : %0.1f ns", t_end - t_start);
    $display("====================================================");

    if (errors == 0) $display("ALL TESTS PASSED");
    else              $display("%0d MISMATCHES FOUND", errors);

    $finish;
  end

endmodule
