# Rate data pipeline — repairing the OCR'd booklets and keeping them current

Status: repair implemented; quarterly pipeline proposed
Date: 2026-10-30

## The problem

The MoWUD quarterly direct-cost booklets reach us as **scanned PDFs**. The
existing extraction produced 303 rows of which roughly half were unusable:

| Damage | Example | Cause |
|---|---|---|
| Glyph confusion | `l4.858.24` (was 14,858.24) | scanner reads `l` as `1` |
| Glyph confusion | `3,44g.52` (was 3,449.52) | `g` read as `9` |
| Separator loss | `19.158.42` (was 19,158.42) | dot used for both separators |
| Separator loss | `I 7,376 92` (was 17,376.92) | space where the decimal point was |
| Prose captured as price | `20183rd0uarter(0n1y01rectc05t)` | page footer read as a row |
| Lost rows | JSON files have 1–2 fewer rows each than their CSVs | lossy conversion |

None of this is random. It is **systematic**, and systematic damage is
repairable.

## Part 1 — Repairing what we already have (done)

`backend/app/utils/rate_ocr.py` + `backend/scripts/normalize_rates.py`.

### The rule that makes repair possible

Every amount in these booklets carries **exactly two decimal places**. So:

> The final two digits are always the cents. Everything to their left is the
> integer part, regardless of which separator glyph the scanner produced.

That single rule resolves the ambiguity that makes OCR'd money dangerous.
`19.158.42` cannot be 19.158 with a `42` suffix; it is 19,158.42.

### What the pipeline does

1. **Repair** — a fixed glyph table (`l/I/|/i`→`1`, `O/o/Q`→`0`, `g/q`→`9`,
   `S/s`→`5`, `B`→`8`), applied **to numeric fields only**. Applying it to
   descriptions would turn "Slab" into "5lab", so description repair uses a
   conservative whole-word list instead.
2. **Classify** — `ITEM` (priced), `HEADER` (section title, correctly priceless),
   `BROKEN` (a price was there but could not be recovered).
3. **Cross-check** the CSV against its JSON twin, paired by item number **and
   occurrence index** (the source repeats item numbers — 4.13.6 appears twice,
   4.13.7 three times, so fuzzy text matching pairs them wrongly).
4. **Flag outliers** within an item group *and unit* — a C-25 footing and a C-25
   column cost within a few percent; a value 3× its siblings is an OCR failure,
   not a price.
5. **Emit a review queue** — nothing uncertain is published as fact.

### Result on the real data

| | |
|---|---|
| Rows read | 612 |
| Priced items | 403 |
| Section headers (correctly priceless) | 207 |
| **Clean as-is** | **387** |
| **Auto-repaired, no flags** | **10** |
| Flagged for human confirmation | 32 |
| Unrecoverable | 2 |
| Confirmed identical in CSV and JSON | 232 |
| Real format conflicts found | 2 |

So **~96 % of the priced rows are now usable**, versus roughly half before.

Two genuine defects surfaced that no amount of repair could fix, because they
are upstream:

- **The JSON files lose rows** — 41 vs 43 in masonry, 41 vs 42 in excavation,
  77 vs 79 in concrete. The ordinal-shift conflict at 5.1 is this bug showing
  through. **Regenerate or drop the JSONs; the CSVs are the better source.**
- **Duplicate item numbers in the source** (4.13.6 ×2, 4.13.7 ×3 with different
  descriptions and prices). Our data model must tolerate this rather than
  assuming `item_no` is unique.

## Part 2 — Extracting it correctly next quarter

Four rules, in priority order.

### Rule 1: get a text-layer PDF before touching OCR

OCR is a last resort, not a method. Before any scanning:

- Ask the issuing office (Addis Ababa City Administration / MoWUD) for the
  **digital original**. These booklets are authored in Word or Excel and printed;
  a digital copy usually exists.
- Ask for the **Excel/Word working file** — many bureaus will share it.
- Check published portals for a non-scan PDF (`pdffonts file.pdf` returns fonts
  → there is a text layer → use `pdfplumber`, never OCR).

