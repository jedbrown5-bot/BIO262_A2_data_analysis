# BIO262 Port Macquarie, Data Analysis Tool

A small Streamlit app that runs every statistical test the assessment requires on the compiled Intensive School dataset, and shows the ANOVA tables, post-hoc groupings, means and 95% confidence intervals, and the figures. It is built as a staff answer key, so you can see the intended results and check student work. It also accepts an uploaded workbook in the same format.

## What it runs

| Metric | Test | Factors |
|---|---|---|
| Canopy height | One-way ANOVA, Tukey post-hoc with letters | Site |
| Tree density | One-way ANOVA per size class | Site, each size class separately |
| Basal area | One-way ANOVA (sites) + paired t-test (methods) | Site, then Plot vs Factor Gauge |
| Canopy cover | One-way ANOVA (sites) + paired t-test (methods) | Site, then Line vs Densiometer |
| Shrub cover | One-way ANOVA (sites) + paired t-test (methods) | Site, then Line vs Subplot |
| Species richness | Two-way ANOVA | Site by Class (Trees, Shrubs) |
| Ground cover | Means and 95% CI table, no test | Site by Method |
| Relative dominance | Stacked composition, no test | Site by Species, trees >= 1.0 cm DBH |

Each of the four groups at a site is treated as a replicate plot, so n = 4, or 3 where a value is missing (canopy height at Littoral Rainforest group 2, shrub cover line intercept at Wet Sclerophyll group 2). The two-way models treat the second factor as crossed with site and include the interaction. Letters above bars are a compact letter display from Tukey HSD, communities that share a letter are not significantly different at p = 0.05.

Basal area, canopy cover and shrub cover are analysed as a one-way ANOVA comparing the sites (on the mean of the two methods per plot) plus a paired t-test comparing the two methods pooled across sites, since the two methods are measured on the same plot. The two-way ANOVA is kept in a reference panel on each of those tabs. Species richness stays a two-way ANOVA because trees versus shrubs is not a method comparison and the interaction is the point.

Each two-way tab also has a "two methods within each site" panel. Because the same group measured both methods, this compares them plot by plot at each community with a paired t-test, and adjusts across the four sites with Holm. This is the analysis to use when you want to know where the two methods actually disagree, which the overall two-way ANOVA does not tell you directly. The method main effect in the ANOVA has only two levels, so it needs no Tukey, the F test is already the comparison. Tukey is shown only for site, which has four levels.

## How to run

You need Python 3.9 or later.

1. Open a terminal in this folder.
2. Install the packages, once:

   pip install -r requirements.txt

3. Start the app:

   streamlit run app.py

It opens in your browser. The bundled class dataset loads by default. To analyse a different file, use the uploader in the sidebar, it must have the same sheet and column layout as the compiled workbook.

## Files

- app.py, the Streamlit interface.
- analysis.py, the data loading and all the statistics. You can import this on its own if you want the numbers without the app.
- data/PMQ_combined_data_2026.xlsx, the compiled class data used by default.
- requirements.txt, the packages needed.

## Exporting the results

There is a "Greyscale figures (report style)" checkbox in the sidebar. Tick it for greyscale, colourblind-safe figures that follow the scientific formatting rules for a written report, on screen and in the downloaded report. Leave it unticked for colour on screen. The ground cover table in the report is always in scientific style, caption above and no vertical rules.

The Overview tab has two download buttons. "Download all ANOVA tables (CSV)" gives you just the ANOVA tables. "Download full report (HTML)" gives you a complete report, every figure, ANOVA table, post-hoc, per-site method comparison, assumption check, ground cover table and relative dominance, in one self-contained file. Open it in a browser and use Print, then Save as PDF, for a clean PDF. You can also generate it from the command line without the app:

    python report.py data/PMQ_combined_data_2026.xlsx report.html

## Assumptions and alternatives

Every ANOVA tab has an "Assumptions and non-parametric alternative" panel:

- **Normality of residuals**, Shapiro-Wilk on the model residuals.
- **Equal variance**, Levene's test across the groups or cells.
- **A non-parametric alternative** you can fall back on if an assumption fails: Kruskal-Wallis for the one-way tests, and the Scheirer-Ray-Hare test (a rank-based two-way test) for the two-way tests.
- The paired per-site method comparison also reports a Wilcoxon signed-rank p as its non-parametric alternative.

If an assumption looks shaky, the panel says so and points you to the alternative test or a transformation (log or square root). Keep in mind that with only three or four replicates per group both the assumption tests and the non-parametric tests are low powered. In particular a Wilcoxon signed-rank test on four pairs cannot return a p below 0.125, so it will never reach significance at 0.05 here. Read the tests alongside the figures rather than on their own.

## Notes on the statistics

The confidence intervals are t times the standard error, with t depending on n. The two-way ANOVA uses Type II sums of squares, which handles the two missing values without trouble. Because the same group is measured by both methods, the method comparison is really a paired design, so the two-way ANOVA is a slight simplification, but it is the analysis the assessment asks for at this level. The Tukey follow-up on site is provided for the two-way tests as a guide to which communities differ.
