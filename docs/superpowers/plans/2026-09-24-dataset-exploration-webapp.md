# Dataset Exploration Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Vue SPA that inventories FIT datasets, visualizes power and heart-rate series, extracts individual or contiguous lap blocks, applies explicit optional normalizations, and exports reproducible time series as ZIP archives.

**Architecture:** A FastAPI backend owns filesystem access, FIT parsing, lap classification, normalization, segmentation, and ZIP creation. A Vue 3/Vite SPA consumes typed JSON endpoints and uses Apache ECharts for overview and detailed zoomable charts. FastAPI serves the compiled SPA and API from one dynamically selected localhost port.

**Tech Stack:** Python 3.14, FastAPI, Uvicorn, existing `fitdecode`/pandas code, pytest, Vue 3, TypeScript, Vite, Vitest, Vue Test Utils, Apache ECharts, vue-echarts.

**Spec:** `docs/superpowers/specs/2026-09-24-dataset-exploration-webapp-design.md`

## Global Constraints

- Keep all application code under `webapp/dataset_exploration/`; modify root files only when the plan explicitly names them.
- Never modify FIT source files or replace measured power and heart-rate values.
- Use FIT `lap.start_time` and `lap.timestamp` as the only initial segmentation source.
- Put activities without usable lap boundaries in the visible section labelled `Esclusi dall'estrazione` and include an explicit reason.
- Permit merging only a gap-free sequence of lap indices from one activity.
- Use `power_w_kg = power_w / weight_kg`, `hr_pct_max = 100 * heart_rate_bpm / hr_max_bpm`, and `hr_pct_threshold = 100 * heart_rate_bpm / hr_threshold_bpm`.
- Require every active normalization denominator to be numeric, finite, and greater than zero.
- Export time-series CSV files plus a manifest in a ZIP; never export original FIT files.
- Bind the local server to `127.0.0.1`, select a free port, and document the final `IP:porta` in the web app README.
- Do not add authentication, a database, remote publishing, automatic non-lap segmentation, search, or unrelated controls.

## Review Focus

- A symlinked dataset whose target is readable must load exactly like a real directory; a broken link must return a specific path error without crashing the service. Covered in Task 2.
- Adjacent laps sharing a boundary timestamp must not duplicate the boundary record in a merged extraction. Covered in Task 3.
- NaN, infinity, zero, negative, empty, and non-numeric normalization parameters must not produce derived columns. Covered in Task 4.
- A dataset containing one corrupt FIT and valid FIT files must inventory the valid activities and report the corrupt file independently. Covered in Task 2.
- Export destination failure must leave source data untouched and return a downloadable ZIP response rather than silently losing the archive. Covered in Tasks 5 and 6.

---

### Task 1: Scaffold the Python and Vue application with reproducible dependency boundaries

**Files:**
- Create: `webapp/dataset_exploration/backend/__init__.py`
- Create: `webapp/dataset_exploration/backend/domain.py`
- Create: `webapp/dataset_exploration/requirements.txt`
- Create: `webapp/dataset_exploration/package.json`
- Create: `webapp/dataset_exploration/tsconfig.json`
- Create: `webapp/dataset_exploration/vite.config.ts`
- Create: `webapp/dataset_exploration/index.html`
- Create: `webapp/dataset_exploration/src/main.ts`
- Create: `webapp/dataset_exploration/src/App.vue`
- Create: `webapp/dataset_exploration/src/styles.css`
- Create: `webapp/dataset_exploration/tests/backend/test_domain.py`
- Create: `webapp/dataset_exploration/src/App.test.ts`

**Interfaces:**
- Consumes: repository Python environment and the approved design specification.
- Produces: `ActivitySummary`, `LapBoundary`, `NormalizationParameters`, and `SegmentSelection` dataclasses; runnable `npm test` and `npm run build` commands.

- [ ] **Step 1: Write the failing Python domain test**

```python
from datetime import datetime, timezone

from backend.domain import ActivitySummary, LapBoundary


def test_activity_summary_marks_missing_laps_as_excluded() -> None:
    activity = ActivitySummary(
        activity_id="ride.fit",
        source_path="ride.fit",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        duration_seconds=3600.0,
        record_count=3601,
        has_power=True,
        has_heart_rate=True,
        laps=(),
        parse_error=None,
    )
    assert activity.extractable is False
    assert activity.exclusion_reason == "Nessun lap FIT utilizzabile"


def test_activity_summary_with_a_valid_lap_is_extractable() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    activity = ActivitySummary(
        activity_id="ride.fit",
        source_path="ride.fit",
        start_time=start,
        end_time=start,
        duration_seconds=0.0,
        record_count=1,
        has_power=True,
        has_heart_rate=True,
        laps=(LapBoundary(index=1, start_time=start, end_time=start),),
        parse_error=None,
    )
    assert activity.extractable is True
    assert activity.exclusion_reason is None
```

