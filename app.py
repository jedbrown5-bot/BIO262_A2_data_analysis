"""
BIO262 Port Macquarie Intensive, data analysis tool (staff answer key).

Runs every statistical test the assessment requires on the compiled class data
and shows the ANOVA tables, post-hoc groupings, means and 95% CIs, and the figures.

Run:  streamlit run app.py
"""
import io
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

import analysis as A

st.set_page_config(page_title="BIO262 PMQ Analysis", layout="wide", page_icon="🌿")

SITE_COLORS = {"Swampy Paperbark": "#4E79A7", "Wet Sclerophyll": "#59A14F",
               "Littoral Rainforest": "#8CD17D", "Heathland": "#E15759"}
SERIES_COLORS = ["#4E79A7", "#E1812C"]
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})

DATA_DEFAULT = os.path.join(os.path.dirname(__file__), "data", "PMQ_combined_data_2026.xlsx")


@st.cache_data(show_spinner=False)
def load(_bytes):
    wb = A.load_workbook_bytes(_bytes)
    return A.run_all(wb)


def p_fmt(p):
    return "< 0.001" if p < 0.001 else f"= {p:.3f}"


def aov_line(aov, factor, resid="Residual"):
    row = aov.loc[factor]
    dfr = int(aov.loc[resid, "df"])
    return f"F({int(row['df'])}, {dfr}) = {row['F']:.2f}, p {p_fmt(row['PR(>F)'])}"


def sig_word(p):
    return "a significant" if p < 0.05 else "no significant"


def fmtp(p):
    try:
        return "< 0.001" if p < 0.001 else f"{p:.3f}"
    except Exception:
        return "n/a"


def assumption_block(res, is_two):
    a = res.get("assump", {})
    sh = a.get("shapiro", {}); lv = a.get("levene", {})
    with st.expander("Assumptions and non-parametric alternative"):
        if "p" in sh:
            ok = sh["p"] >= 0.05
            st.markdown(f"- **Normality of residuals (Shapiro-Wilk):** W = {sh['stat']:.3f}, "
                        f"p = {fmtp(sh['p'])}. " +
                        ("Residuals are consistent with a normal distribution." if ok
                         else "Normality is doubtful, the residuals depart from normal."))
        if "p" in lv:
            ok = lv["p"] >= 0.05
            st.markdown(f"- **Equal variance (Levene):** stat = {lv['stat']:.3f}, p = {fmtp(lv['p'])}. " +
                        ("Variances look homogeneous across groups." if ok
                         else "Variances differ across groups."))
        if is_two:
            st.markdown("**Non-parametric alternative, Scheirer-Ray-Hare** (ranks the data, then a "
                        "two-way decomposition against chi-square):")
            st.dataframe(res["srh"].round(4), hide_index=True, width="stretch")
        else:
            kw = a.get("kruskal", {})
            if "p" in kw:
                st.markdown(f"**Non-parametric alternative, Kruskal-Wallis:** H = {kw['stat']:.3f}, "
                            f"df = {kw['df']}, p = {fmtp(kw['p'])}.")
            dn = a.get("dunn", {})
            if isinstance(dn, dict) and "letters" in dn:
                st.markdown("**Dunn's test (Holm), the non-parametric post-hoc (the rank-based "
                            "counterpart to Tukey):** " +
                            ", ".join(f"{s} ({dn['letters'].get(s, '')})" for s in A.SITE_ORDER
                                      if s in dn["letters"]))
                st.dataframe(dn["table"].round(4), hide_index=True, width="stretch")
        bad = (sh.get("p", 1) < 0.05) or (lv.get("p", 1) < 0.05)
        alt = "Scheirer-Ray-Hare" if is_two else "Kruskal-Wallis"
        if bad:
            st.info(f"At least one assumption is questionable here. Lean on the {alt} result, or try a "
                    "transformation such as log or square root before the ANOVA. With only 3 to 4 "
                    "replicates per group these assumption tests are themselves low powered, so use "
                    "judgement and look at the figure.")
        else:
            st.caption(f"Assumptions look acceptable, so the ANOVA is appropriate. {alt} is shown for comparison.")


