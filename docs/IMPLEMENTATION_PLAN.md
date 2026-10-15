# Project delivery plan for Miva IFT 497 / 498

| Phase | Technical deliverable | Research evidence |
|---|---|---|
| 1. Measured data intake | Timestamp validation, source metadata, PV kW quality checks | Dataset table; missing-value analysis |
| 2. Baseline experiment | One-hour persistence and day-history baselines | Benchmark tables and plots |
| 3. AI experiment | Random Forest, reproducible chronological partitions | MAE/RMSE/nRMSE/R²; selected model |
| 4. Comparative models | XGBoost and LSTM as justified by dataset size | Controlled experiment, runtime/accuracy tradeoff |
| 5. Forecast service | Saved versioned model with target-hour weather forecast integration | API and inference tests |
| 6. Interface | Location/site context, forecast tests, provenance and export | UI screenshots and usability demonstration |
| 7. Report/defence | Chapters 1–5 using verified research and real results | References, architecture, methods, tests, limitations |

## Project boundaries

The MVP is one-hour ahead. Do not describe any output as day-ahead without retraining and retesting to prevent leakage. Do not claim general accuracy for a coordinate-only site without measured local validation. The system is **forecast assistance** only, not automatic mini-grid dispatch or remote operation.