- [ ] **Step 2: Run the Python test and verify the expected failure**

Run: `.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_domain.py -v`

Expected: FAIL because `backend.domain` and its dataclasses do not exist.

- [ ] **Step 3: Create the minimal typed domain model**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LapBoundary:
    index: int
    start_time: datetime
    end_time: datetime


@dataclass(frozen=True)
class ActivitySummary:
    activity_id: str
    source_path: str
    start_time: datetime | None
    end_time: datetime | None
    duration_seconds: float
    record_count: int
    has_power: bool
    has_heart_rate: bool
    laps: tuple[LapBoundary, ...]
    parse_error: str | None

    @property
    def extractable(self) -> bool:
        return bool(self.laps) and self.parse_error is None

    @property
    def exclusion_reason(self) -> str | None:
        if self.parse_error:
            return f"FIT non leggibile: {self.parse_error}"
        if not self.laps:
            return "Nessun lap FIT utilizzabile"
        return None


@dataclass(frozen=True)
class NormalizationParameters:
    weight_kg: float | None = None
    hr_max_bpm: float | None = None
    hr_threshold_bpm: float | None = None


@dataclass(frozen=True)
class SegmentSelection:
    activity_id: str
    first_lap: int
    last_lap: int
```

Create a Vue/Vite package with scripts `dev`, `build`, and `test`; configure Vitest with `jsdom`. Declare only `vue`, `vite`, `typescript`, `vitest`, `@vitejs/plugin-vue`, `@vue/test-utils`, `jsdom`, `echarts`, and `vue-echarts`. Declare only `fastapi`, `uvicorn`, and test-only `httpx` in the web app Python requirements because pandas and fitdecode remain supplied by the repository environment.

- [ ] **Step 4: Install the declared dependencies and preserve lockfiles**

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r webapp/dataset_exploration/requirements.txt
Set-Location webapp/dataset_exploration
npm install
```

Expected: both commands exit 0 and npm creates `package-lock.json`. Do not install globally or add packages not named above.

- [ ] **Step 5: Write and run the initial Vue smoke test**

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import App from './App.vue'

describe('App', () => {
  it('shows the dataset path control', () => {
    const wrapper = mount(App)
    expect(wrapper.get('label[for="dataset-path"]').text()).toBe('Percorso dataset')
  })
})
```

Run: `npm test -- --run` from `webapp/dataset_exploration`.

Expected before `App.vue` implementation: FAIL because the labelled control is absent. Add only the labelled dataset-path input and rerun until PASS.

- [ ] **Step 6: Verify both scaffold test suites and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_domain.py -v
Set-Location webapp/dataset_exploration
npm test -- --run
```

Expected: both suites PASS.

Commit:

```powershell
git add webapp/dataset_exploration
git commit -m "feat: scaffold dataset exploration app"
```

### Task 2: Inventory real and symlinked FIT datasets and classify extraction eligibility

**Files:**
- Create: `webapp/dataset_exploration/backend/dataset_service.py`
- Create: `webapp/dataset_exploration/tests/backend/test_dataset_service.py`
- Modify: `webapp/dataset_exploration/backend/domain.py`

**Interfaces:**
- Consumes: `power_hr_eda.fit_reader.read_fit_activity(path: Path) -> FitActivity` and Task 1 domain types.
- Produces: `resolve_dataset(path_text: str) -> Path`, `discover_fit_files(dataset_path: Path) -> tuple[Path, ...]`, `summarize_activity(path: Path, root: Path) -> ActivitySummary`, and `inventory_dataset(path_text: str) -> DatasetInventory`.

- [ ] **Step 1: Write failing tests for a real directory, directory symlink, broken symlink, corrupt FIT isolation, and unusable lap boundaries**

