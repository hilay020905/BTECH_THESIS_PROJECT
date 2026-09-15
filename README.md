Used verilator
```
export VERILATOR_ROOT=$HOME/verilator
$VERILATOR_ROOT/bin/verilator_bin --binary --timing --coverage --top-module tb_maj_adders_cov -Wno-fatal \
  MAJ_PKG.sv MAJ_KOGGE_STONE_ADDER.sv MAJ_LADNER_FISCHER_ADDER.sv MAJ_BRENT_KUNG_ADDER.sv TB_MAJ_ADDERS_COV.sv

./obj_dir/Vtb_maj_adders_cov
```