**Every quarter spent on a clean digital file saves a week of review.** This is
the single highest-leverage action and it is an email, not code.

### Rule 2: if you must OCR, OCR the column, not the page

Scan quality drives error rate more than any algorithm:

- 400 DPI minimum, deskewed, greyscale.
- **Detect the table first**, then crop the price column and OCR that strip alone
  with a numeric whitelist (`0123456789.,`). Restricting the alphabet removes
  most glyph confusion before it happens.
- **Two independent engines** (e.g. Tesseract + PaddleOCR) and compare. Where
  they agree, confidence is high; where they disagree, a human looks. This is a
  genuine independent check — unlike CSV-vs-JSON, which was one extraction
  written twice.
- Store the **page image and the bounding box** for every amount, so the review
  screen can show the reviewer the pixel the number came from.

### Rule 3: never auto-publish a price

The review gate is not bureaucracy; a wrong rate propagates into every tender
that uses the library.

```
extract → repair → validate → [human review] → publish → lock
```

Only two things can leave the review queue automatically:

- a row confirmed by two independent engines, **and**
- inside the plausibility band for its unit and trade, **and**
- within the expected movement of the previous quarter (see Rule 4).

Everything else is a queue entry with its evidence attached.

### Rule 4: compare against the *previous* quarter, always

Each new booklet is diffed against the last one:

- **Rate movement** per item (e.g. "C-25 concrete up 6.2 % QoQ"). Large jumps are
  either real inflation or a parse error; the diff tells you where to look first.
- **New and removed items.**
- **Items that did not move at all** — suspicious in a high-inflation market and
  often a sign a row was copied rather than extracted.

This produces a **quarterly rate-movement report**, which is a sellable artefact
in its own right: contractors and consultants want to know how much their rates
should have moved before a tender.

## The quarterly ritual (~half a day once the pipeline is trusted)

| Step | Who | Time |
|---|---|---|
| Obtain the booklet; check for a text layer | analyst | 30 min |
| If digital: parse with `pdfplumber` and stop here | script | 10 min |
| If scanned: OCR both engines, crop columns, compare | script | 1–2 hrs |
| Run `normalize_rates.py`; read the summary | analyst | 15 min |
| Work the review queue with the page images beside it | QS reviewer | 1–4 hrs |
| Diff against last quarter; publish the movement report | QS reviewer | 1 hr |
| Publish + lock the set; record the source date | admin | 10 min |

## What this needs in the data model

The blueprint already calls for `rate_sets` with `source_date`; this pipeline is
what makes that table meaningful. Required, per row:

| Field | Why |
|---|---|
| `raw_text` | the exact characters the scanner produced |
| `page_number`, `bbox` | where on the page the number is — evidence for review |
| `ocr_engine`, `ocr_confidence` | which method produced it, and how sure it was |
| `repairs` | which substitutions were applied (`l`→`1`, space→decimal) |
| `review_state` | `auto` / `approved` / `rejected` + reviewer + date |
| `rate_set_id` | which quarterly set the row belongs to |

`RawRateImportRow` already exists in `app/db/models_cost.py` and is unused — it
is the right home for this.

Two governance rules from the master blueprint apply directly:

- **Rules and rates are data with versions, never code.** `rate_sets.source_date`
  answers "why did this number change?".
- **Lock a rate set the moment it is used in a submitted tender.** A tender priced
  on Q3 rates must not silently repoint to Q4.

## Immediate next steps

1. Regenerate the JSONs from the CSVs, or delete them — the CSVs are strictly
   better and the JSONs have already lost rows.
2. Wire `data/rates/normalized/rates_normalized.json` into the rate library,
   replacing the raw OCR files as the ingest source.
3. Build the review screen (page image + bbox + proposed amount + approve/reject).
   Without it, the 32 flagged rows stay stuck.
4. Add `rate_sets` with `source_date` / `quarter` / `locked_at`, and hang the
   normalized rows off it.
5. Email the issuing office for digital originals. Do this before writing any
   more OCR code.