```python
from pathlib import Path

import pytest

from backend.dataset_service import DatasetPathError, inventory_dataset


def test_real_and_symbolic_directories_discover_the_same_fit_files(tmp_path: Path, monkeypatch) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "ride.fit").write_bytes(b"fit")
    link = tmp_path / "linked"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this host")
    monkeypatch.setattr("backend.dataset_service.summarize_activity", fake_summary)
    assert [a.activity_id for a in inventory_dataset(str(real)).activities] == ["ride.fit"]
    assert [a.activity_id for a in inventory_dataset(str(link)).activities] == ["ride.fit"]


def test_broken_symbolic_directory_has_a_specific_path_error(tmp_path: Path) -> None:
    link = tmp_path / "broken"
    try:
        link.symlink_to(tmp_path / "missing", target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this host")
    with pytest.raises(DatasetPathError, match="non esiste"):
        inventory_dataset(str(link))


def test_corrupt_fit_does_not_hide_valid_activity(tmp_path: Path, monkeypatch) -> None:
    # fake_summary returns one ActivitySummary with parse_error for bad.fit and
    # one valid summary for good.fit.
    result = inventory_dataset(str(tmp_path))
    assert [a.activity_id for a in result.activities] == ["bad.fit", "good.fit"]
    assert result.activities[0].exclusion_reason.startswith("FIT non leggibile")


def test_lap_without_start_or_end_is_excluded(tmp_path: Path, monkeypatch) -> None:
    result = inventory_dataset(str(tmp_path))
    assert result.activities[0].extractable is False
    assert result.activities[0].exclusion_reason == "Nessun lap FIT utilizzabile"
```

Define `fake_summary` in the test file as a small real helper returning Task 1 dataclasses; do not mock filesystem resolution.

- [ ] **Step 2: Run the tests and verify they fail for missing inventory behavior**

Run: `.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_dataset_service.py -v`

Expected: FAIL because `dataset_service` does not exist.

- [ ] **Step 3: Implement minimal discovery and summary behavior**

Implement:

```python
class DatasetPathError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetInventory:
    dataset_path: str
    activities: tuple[ActivitySummary, ...]


def resolve_dataset(path_text: str) -> Path:
    candidate = Path(path_text).expanduser()
    if not candidate.exists():
        raise DatasetPathError("Il percorso del dataset non esiste")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_dir():
        raise DatasetPathError("Il percorso del dataset non è una directory")
    return resolved


def discover_fit_files(dataset_path: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for path in dataset_path.rglob("*.fit") if path.is_file()))
```

In `summarize_activity`, preserve parse errors, derive duration from valid record timestamps, accept only lap messages having both `start_time` and `timestamp` with end not earlier than start, and set `activity_id` to the source-relative POSIX path. Extend `DatasetInventory` with serialization helpers only when Task 6 needs them.

- [ ] **Step 4: Run the focused tests and the repository FIT reader tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_dataset_service.py tests/test_fit_reader.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the inventory slice**

```powershell
git add webapp/dataset_exploration/backend webapp/dataset_exploration/tests/backend/test_dataset_service.py
git commit -m "feat: inventory FIT datasets and classify laps"
```

### Task 3: Produce chart series and extract single or contiguous lap blocks

**Files:**
- Create: `webapp/dataset_exploration/backend/segment_service.py`
- Create: `webapp/dataset_exploration/tests/backend/test_segment_service.py`

**Interfaces:**
- Consumes: `FitActivity.records`, `ActivitySummary.laps`, and `SegmentSelection`.
- Produces: `activity_series(records: pd.DataFrame) -> pd.DataFrame`, `validate_selection(summary: ActivitySummary, selection: SegmentSelection) -> tuple[LapBoundary, ...]`, and `extract_segment(records: pd.DataFrame, laps: tuple[LapBoundary, ...]) -> pd.DataFrame`.

- [ ] **Step 1: Write failing tests for zero-based activity time, contiguous selection, rejected gaps, and boundary deduplication**

```python
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from backend.domain import SegmentSelection
from backend.segment_service import SelectionError, activity_series, extract_segment, validate_selection


def test_activity_series_starts_at_zero() -> None:
    start = pd.Timestamp("2026-01-01T10:00:00Z")
    records = pd.DataFrame({"timestamp": [start, start + pd.Timedelta(seconds=2)], "power": [100, 120], "heart_rate": [130, 132]})
    assert activity_series(records)["elapsed_seconds"].tolist() == [0.0, 2.0]


def test_selection_requires_a_gap_free_lap_range(summary_with_three_laps) -> None:
    selected = validate_selection(summary_with_three_laps, SegmentSelection("ride.fit", 1, 2))
    assert [lap.index for lap in selected] == [1, 2]
    with pytest.raises(SelectionError):
        validate_selection(summary_with_three_laps, SegmentSelection("ride.fit", 1, 4))


def test_merged_laps_do_not_duplicate_shared_boundary(summary_with_three_laps, records_on_boundaries) -> None:
    laps = validate_selection(summary_with_three_laps, SegmentSelection("ride.fit", 1, 2))
    segment = extract_segment(records_on_boundaries, laps)
    assert segment["timestamp"].is_unique
    assert segment["elapsed_seconds"].iloc[0] == 0.0
    assert segment["timestamp"].iloc[-1] == pd.Timestamp(laps[-1].end_time)
```

Create real fixtures with lap 1 `[t0, t10)` and lap 2 `[t10, t20]`; the merged output must contain the `t10` record once.

