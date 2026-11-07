#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#include <unordered_map>
#include <chrono>
#include <algorithm>
extern "C" {
#include "cudd.h"
}
using namespace std;
typedef long long ll;
typedef chrono::steady_clock Clk;
static double ms_since(Clk::time_point t0) {
    return chrono::duration<double, milli>(Clk::now() - t0).count();
}

enum GT { AND_, OR_, XOR_ };
struct Gate { GT t; int x, y, out; string name; };
struct Op   { int hi, lo, wh, wl; bool hasP; };

static int N;
static int TOPO = 1;
static const char* TNAME[3] = {"KSA", "BKA", "SA"};
static vector<string> sigName;
static vector<Gate> gates;
static vector<Op> ops;
static vector<int> levelOfOp;
static int sig_a(int i) { return i; }
static int sig_b(int i) { return N + i; }
static vector<int> G_g, P_p, CAR, SUM;
static int newSig(const string& nm) { sigName.push_back(nm); return (int)sigName.size() - 1; }
static int addGate(GT t, int x, int y, const string& nm) {
    int o = newSig(nm);
    gates.push_back({t, x, y, o, nm});
    return o;
}

static void buildPrefix() {
    sigName.clear(); gates.clear(); ops.clear(); levelOfOp.clear();
    for (int i = 0; i < N; i++) newSig("a[" + to_string(i) + "]");
    for (int i = 0; i < N; i++) newSig("b[" + to_string(i) + "]");
    G_g.assign(N, 0); P_p.assign(N, 0);
    for (int i = 0; i < N; i++) {
        G_g[i] = addGate(AND_, sig_a(i), sig_b(i), "g" + to_string(i));
        P_p[i] = addGate(XOR_, sig_a(i), sig_b(i), "p" + to_string(i));
    }
    vector<int> Gs(G_g), Ps(P_p), lo(N);
    for (int i = 0; i < N; i++) lo[i] = i;
    auto op = [&](int hi, int j, int lvl) {
        int wh = hi - lo[hi] + 1, wl = j - lo[j] + 1;
        if (lo[hi] != j + 1) { fprintf(stderr, "prefix construction error\n"); exit(1); }
        string r = to_string(hi) + "_" + to_string(lo[j]);
        int t = addGate(AND_, Ps[hi], Gs[j], "t" + r);
        int g = addGate(OR_, Gs[hi], t, "G" + r);
        bool hasP = (lo[j] != 0);
        int p = Ps[hi];
        if (hasP) p = addGate(AND_, Ps[hi], Ps[j], "P" + r);
        ops.push_back({hi, j, wh, wl, hasP});
        levelOfOp.push_back(lvl);
        Gs[hi] = g; Ps[hi] = p; lo[hi] = lo[j];
    };
    int m = 0; while ((1 << m) < N) m++;
    int lvl = 0;
    if (TOPO == 1) {
        for (int l = 1; l <= m; l++) {
            lvl++;
            for (int i = (1 << l) - 1; i < N; i += (1 << l)) op(i, i - (1 << (l - 1)), lvl);
        }
        for (int l = m - 1; l >= 1; l--) {
            lvl++;
            for (int i = 3 * (1 << (l - 1)) - 1; i < N; i += (1 << l)) op(i, i - (1 << (l - 1)), lvl);
        }
    } else if (TOPO == 0) {
        for (int l = 0; l < m; l++) {
            lvl++;
            int d = 1 << l;
            for (int i = N - 1; i >= d; i--) op(i, i - d, lvl);
        }
    } else {
        for (int l = 1; l <= m; l++) {
            lvl++;
            int blk = 1 << l, half = blk >> 1;
            for (int st = 0; st < N; st += blk)
                for (int i = st + half; i < st + blk; i++) op(i, st + half - 1, lvl);
        }
    }
    CAR.assign(N + 1, -1);
    CAR[1] = G_g[0];
    for (int k = 2; k <= N; k++) CAR[k] = Gs[k - 1];
    for (int i = 0; i < N; i++) if (lo[i] != 0) { fprintf(stderr, "prefix incomplete\n"); exit(1); }
    SUM.assign(N + 1, -1);
    SUM[0] = P_p[0];
    for (int i = 1; i < N; i++) SUM[i] = addGate(XOR_, P_p[i], CAR[i], "s" + to_string(i));
    SUM[N] = CAR[N];
}