# ---------- figures ----------
def fig_oneway(means, letters, ylabel, title):
    order = A.SITE_ORDER
    m = means.set_index("site").reindex(order)
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    x = np.arange(len(order))
    vals = m["mean"].values
    ci = m["ci95"].values
    lower = np.minimum(vals, ci)  # cap at 0
    ax.bar(x, vals, color=[SITE_COLORS[s] for s in order], width=0.62,
           yerr=[lower, ci], capsize=4, error_kw=dict(lw=1))
    for i, s in enumerate(order):
        top = vals[i] + ci[i]
        lt = letters.get(s, "")
        if lt:
            ax.text(i, top + max(vals) * 0.03, lt, ha="center", va="bottom", fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(order, rotation=15, ha="right")
    ax.set_ylabel(ylabel); ax.set_title(title, fontweight="bold")
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


def fig_twoway(means, factor, ylabel, title):
    order = A.SITE_ORDER
    levels = list(dict.fromkeys(means[factor]))
    x = np.arange(len(order)); w = 0.38
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    for k, lv in enumerate(levels):
        sub = means[means[factor] == lv].set_index("site").reindex(order)
        vals = sub["mean"].values; ci = sub["ci95"].values
        lower = np.minimum(vals, ci)
        ax.bar(x + (k - 0.5) * w, vals, width=w, label=lv, color=SERIES_COLORS[k % 2],
               yerr=[lower, ci], capsize=3, error_kw=dict(lw=0.9))
    ax.set_xticks(x); ax.set_xticklabels(order, rotation=15, ha="right")
    ax.set_ylabel(ylabel); ax.set_title(title, fontweight="bold")
    ax.set_ylim(bottom=0); ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def fig_stacked(wide, ylabel, title, percent=False):
    order = [c for c in A.SITE_ORDER if c in wide.columns]
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    bottom = np.zeros(len(order))
    cmap = plt.get_cmap("tab20")
    for i, idx in enumerate(wide.index):
        vals = wide.loc[idx, order].values.astype(float)
        ax.bar(order, vals, bottom=bottom, label=str(idx), color=cmap(i % 20))
        bottom += vals
    ax.set_ylabel(ylabel); ax.set_title(title, fontweight="bold")
    ax.set_xticks(np.arange(len(order))); ax.set_xticklabels(order, rotation=15, ha="right")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, frameon=False)
    fig.tight_layout()
    return fig


def means_display(means, valcols=("mean", "ci95", "count")):
    d = means.copy()
    ren = {"mean": "Mean", "ci95": "95% CI", "count": "n", "std": "SD", "se": "SE"}
    d = d.rename(columns=ren)
    for c in ["Mean", "95% CI", "SD", "SE"]:
        if c in d: d[c] = d[c].round(2)
    return d


# =================================================================== UI
st.title("BIO262 Port Macquarie, Data Analysis")
st.caption("Staff answer key. Runs every test the assessment requires on the compiled class data. "
           "Each group is a replicate plot (n = 4, or 3 where a value is missing).")

with st.sidebar:
    st.header("Data")
    up = st.file_uploader("Upload a workbook in the same format, or leave blank to use the bundled class data.",
                          type=["xlsx"])
    if up is not None:
        raw = up.read(); src = up.name
    else:
        raw = open(DATA_DEFAULT, "rb").read(); src = "bundled: PMQ_combined_data_2026.xlsx"
    st.success(f"Loaded {src}")
    st.markdown("**Communities**")
    for i, nm in A.SITES.items():
        st.markdown(f"{i}. {nm}")
    st.divider()
    st.caption("95% CIs use t x SE with t depending on n. Two-way models treat the second "
               "factor as crossed with site; each group is a replicate.")

R = load(raw)

tabs = st.tabs(["Overview", "Canopy height", "Tree density", "Basal area", "Canopy cover",
                "Shrub cover", "Ground cover", "Species richness", "Relative dominance"])