- [ ] **Step 2: Run the tests and verify the missing-service failure**

Run: `.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_segment_service.py -v`

Expected: FAIL because `segment_service` does not exist.

- [ ] **Step 3: Implement the half-open boundary convention and selection validation**

```python
def extract_segment(records: pd.DataFrame, laps: tuple[LapBoundary, ...]) -> pd.DataFrame:
    start = pd.Timestamp(laps[0].start_time)
    end = pd.Timestamp(laps[-1].end_time)
    timestamps = pd.to_datetime(records["timestamp"], utc=True, errors="coerce")
    selected = records.loc[timestamps.between(start, end, inclusive="both")].copy()
    selected["timestamp"] = timestamps.loc[selected.index]
    selected = selected.drop_duplicates(subset=["timestamp"], keep="first").sort_values("timestamp")
    selected["elapsed_seconds"] = (selected["timestamp"] - selected["timestamp"].iloc[0]).dt.total_seconds()
    return selected.reset_index(drop=True)
```

Validate that `first_lap <= last_lap`, every requested integer index exists, the activity IDs match, and the resulting indices equal `range(first_lap, last_lap + 1)`. Use the same elapsed-time derivation in `activity_series` without interpolation or resampling.

- [ ] **Step 4: Run focused and repository tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_segment_service.py tests/test_fit_reader.py tests/test_quality.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the segment slice**

```powershell
git add webapp/dataset_exploration/backend/segment_service.py webapp/dataset_exploration/tests/backend/test_segment_service.py
git commit -m "feat: extract contiguous FIT lap segments"
```

### Task 4: Apply explicit optional normalizations without changing measured columns

**Files:**
- Create: `webapp/dataset_exploration/backend/normalization.py`
- Create: `webapp/dataset_exploration/tests/backend/test_normalization.py`

**Interfaces:**
- Consumes: `NormalizationParameters` and a segment DataFrame containing `power` and/or `heart_rate`.
- Produces: `NormalizationRequest`, `NormalizationError`, `validate_parameters(request) -> None`, and `apply_normalizations(frame, request) -> pd.DataFrame`.

- [ ] **Step 1: Write failing tests for formulas, source preservation, and every invalid denominator class**

```python
import math

import pandas as pd
import pytest

from backend.normalization import NormalizationError, NormalizationRequest, apply_normalizations


def test_normalizations_add_derived_columns_and_preserve_sources() -> None:
    source = pd.DataFrame({"power": [200.0], "heart_rate": [150.0]})
    result = apply_normalizations(source, NormalizationRequest(70.0, 190.0, 170.0, True, True, True))
    assert source.columns.tolist() == ["power", "heart_rate"]
    assert result.loc[0, "power_w_kg"] == pytest.approx(200 / 70)
    assert result.loc[0, "hr_pct_max"] == pytest.approx(100 * 150 / 190)
    assert result.loc[0, "hr_pct_threshold"] == pytest.approx(100 * 150 / 170)


@pytest.mark.parametrize("bad", [None, "", "abc", 0, -1, math.nan, math.inf, -math.inf])
def test_active_normalization_rejects_invalid_denominator(bad) -> None:
    request = NormalizationRequest(bad, 190.0, 170.0, True, False, False)
    with pytest.raises(NormalizationError):
        apply_normalizations(pd.DataFrame({"power": [200.0]}), request)
```

Add equivalent parametrized assertions for active FCmax and FC-threshold normalization. Confirm invalid inactive parameters are ignored and do not create derived columns.

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run: `.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_normalization.py -v`

Expected: FAIL because `normalization` does not exist.

- [ ] **Step 3: Implement strict parameter validation and copy-on-transform**

```python
@dataclass(frozen=True)
class NormalizationRequest:
    weight_kg: object = None
    hr_max_bpm: object = None
    hr_threshold_bpm: object = None
    normalize_power: bool = False
    normalize_hr_max: bool = False
    normalize_hr_threshold: bool = False


def _positive_finite(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise NormalizationError(f"{label} deve essere numerico") from exc
    if not math.isfinite(number) or number <= 0:
        raise NormalizationError(f"{label} deve essere finito e maggiore di zero")
    return number
```

Copy the input DataFrame, add only requested derived columns, and never rename or overwrite `power` or `heart_rate`.

- [ ] **Step 4: Run the focused tests**

Run: `.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_normalization.py -v`

Expected: PASS for every valid and invalid case.

- [ ] **Step 5: Commit the normalization slice**

```powershell
git add webapp/dataset_exploration/backend/normalization.py webapp/dataset_exploration/tests/backend/test_normalization.py
git commit -m "feat: normalize exported cycling series"
```

