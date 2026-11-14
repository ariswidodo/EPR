# -*- coding: utf-8 -*-
"""Export verified EPR achievement data from EPR_Tool (epr.db + epr_master.csv)
into data/epr_data.json for the EPR Dashboard.
"""
import csv
import datetime
import json
import os
import sqlite3
from collections import defaultdict

DEFAULT_TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "epr_data.json",
)

M12 = [46113, 46143, 46174, 46204, 46235, 46266, 46296, 46327, 46357, 46388, 46419, 46447]
MLBL = ["Apr 26", "Mei 26", "Jun 26", "Jul 26", "Agu 26", "Sep 26",
        "Okt 26", "Nov 26", "Des 26", "Jan 27", "Feb 27", "Mar 27"]
CATS = ["Consumer", "Scanner", "Consumables", "Dotmatrix"]


def export_data(tool_dir=DEFAULT_TOOL_DIR, out_path=OUT_PATH):
    db_path = os.path.join(tool_dir, "data", "epr.db")
    master_path = os.path.join(tool_dir, "data", "epr_master.csv")

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    if not os.path.exists(master_path):
        raise FileNotFoundError(f"Master CSV not found: {master_path}")

    with open(master_path, encoding="utf-8-sig") as f:
        masters = list(csv.DictReader(f))

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT epr, kat, month_ser, qty, price, eim, quarter FROM terverifikasi"
    ).fetchall()
    last_proc = con.execute(
        "SELECT waktu, file FROM proses ORDER BY id DESC LIMIT 1"
    ).fetchone()
    con.close()

    agg = defaultdict(lambda: defaultdict(float))
    midhi = defaultdict(float)
    row_count = defaultdict(int)
    qty_sum = defaultdict(float)

    for r in rows:
        code = (r["epr"] or "").strip()
        kat = (r["kat"] or "").strip()
        mser = r["month_ser"]
        gross = (r["price"] or 0.0) * (r["qty"] or 0.0)
        agg[code][(kat, mser)] += gross
        row_count[code] += 1
        qty_sum[code] += r["qty"] or 0.0
        if (r["eim"] or "").strip() == "Mid High":
            midhi[code] += gross

    partners = []
    for m in masters:
        code = (m.get("EPR CODE") or "").strip()
        if not code:
            continue
        try:
            target_fy = float(m.get("TARGET EXCL") or 0)
        except ValueError:
            target_fy = 0.0

        target_h1 = round(target_fy * 0.52)
        target_h2 = round(target_fy * 0.48)

        monthly_by_cat = {}
        cat_totals = {}
        for kat in CATS:
            arr = [round(agg[code].get((kat, mser), 0.0) / 1.11, 2) for mser in M12]
            monthly_by_cat[kat] = arr
            cat_totals[kat] = round(sum(arr), 2)

        monthly_total = [
            round(sum(monthly_by_cat[kat][i] for kat in CATS), 2)
            for i in range(len(M12))
        ]
        total_h1 = round(sum(monthly_total[:6]), 2)
        total_h2 = round(sum(monthly_total[6:]), 2)
        total_fy = round(sum(monthly_total), 2)
        mid_hi_val = round(midhi.get(code, 0.0) / 1.11, 2)
        low_end_val = round(max(0.0, total_fy - mid_hi_val), 2)

        partners.append({
            "code": code,
            "name": (m.get("EPR NAME") or "").strip(),
            "city": (m.get("CITY") or "").strip(),
            "tier": (m.get("CATEGORY") or "").strip(),
            "am": (m.get("AM") or "").strip(),
            "target_fy": round(target_fy),
            "target_h1": target_h1,
            "target_h2": target_h2,
            "actual_fy": total_fy,
            "actual_h1": total_h1,
            "actual_h2": total_h2,
            "mid_hi": mid_hi_val,
            "low_end": low_end_val,
            "tx_count": row_count.get(code, 0),
            "qty_total": round(qty_sum.get(code, 0.0)),
            "cat_totals": cat_totals,
            "monthly_total": monthly_total,
            "monthly_by_cat": monthly_by_cat,
        })

    payload = {
        "meta": {
            "title": "EPR FY26 Achievement Dashboard",
            "fiscal_year": "FY26 (Apr 2026 - Mar 2027)",
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_source_file": last_proc["file"] if last_proc else "",
            "last_processed_at": last_proc["waktu"] if last_proc else "",
            "verified_rows": len(rows),
            "months": MLBL,
            "categories": CATS,
            "tax_note": "Semua nilai revenue exclude PPN 11% (dibagi 1.11)",
        },
        "partners": partners,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(partners)} EPR partners ({len(rows)} verified rows) -> {out_path}")


if __name__ == "__main__":
    export_data()
