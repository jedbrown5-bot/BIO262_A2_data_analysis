"""
BIO262 Port Macquarie Intensive, data analysis engine.

Loads the compiled field-data workbook, reshapes each metric to tidy long form,
and runs the statistical tests the assessment requires:

  Canopy height     one-way ANOVA across sites, Tukey post-hoc + letters
  Tree density      separate one-way ANOVA per size class (<10, >=10)
  Basal area        two-way ANOVA, site x method (Plot vs Factor Gauge)
  Canopy cover      two-way ANOVA, site x method (Line vs Densiometer)
  Shrub cover       two-way ANOVA, site x method (Line vs Subplot)
  Species richness  two-way ANOVA, site x class (Trees vs Shrubs)
  Ground cover      means + 95% CI table, both methods, no test
  Relative dominance stacked table, no test

Each of the four groups at a site is a replicate plot (n = 4, or 3 where a value
is missing). Two-way models treat the second factor as crossed with site.
"""
from __future__ import annotations
import io
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd

SITES = {1: "Swampy Paperbark", 2: "Wet Sclerophyll", 3: "Littoral Rainforest", 4: "Heathland"}
SITE_ORDER = [SITES[i] for i in (1, 2, 3, 4)]
GC_CATS = ["Native Grasses, Sedges & Graminoids", "Exotic Grasses, Sedges & Graminoids",
           "Orchids", "Herbs, Lilies & Forbs", "Vines & Scramblers", "Woody Seedlings",
           "Ferns", "Mosses & Lichens", "Fungi", "Leaf Litter", "Coarse Woody Debris", "Bare Ground"]


# ---------------------------------------------------------------- loading
def _find_header_row(ws, max_scan=4):
    for r in range(1, max_scan + 1):
        vals = [str(c.value).strip().lower() if c.value is not None else "" for c in ws[r]]
        if "site" in vals and "group" in vals:
            return r
    return 2


def _rows(ws, hr):
    """Return list of row tuples where Site is 1..4, with a 1-based column index map by header."""
    import openpyxl
    hdr = [c.value for c in ws[hr]]
    site_i = [i for i, h in enumerate(hdr) if str(h).strip().lower() == "site"][0]
    out = []
    for row in ws.iter_rows(min_row=hr + 1, values_only=True):
        s = row[site_i]
        if s in (1, 2, 3, 4):
            out.append(row)
    return hdr, out


def load_workbook_bytes(data):
    import openpyxl
    if isinstance(data, (bytes, bytearray)):
        data = io.BytesIO(data)
    return openpyxl.load_workbook(data, data_only=True)


