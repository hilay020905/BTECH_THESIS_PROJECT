module maj(
    input w,
    input x,
    input y,
    output z
);

assign z = w&x | x&y | y&w;
endmodule