# ---- Overview
with tabs[0]:
    st.subheader("What is tested")
    st.markdown("""
| Metric | Test | Factors |
|---|---|---|
| Canopy height | One-way ANOVA + Tukey | Site |
| Tree density | One-way ANOVA per size class | Site (each class separately) |
| Basal area | Two-way ANOVA | Site x Method (Plot, Factor Gauge) |
| Canopy cover | Two-way ANOVA | Site x Method (Line, Densiometer) |
| Shrub cover | Two-way ANOVA | Site x Method (Line, Subplot) |
| Species richness | Two-way ANOVA | Site x Class (Trees, Shrubs) |
| Ground cover | Means and 95% CI, no test | Site x Method |
| Relative dominance | Stacked composition, no test | Site x Species |
""")
    st.info("Letters above bars are a compact letter display from Tukey HSD. Communities that "
            "share a letter are not significantly different at p = 0.05.")
    # quick export of all ANOVA tables
    buf = io.StringIO()
    def dump(name, aov):
        buf.write(f"# {name}\n"); buf.write(aov.to_csv()); buf.write("\n")
    dump("Canopy height (one-way)", R["canopy_height"]["anova"])
    for cls, r in R["tree_density"].items(): dump(f"Tree density {cls} (one-way)", r["anova"])
    for nm, lab in [("basal_area", "Basal area"), ("canopy_cover", "Canopy cover"),
                    ("shrub_cover", "Shrub cover"), ("species_richness", "Species richness")]:
        dump(f"{lab} (two-way)", R[nm]["anova"])
    st.download_button("Download all ANOVA tables (CSV)", buf.getvalue(),
                       file_name="PMQ_ANOVA_tables.csv", mime="text/csv")

# ---- Canopy height
with tabs[1]:
    r = R["canopy_height"]; aov = r["anova"]
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.pyplot(fig_oneway(r["means"], r["letters"], "Canopy height (m)", "Canopy height by community"))
    with c2:
        p = aov.loc["site", "PR(>F)"]
        st.markdown(f"**One-way ANOVA.** Sites show {sig_word(p)} difference in canopy height, "
                    f"{aov_line(aov, 'site')}.")
        st.markdown("**Tukey groups:** " + ", ".join(f"{s} ({r['letters'][s]})" for s in A.SITE_ORDER))
        st.dataframe(aov.round(4), width="stretch")
        st.dataframe(means_display(r["means"]), hide_index=True, width="stretch")
    with st.expander("Tukey HSD pairwise comparisons"):
        st.dataframe(r["tukey"], hide_index=True, width="stretch")
    assumption_block(r, is_two=False)

# ---- Tree density
with tabs[2]:
    st.markdown("Two size classes analysed separately, as the assessment requires.")
    for cls in ["< 10 cm DBH", ">= 10 cm DBH"]:
        r = R["tree_density"][cls]; aov = r["anova"]
        st.markdown(f"#### Trees {cls}")
        c1, c2 = st.columns([1.1, 1])
        with c1:
            st.pyplot(fig_oneway(r["means"], r["letters"], "Density (trees/ha)", f"Tree density, {cls}"))
        with c2:
            p = aov.loc["site", "PR(>F)"]
            st.markdown(f"Sites show {sig_word(p)} difference, {aov_line(aov, 'site')}.")
            st.markdown("**Tukey groups:** " + ", ".join(f"{s} ({r['letters'][s]})" for s in A.SITE_ORDER))
            st.dataframe(aov.round(4), width="stretch")
        with st.expander(f"Tukey HSD pairwise comparisons, {cls}"):
            st.dataframe(r["tukey"], hide_index=True, width="stretch")
        assumption_block(r, is_two=False)
        st.divider()