### Task 5: Build reproducible ZIP exports with CSV series and manifest metadata

**Files:**
- Create: `webapp/dataset_exploration/backend/export_service.py`
- Create: `webapp/dataset_exploration/tests/backend/test_export_service.py`

**Interfaces:**
- Consumes: extracted DataFrames, `SegmentSelection`, activity source metadata, and `NormalizationRequest`.
- Produces: `ExportSegment`, `build_export_zip(dataset_path: str, segments: tuple[ExportSegment, ...]) -> bytes`, and `write_or_return_export(zip_bytes: bytes, destination: str | None) -> ExportResult`.

- [ ] **Step 1: Write failing tests for ZIP contents, reconstruction metadata, explicit parameters, and destination fallback**

```python
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from backend.export_service import ExportSegment, build_export_zip, write_or_return_export


def test_zip_contains_reconstructible_csv_and_explicit_normalization_manifest() -> None:
    frame = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-01-01T10:00:00Z")],
        "elapsed_seconds": [0.0],
        "power": [210.0],
        "heart_rate": [150.0],
        "power_w_kg": [3.0],
    })
    archive = build_export_zip("dataset/cleaned", (example_export_segment(frame),))
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        csv_text = zf.read(manifest["segments"][0]["csv_file"]).decode("utf-8")
    assert "timestamp,elapsed_seconds,power_w,heart_rate_bpm,power_w_kg" in csv_text
    assert manifest["normalization"]["weight_kg"] == 70.0
    assert manifest["normalization"]["formulas"]["power_w_kg"] == "power_w / weight_kg"
    assert manifest["segments"][0]["first_lap"] == 1
    assert manifest["segments"][0]["last_lap"] == 2


def test_unwritable_destination_returns_download_bytes(tmp_path: Path) -> None:
    result = write_or_return_export(b"zip", str(tmp_path / "missing" / "export.zip"))
    assert result.written_path is None
    assert result.download_bytes == b"zip"
```

Add a round-trip assertion that parsing the CSV restores original timestamps and elapsed seconds exactly. Assert that no `.fit` entry exists in the archive.

- [ ] **Step 2: Run the tests and verify the missing-service failure**

Run: `.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_export_service.py -v`

Expected: FAIL because `export_service` does not exist.

- [ ] **Step 3: Implement deterministic CSV names and manifest schema**

Use `csv`/pandas, `json`, `io.BytesIO`, and `zipfile.ZipFile`. Rename exported measured columns to `power_w` and `heart_rate_bpm`; include only activated derived columns. Store ISO-8601 timestamps, seconds as numeric values, units per column, formulas, declared parameters, segment source, lap range, temporal bounds, and boundary convention in `manifest.json`. Use format version `1` and stable names such as `ride__laps_001-002.csv`.

`write_or_return_export` may write only the named ZIP file, must create no implicit parent directories, and must return download bytes after `OSError`. It must never touch the source dataset.

- [ ] **Step 4: Run export and all backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend -v
```

Expected: PASS.

- [ ] **Step 5: Commit the export slice**

```powershell
git add webapp/dataset_exploration/backend/export_service.py webapp/dataset_exploration/tests/backend/test_export_service.py
git commit -m "feat: export lap time series archives"
```

### Task 6: Expose the backend API and single-port local server

**Files:**
- Create: `webapp/dataset_exploration/backend/schemas.py`
- Create: `webapp/dataset_exploration/backend/app.py`
- Create: `webapp/dataset_exploration/backend/run.py`
- Create: `webapp/dataset_exploration/tests/backend/test_api.py`
- Modify: `webapp/dataset_exploration/requirements.txt`

**Interfaces:**
- Consumes: services from Tasks 2–5.
- Produces: `GET /api/health`, `POST /api/datasets/load`, `GET /api/activities/{activity_id}/series`, `POST /api/segments/preview`, `POST /api/exports`, SPA fallback, `find_free_port(host: str) -> int`, and `main() -> None`.

- [ ] **Step 1: Write failing API tests for inventory, duration filtering, excluded activities, series, segment preview, export fallback, and health**

```python
from fastapi.testclient import TestClient

from backend.app import create_app


def test_inventory_separates_extractable_and_excluded_activities(fake_services) -> None:
    client = TestClient(create_app(fake_services))
    response = client.post("/api/datasets/load", json={"path": "dataset/cleaned", "max_duration_seconds": 7200})
    assert response.status_code == 200
    body = response.json()
    assert [a["activity_id"] for a in body["extractable"]] == ["with-laps.fit"]
    assert body["excluded"][0]["exclusion_reason"] == "Nessun lap FIT utilizzabile"
    assert all(a["duration_seconds"] <= 7200 for a in body["extractable"] + body["excluded"])


