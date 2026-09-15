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

  int errors = 0;

  class maj_txn;
    rand bit [N-1:0] a;
    rand bit [N-1:0] b;
    rand bit         cin;

    constraint c_a { a dist { 16'h0000 := 1, 16'hFFFF := 1, [16'h0001:16'hFFFE] :/ 8 }; }
    constraint c_b { b dist { 16'h0000 := 1, 16'hFFFF := 1, [16'h0001:16'hFFFE] :/ 8 }; }
    constraint c_cin { cin dist { 1'b0 := 1, 1'b1 := 1 }; }
  endclass

  maj_txn txn;
  bit clk;
  always #1 clk = ~clk;

  covergroup cg_adders @(posedge clk);
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

  task automatic check(string name, logic [N-1:0] sum_dut, logic cout_dut);
    logic [N:0] expected = a + b + cin;
    if (sum_dut !== expected[N-1:0] || cout_dut !== expected[N]) begin
      errors++;
      $display("FAIL[%s] a=%0d b=%0d cin=%0d got=%0d/%0b exp=%0d/%0b",
                name, a, b, cin, sum_dut, cout_dut, expected[N-1:0], expected[N]);
    end
  endtask

  task automatic run_one(logic [N-1:0] ta, logic [N-1:0] tb, logic tcin);
    a = ta; b = tb; cin = tcin;
    #1;
    check("KS", sum_ks, cout_ks);
    check("LF", sum_lf, cout_lf);
    check("BK", sum_bk, cout_bk);
    cg_h.sample();
  endtask

  initial begin
    txn  = new();
    cg_h = new();

    run_one('0, '0, 1'b0);
    run_one('1, '1, 1'b1);
    run_one(16'hFFFF, 16'h0001, 1'b0);
    run_one(16'h8000, 16'h8000, 1'b0);

    for (int i = 0; i < 2000; i++) begin
      if (!txn.randomize())
        $display("RANDOMIZE FAILED at iter %0d", i);
      run_one(txn.a, txn.b, txn.cin);
    end
    #5000;
    $display("--------------------------------------------------");
    $display("Functional coverage = %0.2f %%", cg_h.get_coverage());
    $display("--------------------------------------------------");

    if (errors == 0) $display("ALL TESTS PASSED");
    else              $display("%0d MISMATCHES FOUND", errors);

    $finish;
  end

endmodule