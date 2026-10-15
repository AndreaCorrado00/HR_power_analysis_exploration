# GRU prescribed-power reconstruction v1

Historical protocol. New experiments use `gru_dataset_v2_protocol.md` (approved
2026-10-12): shuffled six-fold CV, compact best/last checkpoints and eval curves.
Existing v1 results are retained for inspection; the current CLI starts v2 runs.

Protocol approved 2026-10-11. This experiment predicts measured cycling power,
not heart rate. Prescriptions in the source dataset were inferred from the same
measured traces: held-out performance is conditional reconstruction, not evidence
of prospective prediction from independently prescribed plans. `is_maximal` is a
dataset category, not a physiological claim. No additional covariates or models.

## Data and splits

Source: `data/processed/prescribed_workouts_final`. Derived directory contains
JSON manifests only: relative paths, workout IDs, timestamps, SHA256 and splits.
Sort by first observed UTC timestamp, reject duplicate IDs/tied start times.
First floor(0.8*N) workouts development, remainder locked test (48/12 for N=60).
Six expanding folds: validation block size floor(N_development/8), remaining
prefix initial training. For 48: train sizes 12,18,24,30,36,42; six validations
of 6 workouts each. Validation always follows training, no sample-level splits.

Load original CSVs on demand; no persisted copies or window tensors. Accept
finite measured power >=0 with numeric prescription or maximal category.
Preserve valid paused samples in their separate source segments. Reject windows
across source power segment boundaries, non-1-second timestamps, invalid rows
or timer state changes. No interpolation, filtering, resampling or gap filling.
At each segment start use shortened real context; no artificial observations.
All four windows score identical eligible timestamps, including short segments.

## Model and fitting

Experimental proposal (not a replication):
`P_hat(t) = sigma_y * Linear(GRU(x[max(segment_start,t-W+1):t])) + mu_y`.
W = 30,60,120,300 seconds; hidden layers = [32],[64],[32,32],[64,32].
Unidirectional independent windows, zero initial hidden state; no actual power
or HR input, no hidden-state carryover across windows. Linear unconstrained head.
GRU gates follow PyTorch GRU semantics. Parameters are dimensionless in normalized
space and are not physiological quantities. No claim against HR-power baselines;
this separate experiment compares only the 16 explicitly requested configurations.

Input channels: numeric prescription and binary `is_maximal`. Compute input
mean/std only over numeric eligible training samples (once per timestamp, not
over duplicated overlapping windows). For maximal samples put 0 in the normalized
numeric channel and 1 in flag: 0 is neutral encoding, not an invented watt target.
Keep source prescriptions missing for maximal samples. Target mean/std uses all
eligible measured training power, including maximal samples. Population std;
constant channels use scale 1 W. Validation/test never fit normalization.

Adam, learning rate 0.001, constant scheduler, batch 256, seed 42, 100 epochs.
MSE on normalized targets, no weighting, oversampling or gradient clipping.
Each eligible training endpoint appears once per epoch in a seeded permutation.
Validation metrics denormalized: MAE/RMSE/bias/residual SD in W, MSE in W^2.
Best epoch minimizes mean per-workout validation RMSE; ties choose earlier epoch.
CV ranking uses mean per-workout RMSE over all six best-epoch validation sets.
Also report pooled metrics, individual workout metrics, and maximal/nonmaximal.
Transition diagnostics: changes in numeric prescription or maximal flag within a
continuous segment; separate upward, downward, entering/leaving maximal, post-change
0-10,10-30,30-60 s bins. A newer transition resets the clock; no gap-crossing events.

## Persistence and final training

Save atomic full checkpoint every epoch: weights, Adam and constant scheduler,
Python/NumPy/torch CPU/CUDA and DataLoader-generator RNG, normalization, immutable
run configuration, split and seed, history, best epoch and per-parameter statistics.
Checkpoint is source of truth for history after interruption. Keep all epoch files;
resume from last committed epoch, repeat any interrupted partial epoch. Reject
changed source hashes, code/runtime or run configuration. Old-checkpoint resume
cannot overwrite a newer committed epoch. JSON/CSV histories and curves are
regenerable. Append log records; save run environment and source code hashes.
Exact continuation requires same runtime/device; deterministic algorithms enabled.

CV writes comparative CSVs, per-workout and transition CSVs, curves and a frozen
selection JSON. Final refit on development uses median (rounded up) of the selected
configuration's six best epochs, then evaluates test once. Never select on test.
Explicit `--fit-all --frozen-config PATH` refits on all 60 with that same frozen
configuration/epoch budget, fits scaling on all 60, and has no held-out metric.
Full-data mode must use a separate output directory from CV/test.

## Implementation and verification plan

1. `gru/data.py`: manifest creation/integrity and normalization/window datasets.
   Verify exact chronological memberships, source immutability, maximal encoding,
   no scaling leakage, identical endpoints, gaps/pauses and short segments.
2. `gru/model.py`, `gru/training.py`: architectures, deterministic optimizer,
   checkpoint/history transactions. Verify all shapes, causal input, watt metrics,
   uninterrupted/resumed equality and stale checkpoint rejection.
