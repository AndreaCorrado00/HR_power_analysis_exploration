"""Run segment-safe power residual diagnostics, AR fitting and final test."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

from power_hr_eda.power_residual_ar.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
