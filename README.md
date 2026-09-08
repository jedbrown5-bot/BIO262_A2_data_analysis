# BIO262 Port Macquarie, Data Analysis Tool

A small Streamlit app that runs every statistical test the assessment requires on the compiled Intensive School dataset, and shows the ANOVA tables, post-hoc groupings, means and 95% confidence intervals, and the figures. It is built as a staff answer key, so you can see the intended results and check student work. It also accepts an uploaded workbook in the same format.

## What it runs

| Metric | Test | Factors |
|---|---|---|
| Canopy height | One-way ANOVA, Tukey post-hoc with letters | Site |
| Tree density | One-way ANOVA per size class | Site, each size class separately |
| Basal area | Two-way ANOVA | Site by Method (Plot, Factor Gauge) |
| Canopy cover | Two-way ANOVA | Site by Method (Line, Densiometer) |
| Shrub cover | Two-way ANOVA | Site by Method (Line, Subplot) |
| Species richness | Two-way ANOVA | Site by Class (Trees, Shrubs) |
| Ground cover | Means and 95% CI table, no test | Site by Method |
| Relative dominance | Stacked composition, no test | Site by Species |

Each of the four groups at a site is treated as a replicate plot, so n = 4, or 3 where a value is missing (canopy height at Littoral Rainforest group 2, shrub cover line intercept at Wet Sclerophyll group 2). The two-way models treat the second factor as crossed with site and include the interaction. Letters above bars are a compact letter display from Tukey HSD, communities that share a letter are not significantly different at p = 0.05.

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

## Notes on the statistics

The confidence intervals are t times the standard error, with t depending on n. The two-way ANOVA uses Type II sums of squares, which handles the two missing values without trouble. Because the same group is measured by both methods, the method comparison is really a paired design, so the two-way ANOVA is a slight simplification, but it is the analysis the assessment asks for at this level. The Tukey follow-up on site is provided for the two-way tests as a guide to which communities differ.
