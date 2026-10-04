# HR-Power analysis implementation plan

**Goal:** Implement the approved pre-window choice, explicit P1D/short-transient choice, complete diagnostics and run-local PDF/tabular exports.

**Architecture:** Keep the model registry and existing run lifecycle. Share fitting diagnostics between the two explicitly selected structures. Store context separately from objective samples; generate reports from persisted results.

**Spec:** User requests and approval of 2026-09-27; scientific conventions will live in the app README and versioned model metadata.

**Constraints:** No automatic structure selection or rho thresholds. No physiological interpretation. Preserve historical run reading and original CSV blobs. Delay domain is [0,T] for objective samples only. Pre-window is [-10,0), opt-in; absent/invalid windows are recorded. When explicitly requested but unusable, fail that segment instead of silently changing initialization. Gamma default bounds are [1e-6/1800,5/0.01].

## Tasks

- [x] Numerical pipeline: tests for pre-window on/off/absent, fractional delay short-transient recovery, fixed delay, rho/correlation and metrics. Update p1d.py and add shared context handling; extend registry metadata without breaking old configs.
- [x] Persistence: test manifest pre-window inventory, replay compatibility and failures. Update datasets.py/runs.py and API. Historical replay retains the historical initialization protocol, explicitly versioned.
- [x] Analysis/export: test complete tables and PDF endpoint for valid, failed, historical runs. Add reporting.py and CSV ZIP/PDF exports in runs/<id>/exports; use ReportLab and matplotlib. Add PDF dependency pins.
- [x] UI: explicit structure and pre-window controls; four diagnostic sections, ACF/context plots, aggregate views and export buttons. Tests and type/build checks.
- [x] Verification: whole app Python/Vitest suites, production build, PDF rendering inspection, fresh code review, README conventions.

## Review focus

Missing pre-window never silently changes an explicitly requested method. Negative samples never enter objective, duration or metrics. Short-transient outputs never imply separate K/tau. Legacy records with missing diagnostics display unavailable. All-failed runs still export; nonfinite statistics serialize as null.

## Verification record

36 backend tests and 8 frontend tests pass; Vue type check and production build pass. PDF pages rendered and visually inspected for synthetic and real-archive sample reports, both structures. Read-only independent review found legacy protocol exposure and historical positive L lower-bound replay; both fixed with regression tests. Historical plotting avoids duplicating context already in the objective. Gamma multistart absolute tolerance is 1e-6 bpm/(W s), recorded per parameter; full P1D tolerances are unchanged. No commits or existing user run modifications. Nonblocking warnings: Starlette TestClient deprecation and Vite chunk size.
