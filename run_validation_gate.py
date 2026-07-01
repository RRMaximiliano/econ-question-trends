from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "code" / "05_analysis"))

from validation_gate import main  # noqa: E402


if __name__ == "__main__":
    main()
