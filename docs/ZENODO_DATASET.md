# Zenodo orientation-diverse PV dataset: source-specific protocol

Source: Çunkaş, Arslan & Cevik (2026), [Zenodo record 19245713](https://doi.org/10.5281/zenodo.19245713) (CC BY 4.0).

The original workbook contains two sheets:
- **DATA**: 7,080 rows of hourly observations, no header row.
- **DATA DESCRIPTION**: the actual 21 variable names are in its second row (Excel row 2).

The first sheet's header row must **not** be interpreted as the first measurement. The importer detects this two-sheet layout and automatically assigns the correct names.

## Research integrity constraints

- Only \`Day\` (1–295) and \`Hour\` (1–24) are provided; no complete calendar timestamp, year or source time zone. The experiment uses a **relative hourly sequence**, not fabricated calendar dates.
- PV output units are labelled **W or Wh** in source metadata; without clarification do **not** convert to kW, kWh or report an absolute capacity-based nRMSE. Output errors use original reported values and are described as *source units*.
- \`Dewpoint\` contains 7–94 in this file, inconsistent with documented dewpoint °C at typical temperatures. Exclude this from model inputs pending source clarification.
- The total PV output equals the sum of PV-1 ... PV-5 on every source row, so only the total (or a separately selected single panel) is forecast; do not feed the contemporaneous panel outputs into its prediction.
- The included experiment uses past measured power at t−1, t−2, t−24, t−48, trailing mean and known target-hour cyclic features. It does not use actual target-hour irradiance or temperature, which would be data leakage for a one-hour-ahead forecast.
- Nighttime hours have many zero readings; report all-hours and **generating-hours** evaluation. Generating-hours subset is defined by observed target-hour radiation for retrospective reporting **only**.
- Physical-model baseline and source-specific coordinate validation are NOT claimed without trustworthy PV capacity, geometry and weather forecasts known at prediction time.

Run: open the main dashboard, upload the **original** \`PV_Data.xlsx\`, inspect the file and run evaluation. Do not upload original data into this GitHub repository; it is excluded from version control.
