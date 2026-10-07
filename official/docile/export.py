"""DeepRead results -> DocILE KILE predictions (docile_evaluate --task KILE).

usage: python docile/export.py RAW_DIR OUT.json
  RAW_DIR  one <docid>.json per document, from common/run_deepread.py

Mapping:
  - one prediction per located field box; a value printed over several lines
    gets one box around all of it
  - bbox: DeepRead field_bboxes[].field_locations[].bbox_normalized is
    [top, left, bottom, right] on 0-1000; DocILE wants [left, top, right, bottom] on 0-1
  - page: page_number - 1
  - score: the box's confidence, halved when the field is flagged for review
  - text: the extracted value; "a | b" multi-values are matched to boxes in order
  - currency_code_amount_due: DocILE labels the printed symbol ("$"); when the
    amount is printed with a symbol, the currency box is that first character
Fields with a value but no located box are not exported (KILE needs a location).
"""
import json, sys
from pathlib import Path

RAW, OUT_FILE = sys.argv[1], sys.argv[2]

preds, stats = {}, {"docs": 0, "no_preview": 0, "fields_with_value": 0, "fields_located": 0, "boxes": 0}
if True:
    for path in sorted(Path(RAW).glob("*.json")):
        docid = path.stem
        result = json.load(open(path))
        if "data" not in result:  # a failed job: no predictions for this document
            stats["no_preview"] += 1
            preds[docid] = []
            continue
        stats["docs"] += 1
        data = result.get("data") or {}
        boxes: dict[str, list[tuple[int, list[float], float]]] = {}
        for page in result.get("field_bboxes") or []:
            for loc in page.get("field_locations") or []:
                if not loc.get("found") or not loc.get("bbox_normalized"):
                    continue
                top, left, bottom, right = loc["bbox_normalized"]
                boxes.setdefault(loc["field_name"], []).append(
                    (page["page_number"] - 1, [left / 1000, top / 1000, right / 1000, bottom / 1000],
                     float(loc.get("confidence") or 1.0)))
        out = []
        # Currency: DocILE labels the printed symbol ("$"), usually the first
        # character of the amount; place the currency box on that character.
        cur = data.get("currency_code_amount_due")
        if isinstance(cur, dict) and cur.get("value") and "currency_code_amount_due" not in boxes:
            for amount_field in ("amount_due", "amount_total_gross", "amount_total_net"):
                item = data.get(amount_field)
                text = str(item.get("value") if isinstance(item, dict) else item or "")
                if boxes.get(amount_field) and text[:1] in "$€£":
                    page_idx, (l, t, r, b), conf = boxes[amount_field][0]
                    w = (r - l) / max(len(text), 1)
                    boxes["currency_code_amount_due"] = [(page_idx, [l, t, l + w, b], conf)]
                    break
        for field, item in data.items():
            value = item.get("value") if isinstance(item, dict) else item
            if value in (None, "", []):
                continue
            stats["fields_with_value"] += 1
            located = boxes.get(field, [])
            if not located and field == "currency_code_amount_due":
                located = boxes.get(field, [])
            if not located:
                continue
            stats["fields_located"] += 1
            parts = [p.strip() for p in str(value).split(" | ")] if " | " in str(value) else [str(value)]
            penalty = 0.5 if isinstance(item, dict) and item.get("hil_flag") else 1.0
            if len(parts) == 1 and len(located) > 1:
                # One value split over several lines: DocILE draws ONE box around
                # the whole value, so merge its parts per page.
                merged: dict[int, tuple[list[float], float]] = {}
                for page_idx, (l, t, r, b), conf in located:
                    if page_idx in merged:
                        (ml, mt, mr, mb), mc = merged[page_idx]
                        merged[page_idx] = ([min(ml, l), min(mt, t), max(mr, r), max(mb, b)], min(mc, conf))
                    else:
                        merged[page_idx] = ([l, t, r, b], conf)
                located = [(pg, bb, cf) for pg, (bb, cf) in merged.items()]
            for i, (page_idx, bbox, conf) in enumerate(located):
                out.append({"page": page_idx, "bbox": bbox, "fieldtype": field,
                            "score": round(conf * penalty, 4), "text": parts[min(i, len(parts) - 1)]})
                stats["boxes"] += 1
        preds[docid] = out

json.dump(preds, open(OUT_FILE, "w"))
print(json.dumps(stats))
