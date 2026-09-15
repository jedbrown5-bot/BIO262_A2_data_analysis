"""
Build a self-contained HTML report of every finding in the tool.
Figures are embedded as base64 PNGs and tables as HTML, so the file opens in any
browser and prints cleanly to PDF. Used by the app's download button, and can be
run on its own:  python report.py [workbook.xlsx] [out.html]
"""
import base64
import io
import datetime as _dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import analysis as A
from figs import fig_oneway, fig_twoway, fig_stacked

CSS = """
<style>
 body{font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;max-width:960px;margin:24px auto;padding:0 18px;line-height:1.45}
 h1{color:#1F4E3D;border-bottom:3px solid #1F4E3D;padding-bottom:6px}
 h2{color:#1F4E3D;margin-top:34px;border-bottom:1px solid #ccc;padding-bottom:3px}
 h3{color:#2f6b52;margin-top:20px}
 table{border-collapse:collapse;margin:8px 0 14px;font-size:13px}
 th,td{border:1px solid #ccc;padding:4px 8px;text-align:right;white-space:nowrap}
 th{background:#eef2f0;text-align:center}
 td:first-child,th:first-child{text-align:left}
 /* scientific table style: no vertical rules, horizontal only, caption above */
 table.sci{border-collapse:collapse}
 table.sci td,table.sci th{border:none;background:none;font-size:12px}
 table.sci{border-top:2px solid #333;border-bottom:2px solid #333}
 table.sci thead th{border-bottom:1px solid #333}
 .tcap{font-size:13px;margin:14px 0 2px}
 img{max-width:560px;display:block;margin:8px 0}
 .note{background:#f4f7f5;border-left:4px solid #2f6b52;padding:8px 12px;margin:10px 0;font-size:13px}
 .result{font-size:14px;margin:6px 0}
 .muted{color:#666;font-size:12px}
 @media print{h2{page-break-before:auto}h2,h3,img,table{page-break-inside:avoid}}
</style>
"""


def _b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _img(fig):
    return f'<img src="data:image/png;base64,{_b64(fig)}" />'


def _fmtp(p):
    try:
        return "&lt; 0.001" if p < 0.001 else f"{p:.3f}"
    except Exception:
        return "n/a"


def _aov_line(aov, factor, resid="Residual"):
    row = aov.loc[factor]; dfr = int(aov.loc[resid, "df"])
    return f"F({int(row['df'])}, {dfr}) = {row['F']:.2f}, p {_fmtp(row['PR(>F)'])}"


def _tbl(df, index=False):
    return df.round(3).to_html(index=index, border=0)


def _aov_tbl(aov):
    d = aov.rename(columns={"sum_sq": "Sum Sq", "PR(>F)": "p"}).copy()
    d.index.name = "Effect"
    for c in ["Sum Sq", "F"]:
        if c in d:
            d[c] = d[c].round(2)
    if "df" in d:
        d["df"] = d["df"].round(0).astype("Int64")
    if "p" in d:
        d["p"] = d["p"].map(lambda v: "" if pd.isna(v) else ("< 0.001" if v < 0.001 else f"{v:.4f}"))
    return d.to_html(index=True, border=0, na_rep="")


def _means_tbl(means):
    d = means.rename(columns={"mean": "Mean", "ci95": "95% CI", "count": "n",
                              "std": "SD", "se": "SE"})
    for c in ["Mean", "95% CI", "SD", "SE"]:
        if c in d:
            d[c] = d[c].round(2)
    return d.to_html(index=False, border=0)