static void writeVerilog(const char* fn) {
    FILE* f = fopen(fn, "w");
    if (!f) return;
    fprintf(f, "module %s%d(input [%d:0] a, input [%d:0] b, output [%d:0] s);\n", TNAME[TOPO], N, N - 1, N - 1, N);
    for (auto& g : gates) fprintf(f, "  wire %s;\n", g.name.c_str());
    const char* sym[] = {"&", "|", "^"};
    for (auto& g : gates)
        fprintf(f, "  assign %s = %s %s %s;\n", g.name.c_str(), sigName[g.x].c_str(), sym[g.t], sigName[g.y].c_str());
    for (int k = 1; k <= N; k++) fprintf(f, "  wire c%d = %s;\n", k, sigName[CAR[k]].c_str());
    for (int i = 0; i <= N; i++) fprintf(f, "  assign s[%d] = %s;\n", i, sigName[SUM[i]].c_str());
    fprintf(f, "endmodule\n");
    fclose(f);
}

struct Res {
    int n; int topo;
    ll levels, nops, depth, fan, span, ngates;
    bool bvOK; ll bvPeak, bvBound; double bvMs;
    bool scaRan, scaAborted, scaOK; ll scaPeak; double scaMs;
    bool lemOK; int lemN; ll bsPeak, bsBound, bsSca, bsTotal; bool bsOK; double bsMs;
};
static vector<Res> RESULTS;

static void report_structure(Res& R) {
    int nsig = (int)sigName.size();
    vector<int> depth(nsig, 0), fan(nsig, 0);
    int maxd = 0, maxf = 0;
    for (auto& g : gates) {
        depth[g.out] = max(depth[g.x], depth[g.y]) + 1;
        fan[g.x]++; fan[g.y]++;
        maxd = max(maxd, depth[g.out]);
    }
    for (int i = 0; i < nsig; i++) maxf = max(maxf, fan[i]);
    int levels = 0; ll span = 0;
    for (size_t i = 0; i < ops.size(); i++) { levels = max(levels, levelOfOp[i]); span += ops[i].hi - ops[i].lo; }
    R.levels = levels; R.nops = (ll)ops.size(); R.depth = maxd; R.fan = maxf; R.span = span; R.ngates = (ll)gates.size();
    printf("STRUCTURE (n=%d): prefix levels=%d operators=%zu logic depth=%d max fan-out=%d wire span=%lld gates=%zu\n",
           N, levels, ops.size(), maxd, maxf, span, gates.size());
}

static ll cpxOpAB(const Op& o) {
    ll wh = o.wh, wl = o.wl;
    ll c = (3 * wh + 2) * (3 * wl + 1) + (3 * wh + 1) * (3 * (wh + wl) + 1);
    if (o.hasP) c += (3 * wh + 2) * (3 * wl + 2);
    return c;
}
static ll cpxOpGP(const Op& o) {
    ll wh = o.wh, wl = o.wl;
    ll c = (wh + 2) * (2 * wl + 1) + (2 * wh + 1) * (wh + 2 * wl + 1);
    if (o.hasP) c += (wh + 2) * (wl + 2);
    return c;
}

static const int W = 10;
struct Mono { uint64_t w[W]; };
struct MH { size_t operator()(const Mono& m) const {
    uint64_t h = 1469598103934665603ULL;
    for (int i = 0; i < W; i++) { h ^= m.w[i]; h *= 1099511628211ULL; h ^= h >> 29; }
    return (size_t)h; } };