def twoway_tab(key, ylabel, factor, title, factor_word):
    r = R[key]; aov = r["anova"]
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.pyplot(fig_twoway(r["means"], factor, ylabel, title))
    with c2:
        eff = [i for i in aov.index if i != "Residual"]
        st.markdown("**Two-way ANOVA**")
        for e in eff:
            p = aov.loc[e, "PR(>F)"]
            st.markdown(f"- **{e}**: {sig_word(p)} effect, {aov_line(aov, e)}")
        st.markdown("**Tukey on site:** " + ", ".join(f"{s} ({r['letters_site'][s]})" for s in A.SITE_ORDER))
        st.dataframe(aov.round(4), width="stretch")

    # --- the two levels compared within each site (paired) ---
    se = r["simple"]; a, b = se.attrs.get("levels2", (factor_word, ""))
    st.markdown(f"#### The two {factor_word} within each site")
    st.caption(f"Each group measured both, so this compares {a} against {b} plot by plot at each "
               f"community (a paired t-test, with Wilcoxon signed-rank as the non-parametric "
               f"alternative). p (Holm) is adjusted for testing all four sites. With only 3 to 4 "
               f"pairs per site the power is low, and Wilcoxon cannot go below 0.125 with four pairs, "
               f"so read these alongside the figure.")
    disp = se.copy()
    for cnum in [c for c in disp.columns if disp[c].dtype != object and c != "n pairs"]:
        disp[cnum] = disp[cnum].round(3)
    st.dataframe(disp, hide_index=True, width="stretch")
    diff_sites = se.loc[se["sig"] == "yes", "site"].tolist()
    if diff_sites:
        st.markdown(f"**{a} and {b} differ significantly at:** " + ", ".join(diff_sites) +
                    " (Holm adjusted p < 0.05).")
    else:
        st.markdown(f"**No site shows a significant {a} vs {b} difference** after adjusting for the four tests.")

    with st.expander("Means and 95% CI"):
        st.dataframe(means_display(r["means"]), hide_index=True, width="stretch")
    with st.expander("Tukey HSD on site (pooled over " + factor_word + ")"):
        st.dataframe(r["tukey_site"], hide_index=True, width="stretch")
    assumption_block(r, is_two=True)


with tabs[3]:
    twoway_tab("basal_area", "Basal area (m2/ha)", "method", "Live tree basal area, plot vs factor gauge", "methods")
with tabs[4]:
    twoway_tab("canopy_cover", "Canopy cover (%)", "method", "Canopy cover, line vs densiometer", "methods")
with tabs[5]:
    twoway_tab("shrub_cover", "Shrub cover (%)", "method", "Shrub cover, line vs subplot", "methods")

# ---- Ground cover
with tabs[6]:
    st.markdown("Means and 95% confidence intervals per category. No statistical test, the CIs "
                "carry the comparison, as the assessment specifies.")
    gc = R["ground_cover"]
    meth = st.radio("Method", ["Point Intercept", "Visual Estimation"], horizontal=True)
    sub = gc[gc["method"] == meth]
    piv = sub.pivot_table(index="category", columns="site", values="mean").reindex(A.GC_CATS)[A.SITE_ORDER]
    pci = sub.pivot_table(index="category", columns="site", values="ci95").reindex(A.GC_CATS)[A.SITE_ORDER]
    disp = piv.round(1).astype(str) + " (±" + pci.round(1).astype(str) + ")"
    st.dataframe(disp, width="stretch")
    st.pyplot(fig_stacked(piv.fillna(0), "% cover", f"Ground cover composition, {meth}"))

# ---- Species richness
with tabs[7]:
    twoway_tab("species_richness", "Species richness (per 0.04 ha)", "class",
               "Species richness, trees vs shrubs", "classes")
    st.caption("Watch the interaction term: trees dominate richness in the forests while shrubs "
               "dominate in the heath, which is the crossover the two-way test picks up.")

# ---- Relative dominance
with tabs[8]:
    st.markdown("Relative dominance (Do_rel), each species share of plot basal area. "
                "Top eight species with the rest grouped as Other. No statistical test.")
    rd = R["relative_dominance"]
    st.pyplot(fig_stacked(rd, "% of basal area", "Relative tree dominance", percent=True))
    st.dataframe(rd.round(1), width="stretch")
