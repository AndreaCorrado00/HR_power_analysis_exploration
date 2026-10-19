"""Create descriptive diagnostics without changing frozen GRU training code."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from power_hr_eda.gru_diagnostics import main

if __name__=='__main__':
    main()