struct ME { bool operator()(const Mono& a, const Mono& b) const { return memcmp(a.w, b.w, sizeof(a.w)) == 0; } };
typedef __int128 coef;
typedef unordered_map<Mono, coef, MH, ME> Poly;
typedef vector<pair<Mono, coef>> PolyV;
static Mono one_var(int v) { Mono m; memset(m.w, 0, sizeof(m.w)); m.w[v >> 6] |= 1ULL << (v & 63); return m; }
static Mono unite(const Mono& a, const Mono& b) { Mono m; for (int i = 0; i < W; i++) m.w[i] = a.w[i] | b.w[i]; return m; }
static Mono empty_mono() { Mono m; memset(m.w, 0, sizeof(m.w)); return m; }
static bool has(const Mono& m, int v) { return (m.w[v >> 6] >> (v & 63)) & 1; }
static void drop(Mono& m, int v) { m.w[v >> 6] &= ~(1ULL << (v & 63)); }
static void addTerm(Poly& P, const Mono& m, coef c) {
    if (c == 0) return;
    auto it = P.find(m);
    if (it == P.end()) P.emplace(m, c);
    else { it->second += c; if (it->second == 0) P.erase(it); }
}
static bool substitute(Poly& P, int v, const PolyV& Q, size_t limit, size_t& peak) {
    vector<pair<Mono, coef>> hit;
    for (auto& kv : P) if (has(kv.first, v)) hit.push_back(kv);
    if (hit.empty()) return true;
    for (auto& h : hit) P.erase(h.first);
    for (auto& h : hit) {
        Mono base = h.first; drop(base, v);
        for (auto& q : Q) {
            addTerm(P, unite(base, q.first), h.second * q.second);
            if (P.size() > limit) { peak = max(peak, P.size()); return false; }
        }
    }
    peak = max(peak, P.size());
    return true;
}
static PolyV gatePoly(GT t, int x, int y) {
    Mono mx = one_var(x), my = one_var(y), mxy = unite(mx, my);
    if (t == AND_) return {{mxy, 1}};
    if (t == OR_)  return {{mx, 1}, {my, 1}, {mxy, -1}};
    return {{mx, 1}, {my, 1}, {mxy, -2}};
}

struct BddRun { size_t peak; double ms; bool ok; };

static BddRun runBDDV() {
    auto t0 = Clk::now();
    DdManager* dd = Cudd_Init(0, 0, CUDD_UNIQUE_SLOTS, CUDD_CACHE_SLOTS, 0);
    vector<DdNode*> A(N), B(N);
    for (int i = N - 1; i >= 0; i--) {
        A[i] = Cudd_bddNewVar(dd); Cudd_Ref(A[i]);
        B[i] = Cudd_bddNewVar(dd); Cudd_Ref(B[i]);
    }
    vector<DdNode*> f(sigName.size(), nullptr);
    for (int i = 0; i < N; i++) { f[sig_a(i)] = A[i]; f[sig_b(i)] = B[i]; }
    for (auto& g : gates) {
        DdNode* r = (g.t == AND_) ? Cudd_bddAnd(dd, f[g.x], f[g.y])
                  : (g.t == OR_)  ? Cudd_bddOr(dd, f[g.x], f[g.y])
                                  : Cudd_bddXor(dd, f[g.x], f[g.y]);
        Cudd_Ref(r); f[g.out] = r;
    }
    bool ok = true;
    DdNode* c = Cudd_Not(Cudd_ReadOne(dd)); Cudd_Ref(c);
    for (int i = 0; i < N; i++) {
        DdNode* x = Cudd_bddXor(dd, A[i], B[i]); Cudd_Ref(x);
        DdNode* s = Cudd_bddXor(dd, x, c); Cudd_Ref(s);
        if (s != f[SUM[i]]) ok = false;
        DdNode* g1 = Cudd_bddAnd(dd, A[i], B[i]); Cudd_Ref(g1);
        DdNode* g2 = Cudd_bddAnd(dd, x, c); Cudd_Ref(g2);
        DdNode* cn = Cudd_bddOr(dd, g1, g2); Cudd_Ref(cn);
        c = cn;
    }
    if (c != f[SUM[N]]) ok = false;
    size_t peak = (size_t)Cudd_ReadPeakLiveNodeCount(dd);
    BddRun r{peak, ms_since(t0), ok};
    Cudd_Quit(dd);
    return r;
}

struct ScaRun { size_t peak; double ms; bool ok, aborted; size_t remTerms; };
static ScaRun runSCAV(size_t limit) {
    auto t0 = Clk::now();
    Poly P; size_t peak = 0;
    for (int i = 0; i < N; i++) {
        addTerm(P, one_var(SUM[i]), ((coef)1 << i));
        addTerm(P, one_var(sig_a(i)), -(((coef)1 << i)));
        addTerm(P, one_var(sig_b(i)), -(((coef)1 << i)));
    }
    addTerm(P, one_var(SUM[N]), ((coef)1 << N));
    peak = P.size();
    bool okrun = true;
    vector<int> dep(sigName.size(), 0), ord;
    for (auto& g : gates) dep[g.out] = max(dep[g.x], dep[g.y]) + 1;
    for (int i = 0; i < (int)gates.size(); i++) ord.push_back(i);
    sort(ord.begin(), ord.end(), [&](int a, int b) {
        int da = dep[gates[a].out], db = dep[gates[b].out];
        return da != db ? da > db : a > b; });
    for (int gi : ord) {
        auto& g = gates[gi];
        if (!substitute(P, g.out, gatePoly(g.t, g.x, g.y), limit, peak)) { okrun = false; break; }
    }
    ScaRun r;
    r.peak = peak; r.ms = ms_since(t0); r.aborted = !okrun; r.remTerms = P.size();
    r.ok = okrun && P.empty();
    return r;
}