def _assump_html(res, is_two):
    a = res.get("assump", {})
    sh = a.get("shapiro", {}); lv = a.get("levene", {})
    out = ["<h3>Assumptions and non-parametric alternative</h3>"]
    if "p" in sh:
        ok = sh["p"] >= 0.05
        out.append(f'<div class="result"><b>Normality of residuals (Shapiro-Wilk):</b> '
                   f'W = {sh["stat"]:.3f}, p = {_fmtp(sh["p"])}. '
                   + ("Consistent with normal." if ok else "Normality is doubtful.") + "</div>")
    if "p" in lv:
        ok = lv["p"] >= 0.05
        out.append(f'<div class="result"><b>Equal variance (Levene):</b> '
                   f'stat = {lv["stat"]:.3f}, p = {_fmtp(lv["p"])}. '
                   + ("Homogeneous." if ok else "Variances differ across groups.") + "</div>")
    if is_two:
        out.append("<b>Non-parametric alternative, Scheirer-Ray-Hare:</b>")
        out.append(_tbl(res["srh"]))
    else:
        kw = a.get("kruskal", {})
        if "p" in kw:
            out.append(f'<div class="result"><b>Kruskal-Wallis:</b> H = {kw["stat"]:.3f}, '
                       f'df = {kw["df"]}, p = {_fmtp(kw["p"])}.</div>')
        dn = a.get("dunn", {})
        if isinstance(dn, dict) and "letters" in dn:
            groups = ", ".join(f"{s} ({dn['letters'].get(s, '')})" for s in A.SITE_ORDER
                               if s in dn["letters"])
            out.append(f'<div class="result"><b>Dunn\'s test (Holm), non-parametric post-hoc:</b> '
                       f'{groups}</div>')
            out.append(_tbl(dn["table"]))
    bad = (sh.get("p", 1) < 0.05) or (lv.get("p", 1) < 0.05)
    alt = "Scheirer-Ray-Hare" if is_two else "Kruskal-Wallis with Dunn"
    if bad:
        out.append(f'<div class="note">An assumption is questionable here, so lean on the {alt} '
                   "result, or try a log or square root transformation. With only 3 to 4 replicates "
                   "these tests are low powered.</div>")
    return "\n".join(out)


def _oneway_section(title, res, ylabel, grey=False):
    aov = res["anova"]; p = aov.loc["site", "PR(>F)"]
    parts = [f"<h2>{title}</h2>", _img(fig_oneway(res["means"], res["letters"], ylabel, title, grey=grey))]
    parts.append(f'<div class="result">One-way ANOVA. Sites show '
                 f'{"a significant" if p < 0.05 else "no significant"} difference, {_aov_line(aov, "site")}.</div>')
    parts.append('<div class="result"><b>Tukey groups:</b> '
                 + ", ".join(f"{s} ({res['letters'][s]})" for s in A.SITE_ORDER) + "</div>")
    parts.append(_aov_tbl(aov))
    parts.append("<h3>Means and 95% CI</h3>" + _means_tbl(res["means"]))
    parts.append("<h3>Tukey HSD pairwise comparisons</h3>" + _tbl(res["tukey"]))
    parts.append(_assump_html(res, is_two=False))
    return "\n".join(parts)


def _twoway_section(title, res, ylabel, factor, factor_word, grey=False):
    aov = res["anova"]
    parts = [f"<h2>{title}</h2>", _img(fig_twoway(res["means"], factor, ylabel, title, grey=grey))]
    parts.append("<div class='result'><b>Two-way ANOVA</b></div>")
    for e in [i for i in aov.index if i != "Residual"]:
        p = aov.loc[e, "PR(>F)"]
        parts.append(f'<div class="result">{e}: '
                     f'{"significant" if p < 0.05 else "not significant"}, {_aov_line(aov, e)}</div>')
    parts.append(_aov_tbl(aov))
    parts.append("<h3>Means and 95% CI</h3>" + _means_tbl(res["means"]))
    parts.append(_assump_html(res, is_two=True))
    return "\n".join(parts)


def _method_section(title, res, ylabel, grey=False):
    """One-way ANOVA across sites (methods averaged) + paired t-test for the two methods."""
    c = res["combo"]; site = c["site"]; aov_s = site["anova"]; p = c["paired"]
    a, b = p["level_a"], p["level_b"]
    def pc(pv):
        return "p &lt; 0.001" if pv < 0.001 else f"p = {pv:.3f}"
    parts = [f"<h2>{title}</h2>", _img(fig_twoway(res["means"], "method", ylabel, title, grey=grey))]
    ps = aov_s.loc["site", "PR(>F)"]
    parts.append(f'<div class="result"><b>Sites, one-way ANOVA</b> (mean of the two methods per plot): '
                 f'communities show {"a significant" if ps < 0.05 else "no significant"} difference, '
                 f'{_aov_line(aov_s, "site")}.</div>')
    parts.append('<div class="result"><b>Tukey groups:</b> '
                 + ", ".join(f"{s} ({site['letters'][s]})" for s in A.SITE_ORDER) + "</div>")
    parts.append(_aov_tbl(aov_s))
    pv = p["p"]
    parts.append(f'<div class="result"><b>Methods, paired t-test</b> ({a} vs {b}, pooled across sites): '
                 f't({p["df"]}) = {p["t"]:.2f}, {pc(pv)}. '
                 + ("The two methods differ. " if pv < 0.05 else "No significant difference. ")
                 + f'{a} mean = {p["mean_a"]:.1f}, {b} mean = {p["mean_b"]:.1f} '
                   f'(difference {p["mean_diff"]:.1f}).</div>')
    parts.append(f'<div class="muted">Normality of the paired differences (Shapiro-Wilk) '
                 f'p = {p["shapiro_p"]:.3f}. Wilcoxon signed-rank p = {p["wilcoxon_p"]:.3f} is the '
                 f'non-parametric alternative. n = {p["n"]} paired plots.</div>')
    parts.append("<h3>Means and 95% CI</h3>" + _means_tbl(res["means"]))
    return "\n".join(parts)


