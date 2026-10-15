# PV_Data.xlsx — Dataset Audit and Preliminary Validation

**Project:** Design of an AI-Driven Solar PV Forecasting System  
**Dataset:** [Photovoltaic (PV) Generation Dataset with Orientation Diversity](https://doi.org/10.5281/zenodo.19245713), Çunkaş, Arslan & Cevik (2026), CC BY 4.0.  
**Reviewed:** 15 October 2026  
**Status:** Preliminary, retrospective research benchmark — not final thesis findings or live forecasts.

## Input data audit

- Original workbook contains 7,080 hourly observation rows in sheet **DATA**, with **no column-header row**. The **DATA DESCRIPTION** sheet's second row lists the 21 column labels.
- Days 1 through 295, Hours 1 through 24; **0** missing/duplicate Day–Hour pairs.
- Five individual PV outputs sum exactly to **Total PV Power** across all rows.
- **Total PV Power**: min 0, max 1,398, mean approximately 295.53 **original source units**, with 3,811 zero-power observations (53.8%).
- The source describes PV power in **W or Wh** without resolving which unit is correct. Neither the calendar year, timezone nor installed DC/AC capacity is documented. These must not be invented or silently converted.
- Field **Dewpoint** has values 7–94, inconsistent with the stated dewpoint °C semantics at observed air temperatures. Do not use this field until source metadata is clarified.
- One possible inconsistency: Day 159 Hour 19 has reported Solar Radiation = 0, but Total PV Power = 84.

## Methodology

- Target: Total PV Power, in source units.
- Horizon: **one recorded hour ahead** using only known historical PV power and deterministic time features.
- Predictors: target-time cyclical day/hour, historical power lags 1/2/24/48h and previous 24h rolling power average.
- Strict **70% train (4,922 rows), 15% validation (1,055), 15% unseen test (1,055)** after 48h lag warm-up, chronologically split.
- Fixed Random Forest (120 trees, minimum leaf size 3, seed 42) compared against one-hour and previous-day persistence. Select by lowest validation MAE; test metrics must not be used to tune or select.
- Test period is relative **Day 252 Hour 2** to **Day 295 Hour 24**; no real-world calendar dates can be inferred.

## Reproduced benchmark (original dataset units, NOT kW)

| Method | Validation MAE | Test MAE | Test RMSE | Test R² | Generating-hour Test MAE |
|---|---:|---:|---:|---:|---:|
| Persistence 1h | 99.627 | 97.564 | 174.182 | 0.8391 | 208.835 |
| Persistence 24h | 42.510 | 75.470 | 190.918 | 0.8067 | 171.848 |
| **Random Forest** | **30.820** | **38.977** | **88.689** | **0.9583** | **86.602** |

Generating hours use 455 test observations where the actual contemporaneous solar-radiation measurement was positive. This condition is **only an ex-post evaluation filter**, never an inference feature. Random Forest generating-hour RMSE is 133.544 and R² is 0.8830.

Random Forest achieves **48.4% lower test MAE** than the 24h persistence comparator. Many observations are nighttime zeros: all-hours performance alone is insufficient to demonstrate useful forecasting skill.

## Caveats and next work

- No absolute kW accuracy metric or capacity-normalized RMSE can be supported without output-unit and rated-capacity clarification.
- No physical-model benchmark is included: this would require genuine rated capacity, geometry, and meteorological forecasts known at issue time. **Target-hour observed irradiance must not be used as a forecast input.**
- Validate observation units, timing convention, weather variable semantics, equipment details, and original paper before thesis use.
- The source is a single experimental rooftop plant. This does not prove accuracy for Nigerian mini-grids or arbitrary coordinates.
- Next study: more baselines, daylight performance, blocked/rolling temporal validation, weather forecasts, second independent measured-AC-kW dataset, XGBoost and LSTM as justified.

Raw source workbook, model artifacts and secrets are excluded from GitHub. Clone this repo and upload PV_Data.xlsx locally in the dashboard to reproduce.