struct BscvRun { size_t bddPeak, scaPeak, scaPeakStep; ll bddBound; double ms; bool lemmasOK, scaOK; int lemmasProved; };
static BscvRun runBSCV() {
    auto t0 = Clk::now();
    BscvRun R{};
    DdManager* dd = Cudd_Init(0, 0, CUDD_UNIQUE_SLOTS, CUDD_CACHE_SLOTS, 0);
    vector<DdNode*> g(N), p(N);
    for (int i = N - 1; i >= 0; i--) {
        g[i] = Cudd_bddNewVar(dd); Cudd_Ref(g[i]);
        p[i] = Cudd_bddNewVar(dd); Cudd_Ref(p[i]);
    }
    vector<DdNode*> f(sigName.size(), nullptr);
    for (int i = 0; i < N; i++) { f[G_g[i]] = g[i]; f[P_p[i]] = p[i]; }
    size_t firstOp = 2 * (size_t)N, lastOp = gates.size() - (size_t)(N - 1);
    for (size_t gi = firstOp; gi < lastOp; gi++) {
        auto& gt = gates[gi];
        DdNode* r = (gt.t == AND_) ? Cudd_bddAnd(dd, f[gt.x], f[gt.y]) : Cudd_bddOr(dd, f[gt.x], f[gt.y]);
        Cudd_Ref(r); f[gt.out] = r;
    }
    R.lemmasOK = true; R.lemmasProved = 0;
    DdNode* cPrev = Cudd_Not(Cudd_ReadOne(dd));
    for (int k = 1; k <= N; k++) {
        DdNode* t = Cudd_bddAnd(dd, p[k - 1], cPrev); Cudd_Ref(t);
        DdNode* ripple = Cudd_bddOr(dd, g[k - 1], t); Cudd_Ref(ripple);
        DdNode* net = f[CAR[k]];
        if (net == ripple) R.lemmasProved++; else R.lemmasOK = false;
        cPrev = net;
    }
    R.bddPeak = (size_t)Cudd_ReadPeakLiveNodeCount(dd);
    Cudd_Quit(dd);
    R.bddBound = 0; for (auto& o : ops) R.bddBound += cpxOpGP(o);
    auto vA = [&](int i) { return i; };
    auto vB = [&](int i) { return N + i; };
    auto vG = [&](int i) { return 2 * N + i; };
    auto vP = [&](int i) { return 3 * N + i; };
    auto vC = [&](int k) { return 4 * N + (k - 1); };
    auto vS = [&](int i) { return 5 * N + i; };
    Poly P; size_t peak, peakStep;
    for (int i = 0; i < N; i++) {
        addTerm(P, one_var(vS(i)), ((coef)1 << i));
        addTerm(P, one_var(vA(i)), -(((coef)1 << i)));
        addTerm(P, one_var(vB(i)), -(((coef)1 << i)));
    }
    addTerm(P, one_var(vC(N)), ((coef)1 << N));
    peak = peakStep = P.size();
    const size_t LIM = 2000000;
    bool okrun = true;
    for (int i = 0; i < N && okrun; i++) {
        PolyV Q;
        Q.push_back({one_var(vP(i)), 1});
        if (i >= 1) {
            Q.push_back({one_var(vC(i)), 1});
            Q.push_back({unite(one_var(vP(i)), one_var(vC(i))), -2});
        }
        okrun = substitute(P, vS(i), Q, LIM, peakStep);
    }
    peak = max(peak, P.size());
    for (int k = N; k >= 1 && okrun; k--) {
        PolyV Q2;
        Q2.push_back({one_var(vG(k - 1)), 1});
        if (k >= 2) {
            Mono pc = unite(one_var(vP(k - 1)), one_var(vC(k - 1)));
            Q2.push_back({pc, 1});
            Q2.push_back({unite(one_var(vG(k - 1)), pc), -1});
        }
        okrun = substitute(P, vC(k), Q2, LIM, peakStep);
        if (!okrun) break;
        Mono ab = unite(one_var(vA(k - 1)), one_var(vB(k - 1)));
        PolyV Qg = {{ab, 1}};
        PolyV Qp = {{one_var(vA(k - 1)), 1}, {one_var(vB(k - 1)), 1}, {ab, -2}};
        okrun = substitute(P, vG(k - 1), Qg, LIM, peakStep) && substitute(P, vP(k - 1), Qp, LIM, peakStep);
        peak = max(peak, P.size());
    }
    R.scaPeak = peak; R.scaPeakStep = peakStep;
    R.scaOK = okrun && P.empty();
    R.ms = ms_since(t0);
    return R;
}

