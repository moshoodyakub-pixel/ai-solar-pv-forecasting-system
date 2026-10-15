# Dataset provenance and schema

No measured dataset is included in GitHub. Keep unmodified originals in `data/raw/` locally (ignored by Git), and record source and licence in your research log.

| Field | Required | Unit | Source |
|---|---|---|---|
| timestamp | Yes | ISO date/time | Measured plant observation timestamp (specify source time zone) |
| power_kw | Yes | kW AC | Inverter/meter PV generation observed at each hourly timestamp |
| poa_fc | Optional | W/m² | **Archived target-hour irradiance prediction available 1h earlier** |
| temperature_fc | Optional | °C | **Archived target-hour ambient temperature prediction available 1h earlier** |
| capacity_kw | Metadata | kWp DC | Installed array rating, not module efficiency |
| ac_capacity_kw | Metadata | kW AC | Rated inverter output |

If the file has 15-minute intervals, aggregate deliberately and explain timestamp convention and power-versus-energy conversion. If it has only GHI/temperature with no measured AC kW, it cannot validate this project's PV power forecasting target.

Record: dataset title, source URL, access date, plant location (if licensed), permissions/licence, period, resolution, missing values, timestamp basis, measurement location (DC/AC), equipment capacity and all transformations.
