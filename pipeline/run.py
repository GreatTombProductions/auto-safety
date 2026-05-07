"""
Full pipeline orchestrator for Auto Safety Complaints.

Usage:
    python3 pipeline/run.py              # Run full pipeline
    python3 pipeline/run.py --transform  # Skip acquisition, re-transform only
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

from acquire import download_all
from transform import transform


def main():
    args = set(sys.argv[1:])

    if "--transform" not in args:
        print("=" * 60)
        print("STEP 1: DATA ACQUISITION")
        print("=" * 60)
        download_all()
        print()

    print("=" * 60)
    print("STEP 2: TRANSFORM & INDEX")
    print("=" * 60)
    transform()
    print()

    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print("To serve locally: python3 -m http.server 8080")


if __name__ == "__main__":
    main()
