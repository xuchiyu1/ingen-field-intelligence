# SEALED: planted patterns (do not open before Week 3)

| ID | Pattern | How it is planted |
|---|---|---|
| P1 | Navigation hotspot | Aido Rover reports at Site_C, North zone: S1 (Navigation & Localisation) weight ×3 |
| P2 | Cold-weather battery | Aido Rover reports with temperature below 0 °C: H1 (Battery & Power) weight ×2 |
| P3 | Rising motor current before sensor faults | H3 (Sensors) reports: hour-before motor current ×1.2–1.3 and positive trend (+0.8 to +1.8 A/h) |
| P4 | Fari response-delay complaints | Fari U2 reports: delay theme 20% before 2026-04-01, 60% after; response latency 4–9 s vs 0.8–2 s |

`answer_key.csv` holds the generator's category, secondary category, severity, root-cause flag and planted-pattern ID for every report.
