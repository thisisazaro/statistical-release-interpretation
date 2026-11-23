"""Re-extract G.17 cases from the enclosed Federal Reserve ASCII releases."""
import argparse
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_URL = "https://www.federalreserve.gov/releases/g17/"
# The dates identify archived pairs; no numeric level or sign is hardcoded.
PAIRS = [
    ("20240117", "20240215"),
    ("20250815", "20250916"),
    ("20250318", "20250416"),
    ("20260416", "20260515"),
]


def monthly_summary(stamp):
    path = HERE / "releases" / f"{stamp}.txt"
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    date = datetime.strptime(stamp, "%Y%m%d").date()
    dateline = date.strftime("%B %d, %Y").replace(" 0", " ")
    assert any(dateline in line for line in lines[:6]), path
    title = next(i for i, line in enumerate(lines)
                 if "Industrial Production and Capacity Utilization:  Summary" in line)
    assert "Seasonally adjusted" in lines[title + 1]
    header = next(i for i in range(title, title + 15)
                  if lines[i].lstrip().startswith("Industrial production "))
    assert any("2017=100" in line for line in lines[title:header])
    months = lines[header].split("|")[1].split()
    index_row = next(i for i in range(header, header + 8)
                     if lines[i].lstrip().startswith("Total index "))
    levels = lines[index_row].split("|")[1].split()
    assert len(levels) == len(months) and months[-1].endswith("[p]")
    previous_estimates = lines[index_row + 1]
    assert previous_estimates.lstrip().startswith("Previous estimates ")
    return {
        "date": date.isoformat(), "header": header + 1, "row": index_row + 1,
        "months": months, "levels": levels, "previous": previous_estimates.split("|")[1].split(),
        "rate": lines[index_row].split("|")[2].split()[-1],
        "file": "g17/releases/" + path.name,
    }


def prior_month(month):
    year, m = map(int, month.split("-"))
    return f"{year - (m == 1):04d}-{(m-2) % 12 + 1:02d}"


def by_vintage():
    values = {}
    pattern = re.compile(r'^"(init|rev1)\.b50001\.s"\s+(\d{4})\s+(.+)$')
    for line in (HERE / "revision-vintages.txt").read_text().splitlines():
        match = pattern.match(line)
        if match:
            vintage, year, fields = match.groups()
            for month, value in enumerate(fields.split(), 1):
                if value != "na":
                    values[vintage, f"{year}-{month:02d}"] = Decimal(value)
    return values


def extract():
    calendar = (HERE / "release-calendar.html").read_text()
    dates = sorted(set(re.findall(r'href="(?:Revisions/)?(\d{8})/g17(?:rev)?\.txt"', calendar, re.I)))
    vintage = by_vintage()
    output = []
    for prev_stamp, curr_stamp in PAIRS:
        assert dates[dates.index(prev_stamp) + 1] == curr_stamp, "intervening release"
        prev, curr = monthly_summary(prev_stamp), monthly_summary(curr_stamp)
        month = prior_month(curr["date"][:7])
        prior = prior_month(month)
        assert prior_month(prev["date"][:7]) == prior
        for cell, ref_month in [(prev["months"][-1], prior), (curr["months"][-2], prior), (curr["months"][-1], month)]:
            assert cell[:3].lower() == datetime.strptime(ref_month, "%Y-%m").strftime("%b").lower()
        levels = [prev["levels"][-1], curr["levels"][-2], curr["levels"][-1]]
        assert curr["previous"][-1] == levels[0], "previous estimate in later summary differs"
        exact = [vintage["init", prior], vintage["rev1", prior], vintage["init", month]]
        assert [x.quantize(Decimal("0.1")) for x in exact] == list(map(Decimal, levels))
        for i in (0, 1):
            assert (Decimal(levels[2]) - Decimal(levels[i])).compare(0) == (exact[2] - exact[i]).compare(0)
        rate = ((exact[2] / exact[1] - 1) * 100).quantize(Decimal("0.1"))
        assert rate == Decimal(curr["rate"])
        previous_labels = prev["months"][-1]
        current_labels = ", ".join(curr["months"][-2:])
        output.append({
            "id": f"g17-{month}", "series": "Total industrial production index, seasonally adjusted (2017=100)",
            "unit": "index points", "previous_date": prev["date"], "current_date": curr["date"],
            "previous_url": BASE_URL + prev_stamp + "/g17.txt", "current_url": BASE_URL + curr_stamp + "/g17.txt",
            "prior_month": prior, "current_month": month,
            "previous_level": levels[0], "revised_level": levels[1], "current_level": levels[2],
            "locator": (
                "Industrial Production and Capacity Utilization: Summary; Seasonally adjusted; "
                "Industrial production, Total index; 2017=100 level block. "
                f"{prev_stamp}: lines {prev['header']}, {prev['row']} ({previous_labels}); "
                f"{curr_stamp}: lines {curr['header']}, {curr['row']} ({current_labels})."
            ),
            "previous_file": prev["file"], "current_file": curr["file"],
            "archive_crosscheck": {"series": "init.b50001.s, rev1.b50001.s, init.b50001.s",
                                   "levels": [str(x) for x in exact],
                                   "official_monthly_percent": curr["rate"]},
        })
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rebuild cases.json")
    args = parser.parse_args()
    cases = extract()
    dest = HERE / "cases.json"
    if args.write:
        dest.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n")
    else:
        assert cases == json.loads(dest.read_text()), "cases.json differs from the two printed releases"
    for row in cases:
        a, b, c = [Decimal(row[field]) for field in ("previous_level", "revised_level", "current_level")]
        print(f"{row['id']}    A={a}  B={b}  C={c}    Q1={c-b:+}  revision={b-a:+}  Q2={c-a:+}")