def tidy_all(wb):
    """Return a dict of tidy DataFrames for every metric."""
    out = {}

    # canopy height: value in 'Height (m)'
    ws = wb["Canopy Height"]; hr = _find_header_row(ws, 1) or 1
    hdr, rows = _rows(ws, hr)
    hi = hdr.index("Height (m)"); si = hdr.index("Site"); gi = hdr.index("Group")
    out["canopy_height"] = pd.DataFrame(
        [{"site": SITES[r[si]], "group": r[gi], "value": r[hi]} for r in rows]
    ).dropna(subset=["value"])

    # tree density: per-hectare columns are the SECOND pair of duplicate headers
    ws = wb["Tree Density"]; hr = _find_header_row(ws)
    hdr, rows = _rows(ws, hr)
    si = hdr.index("Site"); gi = hdr.index("Group")
    lt_idx = [i for i, h in enumerate(hdr) if str(h).strip().startswith("Trees <")]
    ge_idx = [i for i, h in enumerate(hdr) if "≥" in str(h) or ">=" in str(h) or "≥" in str(h)]
    lt_ha = lt_idx[-1]; ge_ha = ge_idx[-1]  # per-ha = last occurrence
    recs = []
    for r in rows:
        recs.append({"site": SITES[r[si]], "group": r[gi], "class": "< 10 cm DBH", "value": r[lt_ha]})
        recs.append({"site": SITES[r[si]], "group": r[gi], "class": ">= 10 cm DBH", "value": r[ge_ha]})
    out["tree_density"] = pd.DataFrame(recs).dropna(subset=["value"])

    # two-method / two-class sheets: value cols J,K after Observer 5
    def two(sheet, name_a, name_b, factor):
        ws = wb[sheet]; hr = _find_header_row(ws)
        hdr, rows = _rows(ws, hr)
        si = hdr.index("Site"); gi = hdr.index("Group")
        # the two value columns are the first two non-empty headers after 'Observer 5'
        o5 = hdr.index("Observer 5")
        valcols = [i for i in range(o5 + 1, len(hdr)) if hdr[i] not in (None, "")][:2]
        recs = []
        for r in rows:
            recs.append({"site": SITES[r[si]], "group": r[gi], factor: name_a, "value": r[valcols[0]]})
            recs.append({"site": SITES[r[si]], "group": r[gi], factor: name_b, "value": r[valcols[1]]})
        return pd.DataFrame(recs).dropna(subset=["value"])

    out["basal_area"] = two("Basal Area", "Factor Gauge", "Plot", "method")
    out["canopy_cover"] = two("Canopy Cover", "Line Intercept", "Densiometer", "method")
    out["shrub_cover"] = two("Shrub Cover", "Line Intercept", "Subplot", "method")
    out["species_richness"] = two("Species Richness", "Shrubs", "Trees", "class")

    # ground cover: two blocks of 12 categories (Visual then Point Intercept)
    ws = wb["Ground Cover"]; hr = _find_header_row(ws)
    hdr, rows = _rows(ws, hr)
    si = hdr.index("Site"); gi = hdr.index("Group")
    o5 = hdr.index("Observer 5")
    catcols = [i for i in range(o5 + 1, len(hdr)) if hdr[i] not in (None, "")]
    visual = catcols[:12]; point = catcols[12:24]
    recs = []
    for r in rows:
        for meth, cols in [("Visual Estimation", visual), ("Point Intercept", point)]:
            for k, ci in enumerate(cols):
                recs.append({"site": SITES[r[si]], "group": r[gi], "method": meth,
                             "category": GC_CATS[k], "value": r[ci]})
    out["ground_cover"] = pd.DataFrame(recs).dropna(subset=["value"])

    # tree species composition for relative dominance
    ws = wb["Tree Species Composition"]; hr = _find_header_row(ws)
    hdr, rows = _rows(ws, hr)
    si = hdr.index("Site"); spi = hdr.index("Species"); bai = hdr.index("BA (m2)")
    recs = []
    for r in rows:
        if r[spi] and isinstance(r[bai], (int, float)):
            recs.append({"site": SITES[r[si]], "species": str(r[spi]).strip(), "ba": r[bai]})
    out["tree_comp"] = pd.DataFrame(recs)
    return out


# ---------------------------------------------------------------- stats helpers
def _t_crit(n, alpha=0.05):
    return stats.t.ppf(1 - alpha / 2, n - 1) if n > 1 else np.nan


def mean_ci_table(df, by):
    """Mean, sd, n, se, 95% CI half-width grouped by the columns in `by`."""
    g = df.groupby(by, sort=False)["value"]
    out = g.agg(["mean", "std", "count"]).reset_index()
    out["se"] = out["std"] / np.sqrt(out["count"])
    out["ci95"] = out.apply(lambda r: _t_crit(r["count"]) * r["se"] if r["count"] > 1 else 0.0, axis=1)
    return out


def compact_letters(levels, pvals_reject):
    """Compact letter display. pvals_reject: dict[(a,b)] -> True if significantly different."""
    def diff(a, b):
        return pvals_reject.get((a, b), pvals_reject.get((b, a), False))
    letters = {lv: [] for lv in levels}
    columns = []  # each column is a set of levels sharing that letter
    for lv in levels:
        placed = False
        for col in columns:
            if all(not diff(lv, other) for other in col):
                col.add(lv); placed = True; break
        if not placed:
            columns.append({lv})
    # absorb: remove columns that are subsets of others
    columns = [c for i, c in enumerate(columns)
               if not any(i != j and c < d for j, d in enumerate(columns))]
    label = {}
    for idx, col in enumerate(columns):
        ch = chr(ord("a") + idx)
        for lv in col:
            label.setdefault(lv, "")
            label[lv] += ch
    return {lv: "".join(sorted(label.get(lv, ""))) for lv in levels}


def oneway(df, factor="site", order=None):
    """One-way ANOVA + Tukey + compact letters. Returns dict."""
    d = df.dropna(subset=["value"]).copy()
    d[factor] = d[factor].astype(str)
    dm = d.rename(columns={factor: "A", "value": "y"})
    model = ols("y ~ C(A)", data=dm).fit()
    aov = sm.stats.anova_lm(model, typ=2).rename(index={"C(A)": factor})
    levels = order or list(dict.fromkeys(d[factor]))
    # assumptions + non-parametric alternative (Kruskal-Wallis)
    assump = check_assumptions(model, d, factor)
    try:
        groups = [g["value"].values for _, g in d.groupby(factor)]
        h, kp = stats.kruskal(*groups)
        assump["kruskal"] = {"stat": float(h), "df": len(groups) - 1, "p": float(kp)}
    except Exception as e:
        assump["kruskal"] = {"error": str(e)}
    res = {"anova": aov, "levels": levels, "assump": assump}
    # Tukey
    try:
        tuk = pairwise_tukeyhsd(d["value"], d[factor])
        tdf = pd.DataFrame(tuk.summary().data[1:], columns=tuk.summary().data[0])
        reject = {}
        for _, row in tdf.iterrows():
            reject[(str(row["group1"]), str(row["group2"]))] = bool(row["reject"])
        res["tukey"] = tdf
        res["letters"] = compact_letters(levels, reject)
    except Exception as e:
        res["tukey"] = None
        res["letters"] = {lv: "" for lv in levels}
        res["tukey_error"] = str(e)
    res["means"] = mean_ci_table(d, [factor])
    return res


