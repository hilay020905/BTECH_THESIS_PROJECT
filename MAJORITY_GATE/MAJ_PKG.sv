package maj_pkg;

  function automatic logic maj3(input logic a, input logic b, input logic c);
    maj3 = (a & b) | (b & c) | (a & c);
  endfunction

  function automatic logic [1:0] bullet(
      input logic highA, input logic highB,
      input logic lowA,  input logic lowB
  );

    bullet[1] = maj3(highA, highB, lowA);
    bullet[0] = maj3(highA, highB, lowB);
  endfunction

endpackage