def test_export_destination_failure_returns_zip_download(fake_services) -> None:
    client = TestClient(create_app(fake_services))
    response = client.post("/api/exports", json=valid_export_request(destination="Z:/missing/export.zip"))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content.startswith(b"PK")


def test_health_reports_bound_service() -> None:
    response = TestClient(create_app()).get("/api/health")
    assert response.json() == {"status": "ok"}
```

Use a small `ServiceContainer` with real callable interfaces, not global monkeypatches, so route behavior remains testable. Add tests for invalid paths (400), invalid normalization (422), non-contiguous lap selection (422), activity not found (404), and corrupt FIT coexistence (200 with excluded entry).

- [ ] **Step 2: Run the API tests and verify the missing-app failure**

Run: `.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_api.py -v`

Expected: FAIL because `backend.app` does not exist.

- [ ] **Step 3: Implement schemas, dependency container, routes, and safe SPA serving**

Use Pydantic request/response models with the exact field names consumed by the frontend types in Task 7. Cache only the currently loaded dataset inventory and parsed activities in process memory; this is not durable persistence. Convert domain exceptions to explicit 400/404/422 responses. Serve `dist/index.html` and hashed assets only when the frontend has been built; API routes must never fall through to the SPA.

Implement free-port selection by binding a temporary socket to `(host, 0)`, reading its assigned port, closing it, and immediately starting Uvicorn on that port. Print exactly one startup line of the form `Dataset Exploration: http://127.0.0.1:<port>`.

- [ ] **Step 4: Run API and backend suites**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend -v
```

Expected: PASS.

- [ ] **Step 5: Commit the API slice**

```powershell
git add webapp/dataset_exploration/backend webapp/dataset_exploration/tests/backend/test_api.py webapp/dataset_exploration/requirements.txt
git commit -m "feat: expose local dataset exploration API"
```

### Task 7: Build the Vue activity grid, exclusions section, detail zoom, lap merging, normalization controls, and export flow

**Files:**
- Create: `webapp/dataset_exploration/src/api.ts`
- Create: `webapp/dataset_exploration/src/types.ts`
- Create: `webapp/dataset_exploration/src/components/DatasetControls.vue`
- Create: `webapp/dataset_exploration/src/components/ActivityCard.vue`
- Create: `webapp/dataset_exploration/src/components/ActivityGrid.vue`
- Create: `webapp/dataset_exploration/src/components/ActivityDetail.vue`
- Create: `webapp/dataset_exploration/src/components/NormalizationControls.vue`
- Create: `webapp/dataset_exploration/src/components/ExportPanel.vue`
- Create: `webapp/dataset_exploration/src/components/ActivityGrid.test.ts`
- Create: `webapp/dataset_exploration/src/components/ActivityDetail.test.ts`
- Create: `webapp/dataset_exploration/src/components/NormalizationControls.test.ts`
- Create: `webapp/dataset_exploration/src/components/ExportPanel.test.ts`
- Modify: `webapp/dataset_exploration/src/App.vue`
- Modify: `webapp/dataset_exploration/src/styles.css`

**Interfaces:**
- Consumes: Task 6 JSON contracts and ZIP response.
- Produces: the complete requested SPA and typed functions `loadDataset`, `getActivitySeries`, `previewSegment`, and `exportSegments`.

- [ ] **Step 1: Define shared TypeScript contracts matching Task 6 schemas**

```ts
export interface LapBoundary {
  index: number
  startElapsedSeconds: number
  endElapsedSeconds: number
  durationSeconds: number
}

export interface ActivitySummary {
  activityId: string
  sourcePath: string
  durationSeconds: number
  recordCount: number
  hasPower: boolean
  hasHeartRate: boolean
  laps: LapBoundary[]
  extractable: boolean
  exclusionReason: string | null
}

export interface DatasetInventory {
  datasetPath: string
  extractable: ActivitySummary[]
  excluded: ActivitySummary[]
}
```

Add `SeriesPoint`, `NormalizationRequest`, `SegmentRequest`, and `ExportRequest` with names identical to the API schema aliases.

- [ ] **Step 2: Write failing component tests for the two sections and duration text**

```ts
it('groups activities without laps under Esclusi dall\'estrazione', () => {
  const wrapper = mount(ActivityGrid, { props: { inventory } })
  expect(wrapper.get('[data-section="extractable"]').text()).toContain('with-laps.fit')
  expect(wrapper.get('[data-section="excluded"]').text()).toContain("Esclusi dall'estrazione")
  expect(wrapper.get('[data-section="excluded"]').text()).toContain('Nessun lap FIT utilizzabile')
})

