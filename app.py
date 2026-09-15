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
import streamlit as st

import analysis as A
from figs import fig_oneway, fig_twoway, fig_stacked
from report import build_report_html

st.set_page_config(page_title="BIO262 PMQ Analysis", layout="wide", page_icon="🌿")

DATA_DEFAULT = os.path.join(os.path.dirname(__file__), "data", "PMQ_combined_data_2026.xlsx")


@st.cache_data(show_spinner=False)
def load(_bytes):
    wb = A.load_workbook_bytes(_bytes)
    return A.run_all(wb)


GREY = False  # set by the sidebar toggle below

@st.cache_data(show_spinner="Building report...")
def get_report_html(raw, src, grey):
    wb = A.load_workbook_bytes(raw)
    return build_report_html(A.run_all(wb), source=src, grey=grey)


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
    GREY = st.checkbox("Greyscale figures (report style)", value=False,
                       help="Greyscale, colourblind-safe figures for a written report. "
                            "Applies on screen and to the downloaded report.")
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
| Basal area | One-way ANOVA (sites) + paired t-test (methods) | Site, then Plot vs Factor Gauge |
| Canopy cover | One-way ANOVA (sites) + paired t-test (methods) | Site, then Line vs Densiometer |
| Shrub cover | One-way ANOVA (sites) + paired t-test (methods) | Site, then Line vs Subplot |
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
    c_csv, c_rep = st.columns(2)
    with c_csv:
        st.download_button("Download all ANOVA tables (CSV)", buf.getvalue(),
                           file_name="PMQ_ANOVA_tables.csv", mime="text/csv")
    with c_rep:
        st.download_button("Download full report (HTML)", get_report_html(raw, src, GREY),
                           file_name="PMQ_analysis_report.html", mime="text/html",
                           help="A complete report with every figure, ANOVA table, post-hoc, "
                                "assumption check and alternative. Opens in a browser, print to PDF.")

# ---- Canopy height
with tabs[1]:
    r = R["canopy_height"]; aov = r["anova"]
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.pyplot(fig_oneway(r["means"], r["letters"], "Canopy height (m)", "Canopy height by community", grey=GREY))
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
            st.pyplot(fig_oneway(r["means"], r["letters"], "Density (trees/ha)", f"Tree density, {cls}", grey=GREY))
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
        st.pyplot(fig_twoway(r["means"], factor, ylabel, title, grey=GREY))
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


def method_tab(key, ylabel, title):
    """One-way ANOVA across sites (methods averaged) + paired t-test for the two methods."""
    r = R[key]; c = r["combo"]; site = c["site"]; aov_s = site["anova"]; p = c["paired"]
    a, b = p["level_a"], p["level_b"]
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.pyplot(fig_twoway(r["means"], "method", ylabel, title, grey=GREY))
    with c2:
        ps = aov_s.loc["site", "PR(>F)"]
        st.markdown("**Sites, one-way ANOVA** (mean of the two methods per plot)")
        st.markdown(f"- Communities show {sig_word(ps)} difference, {aov_line(aov_s, 'site')}.")
        st.markdown("- Tukey groups: " + ", ".join(f"{s} ({site['letters'][s]})" for s in A.SITE_ORDER))
        st.markdown(f"**Methods, paired t-test** ({a} vs {b}, pooled across sites)")
        pv = p["p"]
        st.markdown(f"- t({p['df']}) = {p['t']:.2f}, p {p_fmt(pv)}. " +
                    (f"The two methods differ. " if pv < 0.05 else "No significant difference. ") +
                    f"{a} mean = {p['mean_a']:.1f}, {b} mean = {p['mean_b']:.1f} "
                    f"(difference {p['mean_diff']:.1f}).")
        st.caption(f"Normality of the paired differences (Shapiro-Wilk) p = {p['shapiro_p']:.3f}. "
                   f"Wilcoxon signed-rank p = {p['wilcoxon_p']:.3f} is the non-parametric alternative. "
                   f"n = {p['n']} paired plots.")
    with st.expander("Sites one-way ANOVA table and Tukey"):
        st.dataframe(aov_s.round(4), width="stretch")
        st.dataframe(site["tukey"], hide_index=True, width="stretch")
    with st.expander("Means and 95% CI (per site and method)"):
        st.dataframe(means_display(r["means"]), hide_index=True, width="stretch")
    with st.expander("Reference: two-way ANOVA (site x method) and per-site comparison"):
        st.dataframe(r["anova"].round(4), width="stretch")
        st.caption("The two-way model treats the paired measurements as independent, which is why the "
                   "paired t-test above is preferred for the method comparison. Per-site breakdown:")
        st.dataframe(r["simple"].round(3), hide_index=True, width="stretch")


with tabs[3]:
    method_tab("basal_area", "Basal area (m2/ha)", "Live tree basal area, plot vs factor gauge")
with tabs[4]:
    method_tab("canopy_cover", "Canopy cover (%)", "Canopy cover, line vs densiometer")
with tabs[5]:
    method_tab("shrub_cover", "Shrub cover (%)", "Shrub cover, line vs subplot")

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
    st.pyplot(fig_stacked(piv.fillna(0), "% cover", f"Ground cover composition, {meth}", grey=GREY))

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
    st.pyplot(fig_stacked(rd, "% of basal area", "Relative tree dominance", percent=True, grey=GREY))
    st.dataframe(rd.round(1), width="stretch")
