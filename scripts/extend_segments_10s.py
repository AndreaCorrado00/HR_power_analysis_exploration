"""Rebuild the approved G1/G2 archive with actual FIT records at t in [-10, 0)."""
from __future__ import annotations

import collections
import csv
import hashlib
import io
import json
from datetime import datetime, timedelta
from pathlib import Path
import zipfile

import fitdecode

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dataset/dataset_segments_G1_G2.zip"
FITS = ROOT / "dataset/cleaned_only_road_activieties.zip"
OUTPUT = ROOT / "dataset/dataset_segments_G1_G2_extended_10s.zip"
RUN = ROOT / "webapp/model_identification_app/storage/runs/20260926T060032Z__Up_to_Down_under60s__p1d__raw__70-10-20__s42__n8-f42__00e47e9c.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=None)))


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def build():
    run_bytes = RUN.read_bytes()
    run = json.loads(run_bytes)
    source_bytes = SOURCE.read_bytes()
    assert run["dataset"]["sources"] == [{"name": SOURCE.name, "sha256": sha(source_bytes)}]
    assert run["split"] == run["dataset"]["split"]
    run_by_file = {s["filename"].split("::", 1)[1]: s for s in run["dataset"]["segments"]}
    split_by_id = {sid: split for split, ids in run["split"]["assignments"].items() for sid in ids}
    assert len(split_by_id) == len(run_by_file) == 56
    report = {
        "source_archive": SOURCE.name, "source_sha256": sha(source_bytes),
        "fit_archive": FITS.name, "fit_archive_sha256": sha(FITS.read_bytes()),
        "reference_run": RUN.name, "reference_run_sha256": sha(run_bytes),
        "window": "[original start_timestamp - 10 seconds, original start_timestamp)",
        "elapsed_seconds": "Relative to original segment start; pre-window values are negative.",
        "completeness_rule": "All ten original UTC second timestamps from -10 through -1 present with power and HR; gaps or missing signals mark incomplete. No interpolation, filtering, resampling or deduplication.",
        "identity": "original_segment_id is the original importer hash of original ZIP name, CSV path and original CSV SHA256; IDs and splits are archival metadata, not restored by the current webapp importer.",
        "sources": {}, "segments": [],
    }
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as original, zipfile.ZipFile(FITS) as fit_zip:
        manifest = json.loads(original.read("manifest.json"))
        cache = {}
        extended = {}
        for segment in manifest["segments"]:
            name = segment["csv_file"]
            data = original.read(name)
            original_rows = rows(data)
            activity = original_rows[0]["activity_id"]
            assert all(r["activity_id"] == activity for r in original_rows)
            assert segment["activity_id"] == activity
            start = stamp(original_rows[0]["timestamp"])
            assert start == stamp(segment["start_timestamp"])
            assert float(original_rows[0]["elapsed_seconds"]) == 0
            if activity not in cache:
                entry = fit_zip.getinfo(activity)
                payload = fit_zip.read(activity)
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    path = Path(payload.decode())
                    payload = path.read_bytes()
                    resolved = str(path)
                else:
                    resolved = FITS.name + "::" + activity
                records = []
                with fitdecode.FitReader(io.BytesIO(payload)) as reader:
                    for frame in reader:
                        if isinstance(frame, fitdecode.FitDataMessage) and frame.name == "record":
                            t = frame.get_value("timestamp", fallback=None)
                            if t is not None:
                                records.append((t, frame.get_value("power", fallback=None), frame.get_value("heart_rate", fallback=None)))
                records.sort(key=lambda r: r[0])
                cache[activity] = records
                cadence = collections.Counter((b[0]-a[0]).total_seconds() for a, b in zip(records, records[1:]))
                report["sources"][activity] = {"resolved_source": resolved, "sha256": sha(payload), "record_count": len(records), "sampling_intervals_seconds": dict(cadence)}
            pre = [r for r in cache[activity] if start-timedelta(seconds=10) <= r[0] < start]
            expected = {start-timedelta(seconds=i) for i in range(1, 11)}
            missing_times = sorted(expected - {r[0] for r in pre})
            missing_power = sum(r[1] is None for r in pre)
            missing_hr = sum(r[2] is None for r in pre)
            out = io.StringIO(newline="")
            writer = csv.DictWriter(out, fieldnames=list(original_rows[0]), lineterminator="\r\n")
            for t, power, hr in pre:
                writer.writerow({"activity_id": activity, "first_lap": original_rows[0]["first_lap"], "last_lap": original_rows[0]["last_lap"], "timestamp": t.isoformat(sep=" "), "elapsed_seconds": (t-start).total_seconds(), "power_w": power, "heart_rate_bpm": hr})
            # Retain the exact original header and body, including original line endings.
            header, body = data.split(b"\n", 1)
            extended[name] = header + b"\n" + out.getvalue().encode() + body
            sid = sha((SOURCE.name + "::" + name + sha(data)).encode())[:24]
            if name in run_by_file:
                assert run_by_file[name]["id"] == sid
                assert run_by_file[name]["sha256"] == sha(data)
            detail = {
                "csv_file": name, "activity_id": activity, "original_segment_id": sid,
                "original_csv_sha256": sha(data), "extended_csv_sha256": sha(extended[name]),
                "original_start_timestamp": segment["start_timestamp"],
                "original_samples": len(original_rows), "pre_window_samples": len(pre),
                "pre_window_complete": not (missing_times or missing_power or missing_hr),
                "missing_second_timestamps": [t.isoformat() for t in missing_times],
                "missing_power_samples": missing_power, "missing_hr_samples": missing_hr,
                "duplicate_pre_window_timestamps": len(pre)-len({r[0] for r in pre}),
                "first_available_timestamp": pre[0][0].isoformat() if pre else None,
                "last_available_timestamp": pre[-1][0].isoformat() if pre else None,
                "selected_in_reference_run": name in run_by_file,
                "reference_split": split_by_id.get(sid),
            }
            report["segments"].append(detail)
            segment["original_segment_id"] = sid
            segment["pre_window"] = detail
        assert set(run_by_file) <= set(extended)
        report["summary"] = {
            "segments": len(extended), "fit_sources": len(cache),
            "added_records": sum(s["pre_window_samples"] for s in report["segments"]),
            "incomplete_pre_windows": sum(not s["pre_window_complete"] for s in report["segments"]),
            "reference_split_counts": {k: len(v) for k, v in run["split"]["assignments"].items()},
        }
        manifest["pre_window_extension"] = {"seconds": 10, "report": "metadata/pre_window_10s.json", "reference_run": "metadata/reference_run.json", "original_segment_bounds_preserved": True}
        extra = {
            "manifest.json": encoded(manifest),
            "metadata/pre_window_10s.json": encoded(report),
            "metadata/reference_run.json": run_bytes,
            "metadata/extend_segments_10s.py": Path(__file__).read_bytes(),
            "metadata/PRE_WINDOW_README.md": (
                "# Estensione pre-window di 10 secondi\n\n"
                "Ogni CSV antepone i record FIT reali in [t_start-10s, t_start). "
                "I record originali sono invariati; elapsed_seconds resta riferito all'inizio originale. "
                "first_lap/last_lap identificano il segmento destinatario anche nelle righe aggiunte. "
                "Nessuna interpolazione, normalizzazione o riclassificazione.\n\n"
                "metadata/pre_window_10s.json documenta sorgenti, hash, campioni mancanti e completezza "
                "rispetto alla griglia di registrazione a 1 secondo, richiedendo anche potenza e HR. "
                "I valori mancanti restano vuoti. I bounds nel manifest riguardano il segmento originale.\n\n"
                "metadata/reference_run.json conserva integralmente il run, inclusi i 56 segmenti "
                "selezionati, i loro ID e lo split 34/19/3. Gli altri segmenti non ricevono uno split. "
                "L'importatore webapp attuale rigenera ID e split: questi metadati non ne modificano "
                "il comportamento. Nessun nuovo fitting eseguito.\n\n"
                "Riproduzione: collocare metadata/extend_segments_10s.py in scripts/ del repository "
                "ed eseguire python scripts/extend_segments_10s.py con fitdecode installato e le "
                "sorgenti originali disponibili. Lo ZIP cleaned contiene link ai FIT locali.\n"
            ).encode(),
        }
        # Exclusive creation protects an existing deliverable from accidental overwrite.
        with zipfile.ZipFile(OUTPUT, "x", compression=zipfile.ZIP_DEFLATED) as target:
            for entry in original.infolist():
                target.writestr(entry, extended.get(entry.filename, extra.get(entry.filename, original.read(entry.filename))))
            for name, data in extra.items():
                if name not in original.namelist():
                    target.writestr(name, data)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    build()