static bool runOne(int argc, char** argv) {
    buildPrefix();
    Res R{};
    R.n = N; R.topo = TOPO;
    char fn[64]; snprintf(fn, sizeof(fn), "%s%d_NETLIST.V", TNAME[TOPO], N);
    writeVerilog(fn);
    printf("==================== %s %d-bit  (carries c1..c%d; Verilog netlist: %s) ====================\n", TNAME[TOPO], N, N, fn);
    report_structure(R);
    ll stage13 = 36LL * N + 25LL * (N - 1) * (3 * N + 2) / 2;
    ll bddvBound = stage13, bscvBound = 0;
    for (auto& o : ops) { bddvBound += cpxOpAB(o); bscvBound += cpxOpGP(o); }
    printf("COST MODEL: BDD-V bound=%lld (stages 1,3 = %lld)   BSCV BDD bound=%lld\n", bddvBound, stage13, bscvBound);

    printf("[1/3] BDD-V  (MSB-first interleaved order a%d,b%d,...,a0,b0)\n", N - 1, N - 1);
    BddRun bv = runBDDV();
    printf("      verdict=%s  peak live nodes=%zu  time=%.2f ms\n", bv.ok ? "EQUIVALENT" : "NOT EQUIVALENT", bv.peak, bv.ms);
    R.bvOK = bv.ok; R.bvPeak = (ll)bv.peak; R.bvBound = bddvBound; R.bvMs = bv.ms;

    printf("[2/3] SCA-V  (whole netlist, reverse topological order, abort at 2e6 terms)\n");
    if (N <= 16 || (argc > 3 && !strcmp(argv[3], "FORCE"))) {
        ScaRun sv = runSCAV(2000000);
        R.scaRan = true; R.scaAborted = sv.aborted; R.scaOK = sv.ok; R.scaPeak = (ll)sv.peak; R.scaMs = sv.ms;
        if (sv.aborted) printf("      verdict=UNDECIDED (aborted)  peak terms>%zu  time=%.2f ms\n", sv.peak, sv.ms);
        else printf("      verdict=%s  peak terms=%zu  remainder terms=%zu  time=%.2f ms\n",
                    sv.ok ? "VERIFIED (remainder 0)" : "NOT VERIFIED", sv.peak, sv.remTerms, sv.ms);
    } else printf("      skipped for n>16 (SCA-V aborts at n=32). Add FORCE as 3rd argument to try.\n");

    printf("[3/3] BSCV   (cut at g,p -> BDD lemmas over (g,p) -> SCA rules R3,R2,R1)\n");
    BscvRun bs = runBSCV();
    printf("      stage 2 lemmas proved: %d/%d (%s)   BDD peak nodes=%zu   BDD bound=%lld\n",
           bs.lemmasProved, N, bs.lemmasOK ? "all L_k hold" : "FAILED", bs.bddPeak, bs.bddBound);
    printf("      stage 3 SCA: remainder %s   peak terms=%zu  expected 5n-1=%d   time(total)=%.2f ms\n",
           bs.scaOK ? "= 0 -> VERIFIED" : "!= 0", bs.scaPeak, 5 * N - 1, bs.ms);
    printf("      BSCV total (BDD peak + SCA peak) = %zu\n\n", bs.bddPeak + bs.scaPeak);
    R.lemOK = bs.lemmasOK; R.lemN = bs.lemmasProved; R.bsPeak = (ll)bs.bddPeak; R.bsBound = bs.bddBound;
    R.bsSca = (ll)bs.scaPeak; R.bsTotal = (ll)(bs.bddPeak + bs.scaPeak); R.bsOK = bs.scaOK; R.bsMs = bs.ms;
    RESULTS.push_back(R);
    return bv.ok && bs.lemmasOK && bs.scaOK;
}

