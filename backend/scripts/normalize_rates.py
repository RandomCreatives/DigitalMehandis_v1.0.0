#!/usr/bin/env python3
"""
Normalise the scanned MoWUD rate booklets into a clean, auditable rate library.

Usage
-----
    python scripts/normalize_rates.py                # write normalised output
    python scripts/normalize_rates.py --check        # exit 1 if rows need review
    python scripts/normalize_rates.py --report-only  # just print the summary

What it does
------------
1. **Repairs** OCR damage in amounts, units and descriptions using the
   structural rules in ``app.utils.rate_ocr`` (the last two digits are always
   cents; glyph confusions are a fixed table).
2. **Classifies** every row: HEADER (section title / parent item, no price),
   ITEM (priced), or BROKEN (a price was present but could not be recovered).
3. **Cross-checks** the CSV and JSON copies of the same booklet. They are the
   same extraction in two formats, so agreement proves the *conversion* was
   lossless -- it cannot prove the OCR was right. Disagreement means a file
   drifted and must be regenerated.
4. **Flags outliers** inside each item group (4.3.1-4.3.4 should be the same
   order of magnitude); a value three times its siblings is a parsing failure,
   not an expensive item.
5. **Emits a review queue** -- nothing low-confidence is published as fact.

Outputs (committed, since this is the product's rate data)
---------------------------------------------------------
    data/rates/normalized/rates_normalized.json   clean rows + provenance
    data/rates/normalized/review_queue.csv        rows a human must confirm
    data/rates/normalized/rejected.csv            unrecoverable rows, with why
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.utils.rate_ocr import (  # noqa: E402
    CONF_CLEAN,
    CONF_REPAIRED,
    repair_amount,
    repair_description,
    normalise_unit,
    check_plausible,
)

RATES_DIR = ROOT / "data" / "rates"
OUT_DIR = RATES_DIR / "normalized"

#: A value this many times its group median is treated as a parse failure.
OUTLIER_FACTOR = 3.0
#: Groups smaller than this are too small to judge.
MIN_GROUP_FOR_OUTLIER_CHECK = 3


@dataclass
class RateRow:
    item_no: str
    description: str
    unit: str | None
    amount: Decimal | None
    confidence: float
    source_file: str
    kind: str = "ITEM"            # ITEM | HEADER | BROKEN
    repairs: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    cross_check: str = "single-source"

    @property
    def group(self) -> str:
        """Parent item number, e.g. '4.3.2' -> '4.3'."""
        return self.item_no.rsplit(".", 1)[0] if "." in self.item_no else ""

    @property
    def needs_review(self) -> bool:
        """A human must confirm this row before it is published as a rate."""
        return bool(self.flags) or self.kind == "BROKEN" or self.confidence < CONF_REPAIRED


# ── Reading the two formats ─────────────────────────────────────────────────

def read_csv(path: Path) -> list[RateRow]:
    rows: list[RateRow] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        for raw in reader:
            if not raw or not any(cell.strip() for cell in raw):
                continue
            cells = list(raw) + [""] * (4 - len(raw))
            item_no, desc, unit, cost = (c.strip() for c in cells[:4])
            # Skip the file's own header line, if it has one.
            if desc.strip().upper() == "DESCRIPTION" or item_no.strip().upper() in {
                "ITEM NO", "ITEM", "NO", "NO."
            }:
                continue
            rows.append(_build_row(item_no, desc, unit, cost, path.name))
    return rows


def read_json(path: Path) -> list[RateRow]:
    rows: list[RateRow] = []
    for rec in json.loads(path.read_text(encoding="utf-8")):
        rows.append(
            _build_row(
                str(rec.get("ID") or ""),
                str(rec.get("Description") or ""),
                str(rec.get("Unit") or ""),
                str(rec.get("Cost") or ""),
                path.name,
            )
        )
    return rows


def _clean_item_no(item_no: str) -> str:
    """'4. 13.7' -> '4.13.7'. The scanner splits item numbers at spaces."""
    cleaned = re.sub(r"\s+", "", item_no or "")
    return cleaned.rstrip(".")


def _build_row(item_no: str, desc: str, unit: str, cost: str, source: str) -> RateRow:
    item_no = _clean_item_no(item_no)
    description, desc_repairs = repair_description(desc)
    clean_unit, unit_repairs = normalise_unit(unit)
    amount = repair_amount(cost)

    repairs = list(amount.repairs) + list(unit_repairs) + list(desc_repairs)
    problems = list(amount.problems)

    if amount.value is None:
        # A row with no amount is a header *if* it reads like one, otherwise a
        # price that failed to parse.
        looks_like_header = not cost.strip() or not re.search(r"\d", cost)
        kind = "HEADER" if looks_like_header else "BROKEN"
        if looks_like_header:
            problems = []
        confidence = 0.0
    else:
        kind = "ITEM"
        confidence = amount.confidence
        problems.extend(check_plausible(amount.value, clean_unit, description))

    return RateRow(
        item_no=item_no,
        description=description,
        unit=clean_unit,
        amount=amount.value,
        confidence=confidence,
        source_file=source,
        kind=kind,
        repairs=repairs,
        problems=problems,
    )


# ── Cross-checking CSV against JSON ─────────────────────────────────────────

def _desc_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()[:70]


def _booklet_key(filename: str) -> str:
    """'Task - Concrete Work.csv' and 'Task_Concrete_Work.json' -> same key."""
    stem = Path(filename).stem.lower()
    stem = stem.replace("task", "").replace("manual", "")
    return re.sub(r"[^a-z0-9]+", "", stem)


def _pair_files(rows: list[RateRow]) -> list[tuple[str, str]]:
    """Match each CSV to its JSON twin by booklet name."""
    csvs = sorted({r.source_file for r in rows if r.source_file.endswith(".csv")})
    jsons = sorted({r.source_file for r in rows if r.source_file.endswith(".json")})
    pairs: list[tuple[str, str]] = []
    for c in csvs:
        best, best_score = None, 0.0
        for j in jsons:
            score = SequenceMatcher(None, _booklet_key(c), _booklet_key(j)).ratio()
            if score > best_score:
                best, best_score = j, score
        if best and best_score >= 0.75:
            pairs.append((c, best))
    return pairs


def cross_check(rows: list[RateRow]) -> None:
    """Compare the CSV and JSON copies of the same booklet, in place.

    Pairing is by **item number and occurrence index**, not by description:
    both formats are conversions of one extraction and preserve source order,
    while the source itself repeats item numbers (4.13.6 appears twice, 4.13.7
    three times). Fuzzy text matching paired those duplicates wrongly and
    reported false conflicts.

    Marks rows ``confirmed`` when both formats agree, ``conflict`` when they
    genuinely disagree (a conversion bug), ``description-drift`` when the
    amounts agree but the text does not.
    """
    by_file: dict[str, list[RateRow]] = defaultdict(list)
    for row in rows:
        by_file[row.source_file].append(row)

    for csv_file, json_file in _pair_files(rows):
        # nth occurrence of each item number, in source order
        csv_index: dict[tuple[str, int], RateRow] = {}
        seen: dict[str, int] = defaultdict(int)
        for row in by_file[csv_file]:
            key = (row.item_no, seen[row.item_no])
            seen[row.item_no] += 1
            csv_index[key] = row

        seen.clear()
        matched = 0
        for row in by_file[json_file]:
            key = (row.item_no, seen[row.item_no])
            seen[row.item_no] += 1
            twin = csv_index.get(key)
            if twin is None:
                row.cross_check = "no-counterpart"
                continue
            matched += 1
            similar = SequenceMatcher(
                None, _desc_key(row.description), _desc_key(twin.description)
            ).ratio()

            if row.amount is not None and twin.amount is not None:
                if row.amount == twin.amount:
                    row.cross_check = twin.cross_check = "confirmed"
                    row.confidence = twin.confidence = max(
                        row.confidence, twin.confidence, CONF_CLEAN
                    )
                    if similar < 0.80:
                        row.flags.append("description differs between formats")
                else:
                    row.cross_check = twin.cross_check = "conflict"
                    row.flags.append(f"CSV says {twin.amount}, JSON says {row.amount}")
                    twin.flags.append(f"CSV says {twin.amount}, JSON says {row.amount}")
            elif (row.amount is None) != (twin.amount is None):
                row.cross_check = twin.cross_check = "one-sided"
                row.flags.append("amount present in only one format")

        unmatched = len(by_file[csv_file]) - matched
        if unmatched:
            for row in by_file[csv_file][-unmatched:]:
                row.cross_check = "no-counterpart"


# ── Outlier detection inside an item group ─────────────────────────────────

def flag_outliers(rows: list[RateRow]) -> None:
    """Flag values far from their own siblings (4.3.1..4.3.4).

    A C-25 footing and a C-25 column cost within a few percent of each other.
    A value three times its siblings is an OCR failure, not a price.
    """
    # Grouped by unit as well: a slab priced per m² is not comparable to
    # concrete priced per m³, and comparing them produced false outliers.
    groups: dict[tuple[str, str, str | None], list[RateRow]] = defaultdict(list)
    for row in rows:
        if row.kind == "ITEM" and row.amount is not None and row.group:
            groups[(row.source_file, row.group, row.unit)].append(row)

    for siblings in groups.values():
        if len(siblings) < MIN_GROUP_FOR_OUTLIER_CHECK:
            continue
        median = statistics.median(float(r.amount) for r in siblings)
        if median <= 0:
            continue
        for row in siblings:
            value = float(row.amount)
            if value > median * OUTLIER_FACTOR or value < median / OUTLIER_FACTOR:
                row.flags.append(
                    f"outlier within group {row.group}: {value:,.2f} vs median "
                    f"{median:,.2f}"
                )


# ── Reporting ──────────────────────────────────────────────────────────────

def summarise(rows: list[RateRow]) -> None:
    total = len(rows)
    kinds = {k: sum(1 for r in rows if r.kind == k) for k in ("ITEM", "HEADER", "BROKEN")}
    review = [r for r in rows if r.needs_review and r.kind != "HEADER"]
    flagged = [r for r in rows if r.flags]
    repaired = [r for r in rows if r.repairs]
    items = [r for r in rows if r.kind == "ITEM"]
    clean = [r for r in items if r.confidence >= CONF_CLEAN]
    auto = [r for r in items if CONF_REPAIRED <= r.confidence < CONF_CLEAN and not r.flags]

    print(f"\nrows read            {total}")
    print(f"  priced items       {kinds['ITEM']}")
    print(f"  section headers    {kinds['HEADER']}  (correctly have no price)")
    print(f"  unrecoverable      {kinds['BROKEN']}")
    print(f"  clean as-is        {len(clean)}")
    print(f"  auto-repaired      {len(auto)}")
    print(f"amounts repaired     {len(repaired)}")
    print(f"confirmed CSV=JSON   {sum(1 for r in rows if r.cross_check == 'confirmed')}")
    print(f"conflicting formats  {sum(1 for r in rows if r.cross_check == 'conflict')}")
    print(f"flagged for review   {len(flagged)}")
    print(f"needs a human        {len(review)}")

    if flagged:
        print("\n— sample flags —")
        for row in flagged[:8]:
            print(f"  {row.item_no:8} {row.description[:48]:50} {row.flags[0]}")
    if kinds["BROKEN"]:
        print("\n— unrecoverable —")
        for row in [r for r in rows if r.kind == "BROKEN"][:8]:
            print(f"  {row.item_no:8} {row.description[:48]:50} {row.problems[0] if row.problems else ''}")


def write_outputs(rows: list[RateRow]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    accepted = [r for r in rows if r.kind == "ITEM" and not r.flags]
    review = [r for r in rows if r.needs_review and r.kind != "HEADER"]
    rejected = [r for r in rows if r.kind == "BROKEN"]

    payload = {
        "schema_version": 1,
        "source": {
            "title": "MoWUD Direct Cost, 3rd Quarter 2018",
            "issuing_authority": "Addis Ababa City Administration",
            "origin": "scanned PDF; amounts repaired from OCR damage",
            "currency": "ETB",
            "calendar": "EC",
        },
        "generated_by": "backend/scripts/normalize_rates.py",
        "row_count": len(accepted),
        "rows": [
            {
                "item_no": r.item_no,
                "description": r.description,
                "unit": r.unit,
                "amount": float(r.amount) if r.amount is not None else None,
                "currency": "ETB",
                "confidence": r.confidence,
                "cross_check": r.cross_check,
                "source_file": r.source_file,
                "repairs": r.repairs,
            }
            for r in sorted(accepted, key=lambda x: (x.source_file, x.item_no))
        ],
    }
    (OUT_DIR / "rates_normalized.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    def _dump(path: Path, subset: list[RateRow]) -> None:
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["item_no", "description", "unit", "raw_amount", "parsed_amount",
                 "confidence", "why", "source_file"]
            )
            for r in subset:
                writer.writerow([
                    r.item_no, r.description, r.unit or "",
                    "", r.amount if r.amount is not None else "",
                    r.confidence,
                    "; ".join(r.flags + r.problems) or "low confidence",
                    r.source_file,
                ])

    _dump(OUT_DIR / "review_queue.csv", review)
    _dump(OUT_DIR / "rejected.csv", rejected)

    print(f"\nwrote {len(accepted)} clean rows -> {OUT_DIR/'rates_normalized.json'}")
    print(f"wrote {len(review)} to review  -> {OUT_DIR/'review_queue.csv'}")
    print(f"wrote {len(rejected)} rejected -> {OUT_DIR/'rejected.csv'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if any row still needs human review")
    parser.add_argument("--report-only", action="store_true",
                        help="print the summary without writing files")
    args = parser.parse_args()

    rows: list[RateRow] = []
    for path in sorted(RATES_DIR.glob("*.csv")):
        if path.parent == OUT_DIR:
            continue
        rows.extend(read_csv(path))
    for path in sorted(RATES_DIR.glob("*.json")):
        if path.parent == OUT_DIR:
            continue
        rows.extend(read_json(path))

    if not rows:
        print("No rate files found in", RATES_DIR, file=sys.stderr)
        return 2

    cross_check(rows)
    flag_outliers(rows)
    summarise(rows)

    if not args.report_only:
        write_outputs(rows)

    if args.check:
        pending = [r for r in rows if r.needs_review and r.kind != "HEADER"]
        if pending:
            print(f"\n{len(pending)} rows still need review", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
