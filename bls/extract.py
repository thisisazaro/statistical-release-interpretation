"""Rebuild BLS inputs from the six release PDFs, offline. Requires pdftotext."""
import argparse
import hashlib
import json
import re
import subprocess
from calendar import month_name
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = [("2025-06", "2025-07"), ("2025-01", "2025-02"), ("2024-09", "2024-10")]


def extract(record):
    path = HERE / record["file"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record["sha256"]:
        raise ValueError(f"File digest changed: {path}")
    text = subprocess.check_output(["pdftotext", "-layout", str(path), "-"], text=True)
    pages = text.split("\f")
    day = date.fromisoformat(record["release_date"])
    date_string = f"{month_name[day.month]} {day.day}, {day.year}"
    if date_string not in pages[0]:
        raise ValueError(f"Release date {date_string} absent from PDF cover: {path}")

    page = pages[record["table_page"] - 1]
    lines = page.splitlines()
    row_index = next(i for i, line in enumerate(lines) if line.startswith("Total nonfarm"))
    header = " ".join(lines[:row_index])
    required = ["Table B-1. Employees on nonfarm payrolls", "[In thousands]",
                "Not seasonally adjusted", "Seasonally adjusted", "Change"]
    if any(term not in header for term in required):
        raise ValueError(f"Unexpected table header in {path}")
    # Four nonseasonally adjusted levels, four adjusted levels, then the printed change.
    values = re.findall(r"[-−]?\d[\d,]*", lines[row_index])
    if len(values) != 9:
        raise ValueError(f"Expected nine numeric cells in {path}")
    old, new, change = [int(x.replace(",", "").replace("−", "-")) for x in values[-3:]]
    if new - old != change:
        raise ValueError(f"Printed monthly change fails arithmetic check in {path}")
    return old, new


def make_cases():
    records = {r["reference_month"]: r for r in json.loads((HERE / "manifest.json").read_text())}
    levels = {month: extract(record) for month, record in records.items()}
    cases = []
    for earlier, later in PAIRS:
        previous, current = records[earlier], records[later]
        revised, latest = levels[later]
        cases.append({
            "id": "bls-" + later,
            "series": "All employees, total nonfarm, seasonally adjusted",
            "unit": "thousand jobs",
            "previous_date": previous["release_date"],
            "current_date": current["release_date"],
            "previous_url": previous["release_url"],
            "current_url": current["release_url"],
            "prior_month": earlier,
            "current_month": later,
            "previous_level": str(levels[earlier][1]),
            "revised_level": str(revised),
            "current_level": str(latest),
            "locator": "Table B-1, Total nonfarm, Seasonally adjusted. Prior release: "
                       f"{earlier}, PDF p. {previous['table_page']}. Current release: "
                       f"{earlier} and {later}, PDF p. {current['table_page']}.",
            "previous_file": "bls/" + previous["file"],
            "current_file": "bls/" + current["file"],
        })
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare with the saved cases.json")
    arguments = parser.parse_args()
    result = make_cases()
    if arguments.check:
        if result != json.loads((HERE / "cases.json").read_text()):
            raise SystemExit("Archived PDFs and cases.json disagree.")
        print(f"Verified {len(result)} BLS cases in six dated PDFs.")
    else:
        print(json.dumps(result, indent=2))