static string fmt(ll v) {
    string t = to_string(v), o;
    int c = 0;
    for (int i = (int)t.size() - 1; i >= 0; i--) { o.insert(o.begin(), t[i]); if (++c % 3 == 0 && i > 0) o.insert(o.begin(), ','); }
    return o;
}

static string cells(const char* label, ll Res::*field, bool hdrNote = false) {
    string r = "<tr><td>" + string(label) + "</td>";
    ll best = -1;
    for (auto& R : RESULTS) if (best < 0 || R.*field < best) best = R.*field;
    for (auto& R : RESULTS) {
        bool isBest = RESULTS.size() > 1 && R.*field == best;
        r += "<td class=\"num" + string(isBest ? " best" : "") + "\">" + fmt(R.*field) + "</td>";
    }
    return r + "</tr>\n";
}

static string section(const char* title) {
    return "<tr class=\"sec\"><td colspan=\"" + to_string(RESULTS.size() + 1) + "\">" + title + "</td></tr>\n";
}

static string textRow(const char* label, const vector<string>& v, const vector<bool>& good) {
    string r = "<tr><td>" + string(label) + "</td>";
    for (size_t i = 0; i < v.size(); i++) r += "<td class=\"num " + string(good[i] ? "ok" : "bad") + "\">" + v[i] + "</td>";
    return r + "</tr>\n";
}

