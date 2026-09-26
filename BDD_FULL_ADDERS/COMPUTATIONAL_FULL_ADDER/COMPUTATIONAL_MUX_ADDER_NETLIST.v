/* Flattened netlist for computational_mux_adder
   (structurally mirrors the AND/inverter expansion in COMPUTATIONAL_MUX_ADDER.aag /
   COMPUTATIONAL_MUX_ADDER.aig, produced the same way Yosys's aigmap would expand
   the mux2 instances in COMPUTATIONAL_MUX_ADDER.v) */

module computational_mux_adder(a, b, cin, sum, cout);
  wire \M_P.d0 ;
  wire \M_P.d1 ;
  wire \M_P.sel ;
  wire \M_P.y ;
  wire \M_SUM.d0 ;
  wire \M_SUM.d1 ;
  wire \M_SUM.sel ;
  wire \M_SUM.y ;
  wire \M_COUT.d0 ;
  wire \M_COUT.d1 ;
  wire \M_COUT.sel ;
  wire \M_COUT.y ;
  input a;
  wire a;
  input b;
  wire b;
  input cin;
  wire cin;
  output cout;
  wire cout;
  wire p;
  output sum;
  wire sum;

  // p = a XOR b   (M_P)
  assign \M_P.sel  = a;
  assign \M_P.d1  = ~b;
  assign \M_P.d0  = b;
  assign \M_P.y  = \M_P.sel  ? \M_P.d1  : \M_P.d0 ;
  assign p = \M_P.y ;

  // sum = p ? ~cin : cin   (M_SUM)
  assign \M_SUM.sel  = p;
  assign \M_SUM.d1  = ~cin;
  assign \M_SUM.d0  = cin;
  assign \M_SUM.y  = \M_SUM.sel  ? \M_SUM.d1  : \M_SUM.d0 ;
  assign sum = \M_SUM.y ;

  // cout = p ? cin : a   (M_COUT)
  assign \M_COUT.sel  = p;
  assign \M_COUT.d1  = cin;
  assign \M_COUT.d0  = a;
  assign \M_COUT.y  = \M_COUT.sel  ? \M_COUT.d1  : \M_COUT.d0 ;
  assign cout = \M_COUT.y ;

endmodule
