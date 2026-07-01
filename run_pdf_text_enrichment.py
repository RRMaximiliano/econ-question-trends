from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "code" / "06_enrich"))

from pdf_text_extraction import main  # noqa: E402


if __name__ == "__main__":
    main()