static void writeHtml(bool allOK) {
    static const char* full[3] = {"Kogge&ndash;Stone", "Brent&ndash;Kung", "Sklansky"};
    string t = "<table><thead><tr><th>Metric</th>";
    for (auto& R : RESULTS) t += "<th>" + string(full[R.topo]) + "<small>" + TNAME[R.topo] + "</small></th>";
    t += "</tr></thead><tbody>\n";
    t += section("Circuit structure");
    t += cells("Prefix levels", &Res::levels);
    t += cells("Operators", &Res::nops);
    t += cells("Logic depth (gate levels)", &Res::depth);
    t += cells("Max fan-out", &Res::fan);
    t += cells("Wire span", &Res::span);
    t += cells("Gates", &Res::ngates);
    t += section("BDD-V &mdash; plain BDD verification");
    {
        vector<string> v; vector<bool> g;
        for (auto& R : RESULTS) { v.push_back(R.bvOK ? "&#10003; equivalent" : "&#10007; not equivalent"); g.push_back(R.bvOK); }
        t += textRow("Verdict", v, g);
    }
    t += cells("Peak BDD nodes", &Res::bvPeak);
    t += cells("Cost bound", &Res::bvBound);
    t += section("SCA-V &mdash; plain algebraic verification");
    {
        vector<string> v; vector<bool> g;
        for (auto& R : RESULTS) {
            if (!R.scaRan) { v.push_back("skipped"); g.push_back(true); }
            else if (R.scaAborted) { v.push_back("aborted (&gt; 2,000,000 terms)"); g.push_back(false); }
            else { v.push_back(R.scaOK ? "&#10003; remainder 0" : "&#10007; remainder not 0"); g.push_back(R.scaOK); }
        }
        t += textRow("Verdict", v, g);
        vector<string> p; vector<bool> pg;
        for (auto& R : RESULTS) { p.push_back(R.scaRan ? fmt(R.scaPeak) : "&mdash;"); pg.push_back(true); }
        t += textRow("Peak polynomial terms", p, pg);
    }
    t += section("BSCV &mdash; BDD + SCA co-verification");
    {
        vector<string> v, w; vector<bool> g, h;
        for (auto& R : RESULTS) {
            v.push_back(R.lemOK ? "&#10003; " + to_string(R.lemN) + " / " + to_string(R.n) + " proved" : "&#10007; failed"); g.push_back(R.lemOK);
            w.push_back(R.bsOK ? "&#10003; remainder 0" : "&#10007; remainder not 0"); h.push_back(R.bsOK);
        }
        t += textRow("Carry lemmas L<sub>k</sub>", v, g);
        t += cells("BDD peak nodes", &Res::bsPeak);
        t += cells("BDD cost bound", &Res::bsBound);
        t += cells("SCA peak terms (5n&minus;1)", &Res::bsSca);
        t += textRow("Final SCA verdict", w, h);
        t += cells("BSCV total (BDD + SCA peak)", &Res::bsTotal);
    }
    t += "</tbody></table>\n";

    FILE* f = fopen("RESULTS.HTML", "w");
    if (!f) return;
    fputs(R"(<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>BSCV results</title><style>
:root{--bg:#f4f5f8;--card:#fff;--ink:#14171c;--dim:#778092;--line:#e4e7ec;--ok:#0f8a4b;--okbg:#e4f5ec;--bad:#c62828;--badbg:#fdeaea;--head:#eef1f6;--acc:#2c5fd8;--best:#fff6d6}
@media (prefers-color-scheme:dark){:root{--bg:#0f1217;--card:#171b22;--ink:#eceff4;--dim:#8d96a3;--line:#2a303a;--ok:#4ed08a;--okbg:#14301f;--bad:#ff7b7b;--badbg:#3a1b1b;--head:#1e232c;--acc:#7ea2ff;--best:#3a3418}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.5 system-ui,Segoe UI,Roboto,sans-serif;padding:32px 18px 56px}
.wrap{max-width:1080px;margin:0 auto}h1{font-size:30px;margin:0 0 4px;letter-spacing:-.01em}.sub{color:var(--dim);margin:0 0 22px}
.banner{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}.pill{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 20px;min-width:170px}
.pill b{font-size:24px;display:block;line-height:1.25}.pill span{color:var(--dim);font-size:14px}.pill.ok{background:var(--okbg);border-color:var(--ok)}.pill.ok b{color:var(--ok)}.pill.bad{background:var(--badbg);border-color:var(--bad)}.pill.bad b{color:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:6px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:16px}
th{text-align:right;padding:14px 16px;font-size:18px;font-weight:700;background:var(--head)}th:first-child{text-align:left;color:var(--dim);font-size:13px;text-transform:uppercase;letter-spacing:.06em;border-radius:12px 0 0 0}th:last-child{border-radius:0 12px 0 0}
th small{display:block;font-size:12px;font-weight:600;color:var(--acc);letter-spacing:.08em}
td{padding:10px 16px;border-bottom:1px solid var(--line);white-space:nowrap}td.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:500}
tr.sec td{background:var(--head);color:var(--acc);font-weight:700;font-size:14px;text-transform:uppercase;letter-spacing:.05em;border-bottom:none;padding:9px 16px}
td.best{background:var(--best);font-weight:700}td.ok{color:var(--ok);font-weight:600}td.bad{color:var(--bad);font-weight:700}
tbody tr:last-child td{border-bottom:none}
.note{color:var(--dim);font-size:14px;margin-top:18px}
</style></head><body><div class="wrap">
<h1>BSCV: Polynomial Formal Verification of Parallel Prefix Adders</h1>
<p class="sub">Measured results from this computer.</p>
)", f);
    char buf[512];
    snprintf(buf, sizeof(buf), "<div class=\"banner\"><div class=\"pill %s\"><b>%s</b><span>BDD-V and BSCV</span></div><div class=\"pill\"><b>%d-bit</b><span>adder width</span></div><div class=\"pill\"><b>c1 &ndash; c%d</b><span>carries verified</span></div></div>\n<div class=\"card\">\n",
             allOK ? "ok" : "bad", allOK ? "ALL VERIFIED" : "FAILED", N, N);
    fputs(buf, f);
    fputs(t.c_str(), f);
    fputs("</div><p class=\"note\">Highlighted cells mark the lowest value in each row. SCA-V is run only at 16 bits because it becomes infeasible at 32 bits.</p></div></body></html>\n", f);
    fclose(f);
}

int main(int argc, char** argv) {
    N = (argc > 1) ? atoi(argv[1]) : 16;
    if (N < 4 || N > 64 || (N & (N - 1))) { fprintf(stderr, "n must be a power of two in 4..64\n"); return 1; }
    string which = (argc > 2) ? argv[2] : "ALL";
    bool all = true;
    for (int t = 0; t < 3; t++) {
        if (which != "ALL" && which != TNAME[t]) continue;
        TOPO = t;
        all = runOne(argc, argv) && all;
    }
    writeHtml(all);
    printf("RESULT: %s\n", all ? "all selected adders VERIFIED by BDD-V and BSCV" : "VERIFICATION FAILED");
    printf("Visual report written to RESULTS.HTML\n");
    return all ? 0 : 2;
}