it('formats activity duration as h:mm:ss', () => {
  const wrapper = mount(ActivityCard, { props: { activity: activityWithDuration(3661) } })
  expect(wrapper.text()).toContain('1:01:01')
})
```

Run: `npm test -- --run src/components/ActivityGrid.test.ts`.

Expected: FAIL because the grid and cards do not exist.

- [ ] **Step 3: Implement dataset controls, grid, cards, and compact ECharts series**

The first viewport must show the dataset path, load action, maximum-duration control, and activity sections. Configure every compact chart with an x-axis `[0, durationSeconds]`, elapsed `h:mm:ss` labels, a blue power series and red HR series. Clicking a card opens detail in the same SPA rather than adding an unrelated route.

Run: `npm test -- --run src/components/ActivityGrid.test.ts`.

Expected: PASS.

- [ ] **Step 4: Write failing detail tests for zoom and contiguous lap selection**

```ts
it('configures an inside and slider dataZoom for the detail chart', () => {
  const wrapper = mount(ActivityDetail, { props: { activity, series } })
  const option = wrapper.getComponent({ name: 'VChart' }).props('option')
  expect(option.dataZoom.map((item: { type: string }) => item.type)).toEqual(['inside', 'slider'])
})

it('allows one lap or a contiguous range and emits its inclusive bounds', async () => {
  const wrapper = mount(ActivityDetail, { props: { activity: activityWithThreeLaps, series } })
  await wrapper.get('[data-lap="1"]').trigger('click')
  await wrapper.get('[data-lap="2"]').trigger('click')
  expect(wrapper.emitted('selection')?.at(-1)).toEqual([{ firstLap: 1, lastLap: 2 }])
})
```

Run: `npm test -- --run src/components/ActivityDetail.test.ts`.

Expected: FAIL because the detail chart and selection behavior are absent.

- [ ] **Step 5: Implement detail chart, lap overlays, zoom, and contiguous merge behavior**

Use ECharts `markArea` or equivalent overlays for lap bounds and `dataZoom` with `inside` plus `slider`. Clicking an unselected lap starts a selection; shift-clicking or selecting the adjacent lap extends the block. Reject a non-adjacent extension in UI and leave the current valid selection unchanged. Show the preview returned by `/api/segments/preview` with elapsed time reset to zero.

Run: `npm test -- --run src/components/ActivityDetail.test.ts`.

Expected: PASS.

- [ ] **Step 6: Write failing normalization and export interaction tests**

```ts
it('requires a positive finite weight only when W/kg is enabled', async () => {
  const wrapper = mount(NormalizationControls)
  await wrapper.get('[name="normalizePower"]').setValue(true)
  await wrapper.get('[name="weightKg"]').setValue('0')
  expect(wrapper.text()).toContain('Il peso deve essere maggiore di zero')
  expect(wrapper.emitted('valid')).toEqual(undefined)
})

it('downloads the ZIP when the backend returns an archive fallback', async () => {
  const wrapper = mount(ExportPanel, { props: { selection, normalization } })
  await wrapper.get('button[type="submit"]').trigger('click')
  expect(api.exportSegments).toHaveBeenCalledWith(expect.objectContaining({ segments: [selection] }))
  expect(downloadZip).toHaveBeenCalledWith(expect.any(Blob), expect.stringEndingWith('.zip'))
})
```

Run: `npm test -- --run src/components/NormalizationControls.test.ts src/components/ExportPanel.test.ts`.

Expected: FAIL because these components do not exist.

- [ ] **Step 7: Implement normalization controls and export flow**

Provide exactly three parameter inputs and three activation controls. Validate only active transformations, show units in labels, and submit declared parameters plus formulas through the API contract. The export panel accepts a local ZIP destination and handles either JSON success with `writtenPath` or an `application/zip` response by downloading the blob.

Run: `npm test -- --run`.

Expected: all frontend tests PASS.

- [ ] **Step 8: Complete responsive styling and build the SPA**

Use a dense technical working surface with readable 16 px body text, compact activity cards, clear blue/red signal identity, a responsive grid, keyboard-focus styles, and no decorative imagery. Keep the primary controls and first useful results in the first viewport. Ensure the exclusion label is text, not color alone.

Run: `npm run build`.

Expected: Vite exits 0 and creates `webapp/dataset_exploration/dist/index.html` plus hashed assets.

- [ ] **Step 9: Commit the complete SPA**

```powershell
git add webapp/dataset_exploration/src webapp/dataset_exploration/index.html webapp/dataset_exploration/package.json webapp/dataset_exploration/package-lock.json webapp/dataset_exploration/tsconfig.json webapp/dataset_exploration/vite.config.ts
git commit -m "feat: add Vue FIT exploration workspace"
```

### Task 8: Verify the integrated app on `dataset/cleaned`, document startup and the actual address

**Files:**
- Create: `webapp/dataset_exploration/README.md`
- Create: `webapp/dataset_exploration/start.ps1`
- Create: `webapp/dataset_exploration/tests/backend/test_real_dataset_contract.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: complete backend, built SPA, and repository dataset.
- Produces: one-command local startup, real-dataset contract evidence, and documentation containing the observed `127.0.0.1:<port>` address.

