"""
Repair and validate amounts OCR'd from scanned government rate publications.

Why this exists
---------------
The MoWUD quarterly direct-cost booklets are distributed as **scanned PDFs**.
Extracting them produces two classes of damage:

1. **Character confusion** -- the scanner reads glyph shapes, not characters::

       l / I / | / i  ->  1        l4.858.24  -> 14.858.24
       O / o / Q      ->  0        I :2:o     -> 1:2:0
       g / q          ->  9        3,44g.52   -> 3,449.52
       S / s          ->  5        1 :2:S     -> 1:2:5
       B              ->  8        8.G.L      -> B.G.L

2. **Separator loss** -- the thousands separator and the decimal point are both
   detected as a dot, a comma, or a space::

       19.158.42   -> 19,158.42
       23,l06.85   -> 23,106.85
       1,1.77.21   -> 1,177.21
       25,186 85   -> 25,186.85
       I 7,376 92  -> 17,376.92

Both are recoverable because the source has a rigid structure: **every amount in
these booklets carries exactly two decimal places**. So the last two digits are
always the cents, and everything to their left is the integer part regardless of
what separator glyph the scanner produced.

This module repairs what is unambiguous, refuses to guess what is not, and
returns a confidence so the caller can route low-confidence rows to human
review instead of publishing a wrong price.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

#: Glyph confusions applied **to numeric fields only**. Applied to descriptions
#: they would corrupt real words (e.g. "Slab" -> "5lab"), so description repair
#: is a separate, much more conservative function.
DIGIT_CONFUSIONS: dict[str, str] = {
    "l": "1",
    "I": "1",
    "i": "1",
    "|": "1",
    "!": "1",
    "O": "0",
    "o": "0",
    "Q": "0",
    "D": "0",
    "g": "9",
    "q": "9",
    "S": "5",
    "s": "5",
    "B": "8",
    "Z": "2",
    "z": "2",
    "G": "6",
    "b": "6",
    "T": "7",
}

#: Characters that may legitimately appear in an amount field.
_ALLOWED = set("0123456789.,")

_CURRENCY_RE = re.compile(r"(?i)\b(?:ETB|BIRR|BTC)\b|Br\.?|ብር")

#: confidence values
CONF_CLEAN = 1.0
CONF_REPAIRED = 0.9
CONF_NO_CENTS = 0.6
CONF_LOW = 0.3


@dataclass(frozen=True)
class RepairedAmount:
    """An amount recovered from OCR text, with its provenance."""

    value: Decimal | None
    confidence: float
    raw: str
    repairs: tuple[str, ...] = field(default_factory=tuple)
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.value is not None

    @property
    def needs_review(self) -> bool:
        return self.value is None or self.confidence < CONF_REPAIRED

    def describe(self) -> dict:
        return {
            "raw": self.raw,
            "value": str(self.value) if self.value is not None else None,
            "confidence": self.confidence,
            "repairs": list(self.repairs),
            "problems": list(self.problems),
        }


def _map_confusions(token: str) -> tuple[str, list[str]]:
    """Map glyph confusions inside a single numeric token."""
    out = []
    repairs: list[str] = []
    for ch in token:
        if ch in _ALLOWED:
            out.append(ch)
            continue
        mapped = DIGIT_CONFUSIONS.get(ch)
        if mapped is not None:
            out.append(mapped)
            repairs.append(f"{ch!r}->{mapped!r}")
        else:
            out.append(ch)  # kept so validation can reject it
    return "".join(out), repairs


def _assemble(integer_part: str, cents: str | None) -> tuple[Decimal | None, str | None]:
    """Build a Decimal from digit groups, requiring the integer part to be digits."""
    int_digits = re.sub(r"[.,\s]", "", integer_part)
    if not int_digits:
        return None, "no digits found"
    if not int_digits.isdigit():
        return None, f"non-numeric characters in amount: {integer_part!r}"
    try:
        value = Decimal(int_digits + ("." + cents if cents else ""))
    except InvalidOperation:  # pragma: no cover - defensive
        return None, "could not build a number"
    return value, None


def repair_amount(raw: str | None) -> RepairedAmount:
    """Parse an OCR'd amount, repairing unambiguous damage.

    Returns a :class:`RepairedAmount`; ``value`` is ``None`` when the text cannot
    be recovered without guessing.

    The governing rule is structural: **every amount in these booklets carries
    exactly two decimal places**, so the final two digits are always the cents
    and everything to their left is the integer part, whatever glyph the
    scanner used for a separator.

    Examples:
        >>> repair_amount("l4.858.24").value
        Decimal('14858.24')
        >>> repair_amount("I 7,376 92").value
        Decimal('17376.92')
        >>> repair_amount("3,44g.52").value
        Decimal('3449.52')
        >>> repair_amount("l 6,369.09").value
        Decimal('16369.09')
        >>> repair_amount("SUB STRUCTURE").value is None
        True
    """
    if raw is None or not str(raw).strip():
        return RepairedAmount(None, 0.0, raw or "", problems=("empty",))

    text = _CURRENCY_RE.sub("", str(raw)).strip()

    # A row with no digits at all is a section header or a description, not a
    # failed amount. Say so plainly instead of reporting garbled characters.
    if not re.search(r"\d", text):
        return RepairedAmount(None, 0.0, raw, problems=("not an amount (no digits)",))

    # Footnotes and watermarks ("Only Correct", page headers) carry digits by
    # accident. Prose, not an amount.
    if len(re.findall(r"[A-Za-z]", text)) > 6:
        return RepairedAmount(None, 0.0, raw, problems=("not an amount (prose)",))

    repairs: list[str] = []
    tokens: list[str] = []
    for tok in text.split():
        mapped, tok_repairs = _map_confusions(tok)
        repairs.extend(tok_repairs)
        tokens.append(mapped)

    if not tokens:
        return RepairedAmount(None, 0.0, raw, problems=("empty after cleanup",))

    cents: str | None = None
    integer_part: str

    if len(tokens) > 1:
        # A trailing 2-digit group after whitespace is the cents:
        # "I 7,376 92", "25,186 85", "8,611 .36"
        last = tokens[-1].lstrip(".,")
        if re.fullmatch(r"\d{2}", last):
            cents = last
            integer_part = "".join(tokens[:-1])
            repairs.append("space used as decimal point")
        else:
            # Whitespace merely split the number: "l 6,369.09"
            integer_part = "".join(tokens)
            repairs.append("collapsed whitespace inside amount")
    else:
        integer_part = tokens[0]

    if cents is None:
        canonical = re.fullmatch(r"(\d{1,3}(?:,\d{3})*)\.(\d{2})", integer_part)
        if canonical:
            # Canonical 1,234.56 -- nothing to repair.
            value, problem = _assemble(canonical.group(1), canonical.group(2))
            if value is None:
                return RepairedAmount(None, 0.0, raw, tuple(repairs), (problem,))
            return RepairedAmount(value, CONF_CLEAN if not repairs else CONF_REPAIRED, raw, tuple(repairs))

        match = re.search(r"[.,](\d{2})$", integer_part)
        if match:
            # The last separator is the decimal point; anything before it is the
            # integer part and all its separators are thousands markers.
            cents = match.group(1)
            integer_part = integer_part[: match.start()]

    if "." in integer_part and "," in integer_part:
        repairs.append("mixed separators normalised")
    elif "." in integer_part:
        repairs.append("'.' used as thousands separator")

    value, problem = _assemble(integer_part, cents)
    if value is None:
        return RepairedAmount(None, 0.0, raw, tuple(repairs), (problem,))

    return RepairedAmount(value, _confidence(repairs, cents), raw, tuple(repairs))


def _confidence(repairs: list[str], cents: str | None) -> float:
    """Confidence in a repaired amount.

    Two decimals present -> the structure pinned the decimal point, so repairs
    are mechanical. No decimals -> the integer part was inferred by deleting
    separators, which can silently merge or split groups, so it needs a human.
    """
    if cents is None:
        return CONF_NO_CENTS
    if not repairs:
        return CONF_CLEAN
    return CONF_REPAIRED


# ── Description repair (conservative) ────────────────────────────────────────

#: Whole-word substitutions only. Never applied character-wise, because "Slab"
#: and "l0cm" differ by exactly the kind of glyph the scanner confuses.
_WORD_FIXES: dict[str, str] = {
    "l0cm": "10cm",
    "l5cm": "15cm",
    "l8cm": "18cm",
    "l00cm": "100cm",
    "Concrète": "Concrete",
    "concrète": "concrete",
    "chernicals": "chemicals",
    "reinfoicement": "reinforcement",
    "inforcement": "reinforcement",
    "foimwork": "formwork",
    "fromwork": "formwork",
    "tormwork": "formwork",
    "tromwork": "formwork",
    "adiuixtui": "admixture",
    "adiuixtuie": "admixture",
    "playwood": "plywood",
    "scafolding": "scaffolding",
    "Masonary": "Masonry",
    "masonary": "masonry",
    "Moriar": "Mortar",
    "vibiated": "vibrated",
    "wiih": "with",
    "Semiclastic": "Semielastic",
    "Semielastic": "Semielastic",
}

_CEMENT_RATIO_RE = re.compile(r"(?i)\b(\d+)\s*(hg|kg|kgs|Kq)\s+of\s+cement")
_UNIT_FIXES = {
    "m3": "m³",
    "m2": "m²",
    "m'": "m³",
    "ml": "ml",
    "no": "no.",
    "No": "no.",
    "pcs": "no.",
    "kg": "kg",
    "qnt": "quintal",
}


def repair_description(text: str | None) -> tuple[str, tuple[str, ...]]:
    """Conservatively clean a description. Returns (text, repairs applied)."""
    if not text:
        return "", ()
    out = " ".join(str(text).split())
    repairs: list[str] = []

    def _cement(match: re.Match) -> str:
        repairs.append(f"cement quantity unit {match.group(2)!r} -> 'kg'")
        return f"{match.group(1)} kg of cement"

    out = _CEMENT_RATIO_RE.sub(_cement, out)

    for wrong, right in _WORD_FIXES.items():
        pattern = re.compile(rf"\b{re.escape(wrong)}\b")
        if pattern.search(out):
            out = pattern.sub(right, out)
            repairs.append(f"{wrong!r} -> {right!r}")

    return out, tuple(repairs)


def normalise_unit(unit: str | None) -> tuple[str | None, tuple[str, ...]]:
    """Normalise a unit cell. Returns (unit, repairs)."""
    if unit is None:
        return None, ()
    raw = str(unit).strip()
    if not raw:
        return None, ()
    fixed = _UNIT_FIXES.get(raw)
    if fixed and fixed != raw:
        return fixed, (f"unit {raw!r} -> {fixed!r}",)
    return raw, ()


# ── Plausibility gates ───────────────────────────────────────────────────────

#: Absolute sanity band for an Ethiopian unit rate in ETB. Outside this, the
#: row is a parsing failure rather than an expensive item.
MIN_PLAUSIBLE_ETB = Decimal("1")
MAX_PLAUSIBLE_ETB = Decimal("5000000")

#: Materials sold by the cubic metre, priced per m², are a classic Ethiopian
#: BoQ mix-up and also the signature of an OCR'd unit column.
CUBIC_MATERIAL_HINTS = ("concrete", "mortar", "excavation", "masonry", "backfill")


def check_plausible(value: Decimal, unit: str | None, description: str = "") -> tuple[str, ...]:
    """Return a list of plausibility problems (empty when the row looks sane)."""
    problems: list[str] = []
    if value <= 0:
        problems.append("non-positive amount")
    elif value < MIN_PLAUSIBLE_ETB:
        problems.append(f"amount {value} is implausibly small")
    elif value > MAX_PLAUSIBLE_ETB:
        problems.append(f"amount {value} exceeds plausibility ceiling")

    desc_lower = (description or "").lower()
    if unit == "m²" and any(h in desc_lower for h in ("lean concrete", "mass concrete")):
        # Lean/mass concrete is a volume; a per-m² price hides the thickness.
        problems.append("concrete measured per m² — verify thickness basis")
    return tuple(problems)
