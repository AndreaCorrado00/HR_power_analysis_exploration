"""Run with .venv/Scripts/python scripts/extract_prescribed_workouts.py --output PATH."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from power_hr_eda.prescription_cli import main

if __name__=='__main__':
    raise SystemExit(main())
