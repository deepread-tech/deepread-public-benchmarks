"""DeepRead results -> Kleister-Charity dev-0/out.tsv (GEval input).

usage: python kleister_charity/export.py RAW_DIR KLEISTER_REPO OUT_DIR
  RAW_DIR        one <name>.json per document (name = the PDF's file name), from common/run_deepread.py
  KLEISTER_REPO  a clone of github.com/applicaai/kleister-charity (for dev-0 document order)
  OUT_DIR/dev-0/out.tsv

Normalisation, as the Kleister README specifies: spaces -> "_", dates YYYY-MM-DD,
money as a number with two decimals. Empty values are omitted.
"""
import json, lzma, os, re, sys
from datetime import date
from pathlib import Path

RAW, KLEISTER, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(f"{OUT}/dev-0", exist_ok=True)
order = [l.split("\t")[0] for l in lzma.open(f"{KLEISTER}/dev-0/in.tsv.xz", "rt") if l.strip()]

MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


def iso_date(v: str) -> str | None:
    s = str(v).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)  # UK documents: day first
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*\.?,?\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def money(v) -> str | None:
    if isinstance(v, int | float) and not isinstance(v, bool):
        return f"{float(v):.2f}"
    s = re.sub(r"[£,\s]", "", str(v))
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        x = float(s)
    except ValueError:
        return None
    return f"{-x if neg else x:.2f}"


def norm(field: str, value) -> str | None:
    if value in (None, "", []):
        return None
    if "date" in field:
        out = iso_date(value)
    elif field.endswith("_in_british_pounds"):
        out = money(value)
    else:
        out = " ".join(str(value).split())
    return out.replace(" ", "_") if out else None



missing, lines = 0, []
for name in order:
    path = Path(RAW) / f"{name.removesuffix('.pdf')}.json"
    if not path.exists() and (alt := Path(RAW) / f"{name}.json").exists():
        path = alt
    result = json.load(open(path)) if path.exists() else {}
    data = result.get("data") or {}
    if not data:
        missing += 1
    pairs = []
    for field, item in sorted(data.items()):
        v = norm(field, item.get("value") if isinstance(item, dict) else item)
        if v:
            pairs.append(f"{field}={v}")
    lines.append(" ".join(pairs))

open(f"{OUT}/dev-0/out.tsv", "w").write("\n".join(lines) + "\n")
print(json.dumps({"docs": len(order), "missing": missing}))
