from pathlib import Path
import sys


APP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_SRC = APP_ROOT.parents[1] / "src"

for path in (APP_ROOT, REPOSITORY_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
