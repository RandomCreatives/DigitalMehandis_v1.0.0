# Spine foundations — element identity, grade conventions, correct citations

Status: implemented (as-built notes)
Date: 2026-10-30
Source: `DigitalMehandis_master_blueprint.md` (v1, 30 Oct 2026)

## Why

The master blueprint sets the direction — one spine (elements → quantity lines →
rates → assignments → progress → EVM), four faces (quantity, cost, time, cash) —
and nominates three "do it this week" items:

1. `elements` with a stable `ext_uid`, **before** there is data to migrate.
2. Fix the "BBS per EBCS 3" citation.
3. Concrete grade conventions (`grade_standard`), the local feature nobody else has.

This change implements those three, plus the defects the work uncovered.

## What the blueprint got wrong (and what we did instead)

| Blueprint claim | Reality in this repo | Action |
|---|---|---|
| `elements` is **missing** — "implement this first, before anything else" | `project_elements` already exists in `app/db/models_phase2.py` with element_code, type, discipline, section, floor, status, confidence, geometry, drawing/page links | **Augmented the existing table** with `ext_uid`, `revision`, `grade_standard` instead of creating a duplicate |
| `quantity_lines` is missing | `measurements` + `quantity_sources` + `boq_item_sources` already provide traceability | No change; rule/version link still outstanding |
| Rate library is "25 rates — too thin to trust" | 303 rows across 5 categories, ~47 % with unparseable OCR costs | Not attempted here — flagged as the next highest-value work |
| "14 issues" | 8 open | — |
| The `EBCS_3` slip is in the README | It is in **code defaults** (`schemas/bbs.py`, `modules/bbs`, `utils/bbs_calculator.py`) and in `docs/USER_GUIDE.md` | Fixed at the source |

## What changed

### 1. Element identity (migration `0004`)

- `project_elements.ext_uid` — sha1(project | element_code | row id), backfilled
  deterministically and idempotently, so two environments derive the same values.
- `project_elements.revision` — existing rows backfilled to `'R0'` rather than
  `NULL`, because SQL treats NULLs as distinct and would let duplicate uids
  through the unique index.
- `project_elements.grade_standard` — which strength convention a grade is in.
- Unique index `uq_project_element_uid_revision` on (project, ext_uid, revision).
- Verified: upgrade, backfill idempotency, indexes, and downgrade against a real
  engine.

This is the prerequisite for revision diffs, variations (added/omitted/
re-measured) and element-level progress — all still to be built, but nothing
will now need a data migration before they can be.

### 2. Code citations corrected

`EBCS-3` is *Design of Steel Structures*. The concrete code is **EBCS-2:1995**
(cube strength), superseded by **ES EN 1992-1-1:2015** (cylinder strength).

- `utils/bbs_calculator.py` now has a code registry with citations;
  `EBCS_3` survives only as a deprecated alias mapped to `EBCS_2`.
- Laps are computed from the EC2 §8.4 formula, with every coefficient as an
  argument so a reviewer can reproduce the number:
  `l_0 = α₁α₂α₃α₅α₆·l_b,rqd`, `f_bd = 2.25·η₁·η₂·f_ctd`.
- `BS_8666` **raises** when asked for a lap length instead of inventing one;
  it defines shape codes and bend deductions only.
- `bbs_bars` records `design_code` + `concrete_grade`, so a schedule shows which
  rule produced each lap. Legacy rows are labelled `EBCS_2_LEGACY_50D`, not
  retro-credited to a code they never followed.

Worked example (φ16, C25/30, f_yk 500): 969 mm under EC2, versus 800 mm under
the old hard-coded 50φ.

### 3. Grade conventions (`app/utils/concrete_grades.py`)

- Parses `C-25`, `C25`, `C25/30`; keeps cube vs cylinder explicit; converts at
  `f_ck,cyl ≈ 0.80·f_cu`.
- `rate_key` is convention-aware and snaps derived pairs onto real EN 206
  classes (`C25/31.25` → `C25/30`) so a rate can never be matched across
  conventions.
- The same BoQ text "C-25" yields `C20/25` (cube) or `C25/30` (cylinder) — and a
  φ16 lap that differs by **155 mm**. That is the feature.

### 4. Defects found while making the tests run

| Defect | Impact | Fix |
|---|---|---|
| `tests/conftest.py` issued `DROP DATABASE`/`CREATE DATABASE` unconditionally | CI sets a SQLite URL → the suite failed before running a single test | Harness now branches on the URL; SQLite file for CI/local |
| `aiosqlite` missing from `requirements.txt` | CI could not connect as configured | Added |
| `JSONB` columns in `models_phase3` | SQLite cannot render them → no test could run | `JSON().with_variant(JSONB, "postgresql")` — JSONB preserved on Postgres |
| `app.modules.drawings` imported `BOQItem` from `app.db.models` | `ImportError`; the loader logs and continues, so **20 routes vanished** with no failure | Correct import + regression test importing every module |
| `rapidfuzz` imported but not declared | DXF classification fails on a clean install | Added to requirements |

## Not done yet (next)

1. Rate-data validator: quarantine the ~47 % unparseable OCR rows, fix m²/m³
   mixups, retire the dead `import_mowud_rates.py` (it looks for PDFs that no
   longer exist).
2. `assignments` (BoQ ↔ activity), `progress_records`, `baselines` — the other
   three spine tables.
3. Excel/CSV `IngestAdapter` — the phase-1 proof test.
4. CLA/DCO, licence detection, v0.1.0 release.
5. Frontend lint is unconfigured (`next lint` prompts interactively), so the CI
   `npm run lint` job cannot pass.

## Proof

```
$ pytest -q
54 passed
```

(`backend/tests/test_concrete_grades.py`, `test_modules_load.py` and the
rewritten `test_bbs_calculator.py` carry the new assertions; the EC2 lap
figures are hand-checked in the test docstrings.)
