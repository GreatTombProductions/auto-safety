"""
Acquire NHTSA consumer complaint data.

Source: https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip
Format: Tab-delimited, 51 fields, no header row, ~2.2M records, ~1.5GB uncompressed.

Also fetches active recall data for cross-referencing.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "raw_data"

COMPLAINTS_URL = "https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip"


def download_file(url: str, dest: Path, description: str) -> Path:
    """Download a file if not already present."""
    if dest.exists():
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"  {description}: Already downloaded ({size_mb:.0f} MB)")
        print(f"  Delete {dest} to re-download.")
        return dest

    print(f"  Downloading {description}...")
    print(f"  URL: {url}")

    result = subprocess.run(
        ["curl", "-L", "--fail", "-o", str(dest), url],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  ERROR: Download failed for {description}.", file=sys.stderr)
        sys.exit(1)

    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"  Downloaded: {size_mb:.0f} MB")
    return dest


def extract_file(zip_path: Path, dest_dir: Path) -> list[Path]:
    """Extract a zip file."""
    print(f"  Extracting {zip_path.name}...")
    subprocess.run(["unzip", "-o", str(zip_path), "-d", str(dest_dir)], check=True)
    extracted = sorted(dest_dir.glob("*.txt"))
    for f in extracted:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"    {f.name}: {size_mb:.0f} MB")
    return extracted


def download_all():
    """Download all data files."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Complaints
    cmpl_zip = RAW_DIR / "FLAT_CMPL.zip"
    cmpl_txt = RAW_DIR / "FLAT_CMPL.txt"

    if not cmpl_txt.exists():
        download_file(COMPLAINTS_URL, cmpl_zip, "NHTSA Complaints")
        extract_file(cmpl_zip, RAW_DIR)
    else:
        size_mb = cmpl_txt.stat().st_size / (1024 * 1024)
        print(f"  Complaints: Already extracted ({size_mb:.0f} MB)")

    # Note: NHTSA recall flat file URL is no longer available.
    # Recall cross-referencing is optional — transform handles missing file gracefully.


if __name__ == "__main__":
    print("Acquiring NHTSA data...")
    download_all()