def check_assumptions(model, d, groupcols):
    """Shapiro-Wilk on residuals (normality) and Levene across cells (equal variance)."""
    out = {}
    resid = np.asarray(model.resid)
    try:
        w, p = stats.shapiro(resid)
        out["shapiro"] = {"stat": float(w), "p": float(p), "n": len(resid)}
    except Exception as e:
        out["shapiro"] = {"error": str(e)}
    try:
        groups = [g["value"].values for _, g in d.groupby(groupcols)]
        groups = [g for g in groups if len(g) > 1]
        s, p = stats.levene(*groups, center="median")
        out["levene"] = {"stat": float(s), "p": float(p), "k": len(groups)}
    except Exception as e:
        out["levene"] = {"error": str(e)}
    return out


def scheirer_ray_hare(df, f1, f2):
    """Non-parametric two-way test (Scheirer-Ray-Hare). Ranks the data, then an
    ANOVA-style decomposition, comparing each H to chi-square. A rank-based
    alternative when normality or equal variance fail."""
    d = df.dropna(subset=["value"]).copy()
    d[f1] = d[f1].astype(str); d[f2] = d[f2].astype(str)
    dm = d.rename(columns={f1: "A", f2: "B"})
    dm["R"] = stats.rankdata(dm["value"])
    model = ols("R ~ C(A) * C(B)", data=dm).fit()
    aov = sm.stats.anova_lm(model, typ=2)
    ss_total = ((dm["R"] - dm["R"].mean()) ** 2).sum()
    ms_total = ss_total / (len(dm) - 1)
    rows = []
    label = {"C(A)": f1, "C(B)": f2, "C(A):C(B)": f"{f1} x {f2}"}
    for term in ["C(A)", "C(B)", "C(A):C(B)"]:
        ss = aov.loc[term, "sum_sq"]; dfree = int(aov.loc[term, "df"])
        H = ss / ms_total
        p = stats.chi2.sf(H, dfree)
        rows.append({"effect": label[term], "H": H, "df": dfree, "p": p})
    return pd.DataFrame(rows)