def build_report_html(R, source="bundled data", grey=False):
    now = _dt.date.today().isoformat()
    html = ["<!doctype html><html><head><meta charset='utf-8'>",
            "<title>BIO262 Port Macquarie, Analysis Report</title>", CSS, "</head><body>"]
    html.append("<h1>BIO262 Port Macquarie, Data Analysis Report</h1>")
    style = "greyscale (report style)" if grey else "colour (on screen)"
    html.append(f'<div class="muted">Generated {now}. Source: {source}. Figures: {style}. '
                "Staff answer key. Each group is a replicate plot (n = 4, or 3 where a value is missing).</div>")
    html.append('<div class="note">Column figures show community means with 95% confidence interval '
                "error bars, capped at zero. Letters above bars are a Tukey compact letter display, "
                "communities sharing a letter are not significantly different at p = 0.05. Two-way "
                "models treat the second factor as crossed with site.</div>")

    html.append(_oneway_section("Canopy height", R["canopy_height"], "Canopy height (m)", grey))
    html.append("<h2>Tree density</h2>")
    for cls in ["< 10 cm DBH", ">= 10 cm DBH"]:
        html.append(_oneway_section(f"Tree density, {cls}", R["tree_density"][cls], "Density (trees/ha)", grey)
                    .replace("<h2>", "<h3>").replace("</h2>", "</h3>", 0))
    html.append(_method_section("Live tree basal area", R["basal_area"], "Basal area (m2/ha)", grey))
    html.append(_method_section("Canopy cover", R["canopy_cover"], "Canopy cover (%)", grey))
    html.append(_method_section("Shrub cover", R["shrub_cover"], "Shrub cover (%)", grey))

    # ground cover, scientific table style (no vertical rules, caption above)
    html.append("<h2>Ground cover</h2>")
    html.append('<div class="muted">Mean % cover with the 95% CI in brackets. No test, the CIs carry '
                "the comparison. Tables are in scientific style, caption above, no vertical rules.</div>")
    gc = R["ground_cover"]
    for ti, meth in enumerate(["Point Intercept", "Visual Estimation"], start=1):
        sub = gc[gc["method"] == meth]
        piv = sub.pivot_table(index="category", columns="site", values="mean").reindex(A.GC_CATS)[A.SITE_ORDER]
        pci = sub.pivot_table(index="category", columns="site", values="ci95").reindex(A.GC_CATS)[A.SITE_ORDER]
        disp = piv.round(1).astype(str) + " (&plusmn;" + pci.round(1).astype(str) + ")"
        disp.index.name = "Ground cover type"
        html.append(f'<div class="tcap"><b>Table {ti}.</b> Mean per cent ground cover (95% CI) by '
                    f"community, {meth} method.</div>")
        html.append(disp.to_html(border=0, escape=False, classes="sci"))
        html.append(_img(fig_stacked(piv.fillna(0), "% cover", f"Ground cover composition, {meth}", grey=grey)))

    html.append(_twoway_section("Species richness", R["species_richness"],
                                "Species richness (per 0.04 ha)", "class", "classes", grey))

    # relative dominance
    html.append("<h2>Relative tree dominance</h2>")
    rd = R["relative_dominance"]
    html.append(_img(fig_stacked(rd, "% of basal area", "Relative tree dominance", grey=grey)))
    html.append(rd.round(1).to_html(border=0))
    html.append('<div class="muted">Do_rel, each species share of plot basal area for trees >= 1.0 cm '
                "DBH, top eight species with the rest grouped as Other. No statistical test.</div>")

    html.append("</body></html>")
    return "\n".join(html)


if __name__ == "__main__":
    import sys, os
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "data", "PMQ_combined_data_2026.xlsx")
    out = sys.argv[2] if len(sys.argv) > 2 else "PMQ_analysis_report.html"
    wb = A.load_workbook_bytes(open(src, "rb").read())
    R = A.run_all(wb)
    open(out, "w").write(build_report_html(R, source=os.path.basename(src)))
    print("wrote", out)