- [ ] **Step 1: Write a failing real-dataset contract test**

```python
from pathlib import Path

import pytest

from backend.dataset_service import inventory_dataset


@pytest.mark.skipif(not Path("dataset/cleaned").exists(), reason="Repository cleaned dataset unavailable")
def test_cleaned_dataset_contains_both_extractable_and_excluded_activities() -> None:
    inventory = inventory_dataset("dataset/cleaned")
    extractable = [item for item in inventory.activities if item.extractable]
    excluded = [item for item in inventory.activities if not item.extractable]
    assert extractable
    assert excluded
    assert all(item.exclusion_reason for item in excluded)
```

Run: `.\.venv\Scripts\python.exe -m pytest webapp/dataset_exploration/tests/backend/test_real_dataset_contract.py -v`.

Expected before integration fixes: FAIL if real paths, symbolic FIT files, or classification differ from the service contract. Correct the service rather than weakening the assertions.

- [ ] **Step 2: Add one-command startup and focused ignore rules**

`start.ps1` must build the SPA only when `dist/index.html` is absent, then run `.\.venv\Scripts\python.exe -m backend.run` with `PYTHONPATH` including repository `src` and the web app directory. Add only `webapp/dataset_exploration/node_modules/` and generated `webapp/dataset_exploration/dist/` to `.gitignore`; preserve all pre-existing user changes in `.gitignore`.

- [ ] **Step 3: Run full automated verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
Set-Location webapp/dataset_exploration
npm test -- --run
npm run build
```

Expected: all repository and web app tests PASS; Vite build exits 0.

- [ ] **Step 4: Start the server and capture the actual free port**

Run `webapp/dataset_exploration/start.ps1` in a retained process. Read the emitted line `Dataset Exploration: http://127.0.0.1:<port>`. Make a non-browser request to `http://127.0.0.1:<port>/api/health` and require HTTP 200 with `{"status":"ok"}`. Make a second request to `/` and require HTTP 200.

- [ ] **Step 5: Verify a real inventory and export through HTTP**

POST `dataset/cleaned` to `/api/datasets/load`; require at least one item in both `extractable` and `excluded`, and require every excluded item to have `exclusionReason`. Request one known lap preview, verify the first elapsed value is zero, then request a ZIP export and inspect that it contains one CSV plus `manifest.json`, no FIT files, and explicit normalization parameters.

- [ ] **Step 6: Write the README with the observed address**

Document:

- purpose and exact supported scope;
- prerequisites and install commands;
- `start.ps1` usage;
- dataset path and symlink behavior;
- duration filter, activity detail, zoom, lap selection, contiguous merge, normalization, and export behavior;
- CSV and manifest contents;
- the exact observed `IP:porta` under a heading `Indirizzo verificato`, for example `127.0.0.1:53741` using the actual value from Step 4;
- that a later launch may choose a different free port and prints its current value.

- [ ] **Step 7: Run final verification and inspect the scoped diff**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
Set-Location webapp/dataset_exploration
npm test -- --run
npm run build
Set-Location ../..
git diff --check
git status --short
```

Expected: tests and build PASS, `git diff --check` prints nothing, and status shows only intended web app/documentation changes plus any clearly identified pre-existing user changes.

- [ ] **Step 8: Commit documentation and integration evidence**

```powershell
git add webapp/dataset_exploration/README.md webapp/dataset_exploration/start.ps1 webapp/dataset_exploration/tests/backend/test_real_dataset_contract.py .gitignore
git commit -m "docs: add verified dataset explorer startup"
```

Keep the verified local server running for the user and report the same `http://127.0.0.1:<port>` address recorded in the README.

### Approved amendment: editable lap partitions and export review

- Resolve symbolic FIT targets before decoding while retaining the logical
  dataset-relative activity identifier.
- Place normalization parameters and activation controls in the dataset-load
  surface and apply them globally.
- Represent each activity initially as one segment per lap; merge only adjacent
  segments and allow a merged segment to be restored to its original laps.
- Add any subset of the resulting segments to a deduplicated export collection.
- Provide a pre-export view with segment metadata, charts, individual removal,
  and one ZIP export for the entire collection.
- Open the local URL in the default browser after server startup.
