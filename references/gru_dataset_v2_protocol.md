# GRU v2: six-fold workout CV and compact resumable checkpoints

Approved 2026-10-12. Supersedes the v1 chronological CV for new experiments.
Mathematical model, 16 configurations, inputs, targets, masking, window boundaries,
normalization, fitting and selection criterion remain those in
`gru_dataset_v1_protocol.md`. No new covariates, filtering or weighting.

## Data and scientific interpretation

`data/processed/gru_dataset_v2/manifest.json` references the original source files.
The original chronological 80/20 development/test split is preserved: first 48
workouts development, latest 12 test. Only the CV assignment changes.

Shuffle the 48 development indices with NumPy `RandomState(42).permutation`, then
divide into six equally sized validation sets. Each fold trains from scratch on
the remaining 40 workouts and validates on 8. Every development workout validates
exactly once and trains five times. No individual temporal samples are split.
Fold membership is saved and shared by all 16 configurations. `--split-seed` is
used only during `--prepare`; training `--seed` does not change saved folds.

The new CV assesses held-out workouts mixed across historical time, not strictly
future workouts. The latest 12-workout test remains the temporal holdout and is
never used for tuning. Prescriptions remain inferred from observed power, so
results are conditional reconstruction rather than prospective independent-plan
prediction. Normalizers are fitted separately on each fold's 40 training workouts
only; validation uses the identical scaler.

## Metrics

Train and validation curves now both use the frozen end-of-epoch model in eval
mode. `train_nmse_eval` and `validation_nmse_eval` are watt-space MSE divided by
the same training target variance. RMSE/MAE/bias remain in W. The original online
training loss is retained as `train_loss_online`, separately from eval curves.
Best epoch minimizes mean per-workout validation RMSE, with earlier ties retained.

## Checkpoints and interruption recovery

Each run has only `checkpoints/best.pt` and `checkpoints/last.pt`.
The best is updated only on validation improvement; last is atomically replaced
at every committed epoch. Both contain full model/optimizer/scheduler/RNG/scaler,
identity and history state. Last additionally embeds an immutable best snapshot,
so it is the single transaction commit: after a crash, best can be restored even
if the interruption occurred before best.pt was replaced. There is no chain of
embedded snapshots. An interrupted partial epoch is replayed; committed epochs
and metric history are preserved. Resume accepts last.pt only.
Final evaluation is committed through result.json only after all its artifacts
are written. Resume regenerates uncommitted evaluation outputs, including files
left partially written by an interruption.

No per-epoch weight files. All epoch statistics are in metrics/history.json and
metrics/weight_statistics.csv. Historical epoch models other than best/last are
not retained, so arbitrary retrospective epoch inference is unavailable.
In frozen refit modes, there is no validation selection: best.pt represents the
final committed epoch, as does last.pt on completion.

## Output structure

```text
reports/gru_v2/
  experiment.json
  frozen_config.json              # after all CV runs finish
  summary/comparison.csv          # plus fold/workout/transition tables and .md
  configurations/w030_gru32/fold_01/
    run.json
    result.json
    checkpoints/best.pt
    checkpoints/last.pt
    metrics/history.json
    metrics/history.csv
    metrics/weight_statistics.csv
    metrics/validation_metrics.json
    metrics/validation_per_workout.csv
    metrics/validation_transitions.csv
    figures/training_curves.png
    predictions/validation_predictions.csv.gz
    logs/training.log
```

V1 manifests remain readable for historical inspection. V2 training rejects them.
Existing v1 results/checkpoints are preserved; they cannot be resumed into the new
CV because data membership, code and checkpoint format changed. All v2 runs start
from scratch. The old v1 protocol documents the historical implementation.

## Commands (repository root, PowerShell)

The v2 manifest has already been generated. Start the complete 16 x 6 experiment:

```powershell
.venv/Scripts/python -B scripts/train_gru.py --cv --dataset data/processed/gru_dataset_v2 --output reports/gru_v2 --epochs 100 --batch-size 256 --learning-rate 0.001 --seed 42 --device auto --threads 4
```

Resume all runs from their last committed checkpoint:

```powershell
.venv/Scripts/python -B scripts/train_gru.py --cv --output reports/gru_v2 --resume
```

Explicit resume checkpoint (the rest of the experiment also resumes):

```powershell
.venv/Scripts/python -B scripts/train_gru.py --cv --output reports/gru_v2 --resume reports/gru_v2/configurations/w030_gru32/fold_01/checkpoints/last.pt
```

After reviewing CV results, refit on 48 and evaluate the untouched 12:

```powershell
.venv/Scripts/python -B scripts/train_gru.py --evaluate-test --frozen-config reports/gru_v2/frozen_config.json --output reports/gru_v2_test
```

Explicit frozen full-data training, with no independent test left:

```powershell
.venv/Scripts/python -B scripts/train_gru.py --fit-all --frozen-config reports/gru_v2/frozen_config.json --output reports/gru_v2_all
```

To reproduce the manifest use a new destination:

```powershell
.venv/Scripts/python -B scripts/train_gru.py --prepare --split-seed 42 --dataset data/processed/gru_dataset_v2_rebuilt
```

Verification covers membership/coverage, scaler isolation, eval metrics, exact CPU
resume, best-state recovery, 96 synthetic runs, comparisons and frozen refits.
Final verification (2026-10-12): 113 passed, 1 skipped with
`pytest tests -q --ignore=tests/_generated --ignore=tests/test_prescription_plot_gaps.py`.
The excluded plotting test has a pre-existing Windows/fontTools DLL loading block.
The real v2 source hashes and unchanged development/test membership were checked;
the full real-data training was not launched.
