# Power response implementation plan

**Goal:** implement the approved decomposition with default least squares (Huber optional), validation order selection, AR(2) refit, evaluation, standalone HTML and an evidence-based report.

**Spec:** [power_response_decomposition_proposal.md](power_response_decomposition_proposal.md). User authorization: 2026-10-15; execute directly in the current workspace. Preserve unrelated existing deletions and all previous artifacts.

**Architecture:** new independent `src/power_hr_eda/power_response/` package, reusing existing AR data boundaries and AR fit. SciPy optimization/filtering, NumPy, pandas; standalone HTML canvas with embedded data, no external service.

## Frozen scientific choices

- Reuse existing 36/12/12 workout split; training-only coefficients for validation. Test already seen, descriptive only. No automatic train+validation refit in validation evaluation.
- Symmetric orders 2, 3, 4 first; asymmetry remains a subsequent optional experiment.
- Stable real polynomial via bounded reflection coefficients (permits real and complex poles), numerator degree n including direct term, global mean, zero initial state, input difference starts at zero in each real segment.
- Equal total LS weight per workout. Huber optional with training-derived common scale; never used in this initial run.
- Select smallest converged order within one paired standard error of best validation mean workout RMSE. Bootstrap paired workout RMSE differences (seed 42) for descriptive uncertainty, not an independent test after selection.
- Transition diagnostic: first 30 seconds after latest nonzero input, separately up/down; plateau otherwise, initial 30 seconds reported separately. No exclusion from overall fit/metrics.
- Parameter diagnostics: convergence/multistart costs, poles, rank/condition, workout-cluster sandwich local uncertainty with t intervals; explicit rank/near-boundary limitations. Do not treat iid OLS intervals as robust.
- Fit residual AR(2) with existing sample-weighted OLS; report weighting difference and AR stability. Deterministic validation and full AR mean are separate metrics; no observed-history feedback. Existing AR iid intervals clearly labeled.
- Record source hashes, settings, split and runtime versions. New output directories refuse overwrite.

## Tasks and verification

1. [x] `model.py`: input construction, stable fit, simulation and parameter diagnostics. Tests: independent synthetic response recovery with colored noise, direct term and no fake initial jump, repeated transitions without reset, output independence from observed residual, stable poles.
2. [x] `evaluation.py` and `pipeline.py`: training fit, validation order selection, AR refit, frozen evaluation command, trace and metric exports. Tests: gap handling, paired selection, split overlap refusal, no test signal read in fit, data hash checks, model serialization and end-to-end synthetic run.
3. [x] `viewer.py`, `scripts/power_response.py`: standalone interactive HTML (workout/order selectors, zoom, prescribed/real/predicted power, y/r/e, input), CLI. Test payload contains all full-resolution valid samples and segment boundaries; browser check selectors and charts.
4. [x] Execute on real training/validation, inspect convergence and diagnostics, run appropriate regression tests, write reproducible report with limitations and viewing advice. Final whole-change review before completion.

## Review focus

- No lags/input differences or drawn lines across real gaps.
- No validation observations in deterministic state or fitted coefficients.
- Selection is based only on validation, with equal workout weights.
- AR mean is not double counted; AR fit uses y-r, not centered residuals.
- Weak identifiability and failed optimizations remain visible; no hidden correction after examining test.

## Completion evidence

- Final run: `reports/power_response_ls_v1/`, 36 training / 12 validation workouts, n=4 selected. Descriptive frozen test evaluation: `reports/power_response_ls_test/`.
- 126 tests passed, 1 skipped: `.venv/Scripts/python -B -m pytest tests --ignore=tests/_generated -q -p no:cacheprovider`.
- Browser QA passed 36 workout/order combinations, four canvases, parameter table, zoom/reset and stochastic toggle. Screenshot: `reports/power_response_ls_v1/browser_qa.png`.
- Frozen validation reload: all 91,597 predictions identical, maximum difference 0 W.
- Independent read-only review: fixed overlapping initialization-window diagnostics and source provenance; added pole-zero diagnostics. Follow-up found no remaining important issues.
- `scripts/report_power_response.py` regenerates viewer and numerical observations without fitting. HTML/report rendering provenance is persisted separately from the frozen fitting manifest.
- Repeatability across workout subsets and asymmetric dynamics remain explicitly deferred; local cluster intervals and multistart checks do not establish test-retest repeatability.
