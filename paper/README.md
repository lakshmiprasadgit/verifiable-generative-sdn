# Paper: Predictive Verification in a Shielded SDN Control Loop

IEEE conference format (`IEEEtran`). Upload this folder to Overleaf and compile
`main.tex` with pdfLaTeX (bibliography via BibTeX).

* `main.tex` - paper body; `results.tex` - Results and Performance Analysis (input by main.tex)
* `references.bib` - references (metadata verified 2026-11-09 against publisher records; DOIs included)
* `figures/dashboard_slot.png` - screenshot of the prototype dashboard (dashboard figure)

All other figures are drawn in TikZ/pgfplots from the numbers in the reports below,
so they compile without external images.

## Sources of every reported number

| Paper item | Repository source |
|---|---|
| simulation table, time-series and bar figures (seeds 1-5) | `experiments/reports/2026-11-09-sim-main/` |
| held-out seeds 6-10 | `experiments/reports/2026-11-09-sim-heldout/` |
| calibration ablation, k = 1.109 | `experiments/reports/2026-11-09-sim-heldout-k1.109/` |
| static-fallback ablation (bar figure) | `experiments/reports/2026-11-09-sim-static/` |
| simulator calibration (calibration table) | `experiments/reports/2026-11-09-sim-main/calibration.md` |
| emulated calibration (calibration table) | `experiments/reports/2026-10-26-mininet-s1-s3-5seeds/calibration.md` |
| meter test table | `experiments/reports/2026-10-26-meter-sweep/modify.md` |
| emulated-network s2 table | `experiments/reports/2026-10-26-mininet-s2-meter-fix/` |
| latency spikes, idle-path test | `experiments/reports/2026-10-26-mininet-s1-s3-5seeds/NOTE.md`, `.../meter-sweep/latency.md` |

The 2026-11-09 simulation reports were re-run at commit `296d117`, whose code is
identical to `c831a00` (the commit of the emulated s2 run), so all simulation
numbers describe the implementation the paper presents.
