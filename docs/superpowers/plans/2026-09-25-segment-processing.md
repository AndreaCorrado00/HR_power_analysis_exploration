# Segment processing implementation plan

Approved in conversation: implement the complete pipeline in one intervention.
Execute inline using executing-plans and test-driven-development.

Goal: import exported segment ZIPs, select all/subset, smooth, normalize and export.
Architecture: isolated processing service/router plus dedicated Vue page; reuse
normalization formulas. Existing FIT extraction and local modifications preserved.

Scientific contract: centered arithmetic mean on original samples in
[t-W/2, t+W/2), W globally 3 (default), 5 or 10 seconds. The half-open
interval ensures exactly W samples for interior 1 Hz samples, including even W.
No resampling/interpolation. Split blocks at dt > 1.5 * median positive dt.
Truncate windows at block boundaries; record counts and incomplete windows.
Missing values propagate per signal. Preserve raw values and all source columns.
Global positive finite normalization references, applied to raw and smoothed data.
Reprocessing starts from raw columns and removes previous derived columns.
Centered smoothing is offline and must not cross future train/test boundaries.

Files: backend/processing_service.py, backend/processing_api.py, backend/app.py;
src/components/ProcessingPage.vue, src/components/ProcessingChart.vue,
src/processingApi.ts, src/App.vue; backend/frontend tests; app README.

Execution checklist:
- [x] Write failing API tests for import, fixed windows, gaps, normalization,
  invalid archives/parameters, selection and roundtrip.
- [x] Implement ZIP validation, immutable source session, processing and export.
- [x] Write failing UI test for select-all and stale preview invalidation.
- [x] Implement dedicated page, global controls and comparison plots.
- [x] Run backend/frontend suites, production build, real 221-segment roundtrip.
- [x] Review changes and persist scientific/usage documentation.

Review focus: malformed manifests/CSV; duplicate selection; stale async responses;
even-window endpoint convention; reimport retaining raw values and provenance.
No commits of existing user changes; deliver working-tree implementation.

Verification 2026-09-25: 71 Python tests passed, 1 existing skip (suite includes
repository tests and webapp tests); 15 frontend tests passed; vue-tsc and Vite
production build passed. Existing Starlette/httpx deprecation and Vite >500 kB
bundle warnings remain. Tests requiring private temporary directories and
Node/esbuild subprocesses needed execution outside the Windows sandbox.

Real input: 221 segments, 34,135 samples, 7 gaps. For all 3/5/10 s windows,
export/reimport preserved original series and reproduced every processed frame.
Normalization test references 60 kg/200 bpm/180 bpm are synthetic test values,
not athlete defaults. HTTP smoke test also imported, previewed and exported all
221 segments from the running application. Browser visual QA unavailable:
the connected computer-use provider reported no browser.

Independent code review identified the empty inactive numeric field issue;
a failing regression reproduced it and conversion of empty references to null
fixed it. No other actionable findings. Scientific contract and usage persisted
in webapp/dataset_exploration/README.md. Existing local changes retained.