def _holm(pvals):
    """Holm-Bonferroni adjusted p-values, preserving input order."""
    idx = np.argsort(pvals)
    m = len(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(idx):
        val = (m - rank) * pvals[i]
        running = max(running, val)
        adj[i] = min(running, 1.0)
    return adj


def simple_effects(df, f1="site", f2="method", order1=None, order2=None):
    """
    Compare the two levels of f2 within each level of f1, paired by group.
    Each group measured both levels, so this is a paired (repeated measures) test.
    Returns a tidy DataFrame: one row per f1 level.
    """
    d = df.dropna(subset=["value"]).copy()
    d[f1] = d[f1].astype(str); d[f2] = d[f2].astype(str)
    levels1 = order1 or list(dict.fromkeys(d[f1]))
    levels2 = order2 or list(dict.fromkeys(d[f2]))
    a, b = levels2[0], levels2[1]
    rows = []
    for lv in levels1:
        sub = d[d[f1] == lv]
        wide = sub.pivot_table(index="group", columns=f2, values="value")
        if a not in wide or b not in wide:
            continue
        pair = wide[[a, b]].dropna()
        n = len(pair)
        rec = {f1: lv, f"{a} mean": pair[a].mean() if n else np.nan,
               f"{b} mean": pair[b].mean() if n else np.nan,
               "mean diff": (pair[a] - pair[b]).mean() if n else np.nan,
               "n pairs": n}
        if n >= 2 and (pair[a] - pair[b]).std(ddof=1) > 0:
            t, p = stats.ttest_rel(pair[a], pair[b])
            rec["t"] = t; rec["df"] = n - 1; rec["p"] = p
        else:
            rec["t"] = np.nan; rec["df"] = max(n - 1, 0)
            rec["p"] = np.nan if n < 2 else 1.0  # identical or single pair
        # non-parametric alternative: Wilcoxon signed-rank on the paired differences
        try:
            _, wp = stats.wilcoxon(pair[a], pair[b])
            rec["p (Wilcoxon)"] = float(wp)
        except Exception:
            rec["p (Wilcoxon)"] = np.nan
        rows.append(rec)
    out = pd.DataFrame(rows)
    valid = out["p"].notna()
    out["p (Holm)"] = np.nan
    if valid.any():
        out.loc[valid, "p (Holm)"] = _holm(out.loc[valid, "p"].values)
    out["sig"] = np.where(out["p (Holm)"] < 0.05, "yes", "no")
    out.attrs["levels2"] = (a, b)
    return out


def twoway(df, f1="site", f2="method", order1=None):
    """Two-way ANOVA with interaction. Tukey on f1 as a follow-up."""
    d = df.dropna(subset=["value"]).copy()
    d[f1] = d[f1].astype(str); d[f2] = d[f2].astype(str)
    dm = d.rename(columns={f1: "A", f2: "B", "value": "y"})
    model = ols("y ~ C(A) * C(B)", data=dm).fit()
    aov = sm.stats.anova_lm(model, typ=2).rename(
        index={"C(A)": f1, "C(B)": f2, "C(A):C(B)": f"{f1} x {f2}"})
    levels = order1 or list(dict.fromkeys(d[f1]))
    assump = check_assumptions(model, d, [f1, f2])
    res = {"anova": aov, "model": model, "levels": levels,
           "means": mean_ci_table(d, [f1, f2]), "f2_levels": list(dict.fromkeys(d[f2])),
           "simple": simple_effects(df, f1, f2, order1, list(dict.fromkeys(d[f2]))), "factor2": f2,
           "assump": assump, "srh": scheirer_ray_hare(df, f1, f2)}
    # Tukey on site (main effect follow-up)
    try:
        tuk = pairwise_tukeyhsd(d["value"], d[f1])
        tdf = pd.DataFrame(tuk.summary().data[1:], columns=tuk.summary().data[0])
        reject = {(str(r["group1"]), str(r["group2"])): bool(r["reject"]) for _, r in tdf.iterrows()}
        res["tukey_site"] = tdf
        res["letters_site"] = compact_letters(levels, reject)
    except Exception as e:
        res["tukey_site"] = None; res["letters_site"] = {lv: "" for lv in levels}
        res["tukey_error"] = str(e)
    return res


def ground_cover_table(gc):
    """Mean % and 95% CI per category, site and method. Returns tidy + a wide table per method."""
    tbl = mean_ci_table(gc, ["method", "site", "category"])
    return tbl


def relative_dominance(tree_comp, top_n=8):
    """Do_rel: species share of total plot basal area per site. Top N species + Other."""
    df = tree_comp.copy()
    site_tot = df.groupby("site")["ba"].sum()
    sp_tot = df.groupby(["site", "species"])["ba"].sum().reset_index()
    sp_tot["dorel"] = sp_tot.apply(lambda r: 100 * r["ba"] / site_tot[r["site"]] if site_tot[r["site"]] else 0, axis=1)
    overall = df.groupby("species")["ba"].sum().sort_values(ascending=False)
    top = list(overall.index[:top_n])
    wide = pd.DataFrame(index=top + ["Other species"], columns=SITE_ORDER, dtype=float).fillna(0.0)
    for _, r in sp_tot.iterrows():
        sp = r["species"] if r["species"] in top else "Other species"
        if r["site"] in wide.columns:
            wide.loc[sp, r["site"]] += r["dorel"]
    return wide


def run_all(wb):
    """Compute every analysis and return a results dict."""
    t = tidy_all(wb)
    R = {"tidy": t}
    R["canopy_height"] = oneway(t["canopy_height"], "site", SITE_ORDER)
    # tree density: separate one-way per size class
    td = {}
    for cls in ["< 10 cm DBH", ">= 10 cm DBH"]:
        td[cls] = oneway(t["tree_density"][t["tree_density"]["class"] == cls], "site", SITE_ORDER)
    R["tree_density"] = td
    R["basal_area"] = twoway(t["basal_area"], "site", "method", SITE_ORDER)
    R["canopy_cover"] = twoway(t["canopy_cover"], "site", "method", SITE_ORDER)
    R["shrub_cover"] = twoway(t["shrub_cover"], "site", "method", SITE_ORDER)
    R["species_richness"] = twoway(t["species_richness"], "site", "class", SITE_ORDER)
    R["ground_cover"] = ground_cover_table(t["ground_cover"])
    R["relative_dominance"] = relative_dominance(t["tree_comp"])
    return R
