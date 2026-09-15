"""Shared matplotlib figures for the app and the report export."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import analysis as A

SITE_COLORS = {"Swampy Paperbark": "#4E79A7", "Wet Sclerophyll": "#59A14F",
               "Littoral Rainforest": "#8CD17D", "Heathland": "#E15759"}
SERIES_COLORS = ["#4E79A7", "#E1812C"]
# greyscale (report style): single fill for one series, light/dark for two series
GREY_ONE = "#bdbdbd"
GREY_SERIES = ["#d9d9d9", "#7f7f7f"]
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})


def fig_oneway(means, letters, ylabel, title, grey=False):
    order = A.SITE_ORDER
    m = means.set_index("site").reindex(order)
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    x = np.arange(len(order))
    vals = m["mean"].values
    ci = m["ci95"].values
    lower = np.minimum(vals, ci)
    colors = [GREY_ONE] * len(order) if grey else [SITE_COLORS[s] for s in order]
    ax.bar(x, vals, color=colors, edgecolor="black" if grey else "none", linewidth=0.6, width=0.62,
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


def fig_twoway(means, factor, ylabel, title, grey=False):
    order = A.SITE_ORDER
    levels = list(dict.fromkeys(means[factor]))
    x = np.arange(len(order)); w = 0.38
    pal = GREY_SERIES if grey else SERIES_COLORS
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    for k, lv in enumerate(levels):
        sub = means[means[factor] == lv].set_index("site").reindex(order)
        vals = sub["mean"].values; ci = sub["ci95"].values
        lower = np.minimum(vals, ci)
        ax.bar(x + (k - 0.5) * w, vals, width=w, label=lv, color=pal[k % 2],
               edgecolor="black" if grey else "none", linewidth=0.6,
               yerr=[lower, ci], capsize=3, error_kw=dict(lw=0.9))
    ax.set_xticks(x); ax.set_xticklabels(order, rotation=15, ha="right")
    ax.set_ylabel(ylabel); ax.set_title(title, fontweight="bold")
    ax.set_ylim(bottom=0); ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def fig_stacked(wide, ylabel, title, percent=False, grey=False):
    order = [c for c in A.SITE_ORDER if c in wide.columns]
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    bottom = np.zeros(len(order))
    n = max(len(wide.index), 1)
    if grey:
        greys = [str(v) for v in np.linspace(0.85, 0.2, n)]  # light to dark
    cmap = plt.get_cmap("tab20")
    for i, idx in enumerate(wide.index):
        vals = wide.loc[idx, order].values.astype(float)
        col = greys[i] if grey else cmap(i % 20)
        ax.bar(order, vals, bottom=bottom, label=str(idx), color=col,
               edgecolor="black", linewidth=0.4)
        bottom += vals
    ax.set_ylabel(ylabel); ax.set_title(title, fontweight="bold")
    ax.set_xticks(np.arange(len(order))); ax.set_xticklabels(order, rotation=15, ha="right")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, frameon=False)
    fig.tight_layout()
    return fig