3. `gru/reporting.py`, `gru/cli.py`, `scripts/train_gru.py`: 96-run orchestration,
   comparisons, frozen selection, isolated holdout and all-data modes. Verify
   smoke CV with all configurations, resume, frozen refit/test and fit-all.
4. Generate actual manifests, run targeted and existing unit tests, and a bounded
   synthetic smoke experiment. Full scientific training is launched by the user
   with the documented CLI after implementation verification.

Dependency installation is isolated to `.venv`; additional pinned requirements
live in `requirements-gru.txt`. Existing application changes are outside scope.

## CLI (PowerShell, from repository root)

The manifest has already been generated. Rebuilding refuses an existing output;
use a new `--dataset` directory if a new source version is needed.

```powershell
# Only needed in a fresh environment:
.venv/Scripts/python -m pip install -r requirements-gru.txt

# Reproduce the manifests in a NEW directory, if needed:
.venv/Scripts/python -B scripts/train_gru.py --prepare --dataset data/processed/gru_dataset_v1_rebuilt

# Full 16 x 6 chronological CV, 100 epochs per fold:
.venv/Scripts/python -B scripts/train_gru.py --cv --dataset data/processed/gru_dataset_v1 --output reports/gru_v1 --epochs 100 --batch-size 256 --learning-rate 0.001 --seed 42 --device auto --threads 4

# Resume the same experiment; settings are recovered from experiment.json:
.venv/Scripts/python -B scripts/train_gru.py --cv --output reports/gru_v1 --resume

# Explicit checkpoint form (use the last committed epoch in that fold):
.venv/Scripts/python -B scripts/train_gru.py --cv --output reports/gru_v1 --resume reports/gru_v1/w030_gru32/fold_01/epoch_0001.pt

# After reviewing CV: frozen development refit and one final test evaluation:
.venv/Scripts/python -B scripts/train_gru.py --evaluate-test --dataset data/processed/gru_dataset_v1 --frozen-config reports/gru_v1/frozen_config.json --output reports/gru_v1_test

# After CV/test review: explicitly refit frozen configuration on ALL workouts:
.venv/Scripts/python -B scripts/train_gru.py --fit-all --dataset data/processed/gru_dataset_v1 --frozen-config reports/gru_v1/frozen_config.json --output reports/gru_v1_all

# Resume either refit, for example:
.venv/Scripts/python -B scripts/train_gru.py --fit-all --output reports/gru_v1_all --resume
```

`--device auto` resolves once to CUDA if available, otherwise CPU, and is saved.
The implementation environment has PyTorch 2.14.1+cpu; CUDA execution has not
been validated here. Same code/runtime/device required for exact continuation.
An explicit checkpoint older than another committed epoch is rejected; the
automatic `--resume` form finds the latest epoch for each run. No completed epoch
is retrained. Interrupted partial epochs are replayed from their previous commit.
Only load checkpoints produced by this trusted local workflow (full RNG state
requires Python-object deserialization).

`reports/gru_v1/comparison.csv` and `.md` compare all 16 configurations.
Per-workout, per-fold and transition CSVs sit alongside them. Each configuration
contains `fold_01` through `fold_06`, with `run.json`, `history.json/.csv`,
`training_curves.png`, `training.log`, `epoch_NNNN.pt`, `weights_NNNN.json`,
`latest.json`, `result.json`, and best-epoch validation reports/predictions.
The derived dataset directory itself contains only `manifest.json`.

Transition bins are descriptive diagnostics, not additional loss terms. Train
loss is the online normalized batch MSE; train watt metrics evaluate the final
model of that epoch on training samples. Validation uses that same final model.
CV comparison uses each fold's own selected epoch and therefore remains a tuning
estimate. The untouched final test is the independent model-selection holdout,
subject to the source prescription-inference limitation stated above.

Actual chronological boundary: development 2025-05-18 through 2026-08-11;
test 2026-08-19 through 2026-09-19. Source hashes are checked before every CLI run.

## Verification record (2026-10-11)

- 109 tests passed, 1 skipped with
  `.venv/Scripts/python -B -m pytest tests --ignore=tests/_generated --ignore=tests/test_prescription_plot_gaps.py -q --basetemp tmp/gru-suite-available`.
- The complete collection was attempted first. Existing
  `tests/test_prescription_plot_gaps.py` cannot collect because Windows application
  control blocks the installed `fontTools.misc.bezierTools` DLL. The same import
  fails independently of this subsystem; no security setting or existing PDF
  dependency was changed.
- GRU tests include all 96 synthetic fold runs, frozen test/all-data refits,
  continuous/resumed exact CPU weight and history equality, stale-checkpoint
  rejection, recovery after final checkpoint commit, source-hash checks,
  train-only scaling, all four long-window cutoffs and gap/segment boundaries.
- Real-source smoke: first 360 original rows of one first-fold training workout
  and one first-fold validation workout; 339/360 eligible endpoints respectively,
  one epoch of GRU(32), W=300. Artifacts under `reports/gru_v1_verification` are
  software verification only, not scientific CV results. PNG layout inspected.
- Full 100-epoch scientific CV has not been launched; the commands above start
  it and create the comparative table when the 96 runs complete.
