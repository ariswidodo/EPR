# -*- coding: utf-8 -*-
"""Export verified EPR achievement data from EPR_Tool (epr.db + epr_master.csv)
into data/epr_data.json for the EPR Dashboard.
"""
import csv
import datetime
import json
import os
import re
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

    epp_master_path = os.path.join(tool_dir, "data", "epp_master.csv")
    epp_names = {}
    epp_cities = {}
    if os.path.exists(epp_master_path):
        with open(epp_master_path, encoding="utf-8-sig") as f:
            for er in csv.DictReader(f):
                ec = (er.get("EPP CODE") or "").strip()
                en = (er.get("COMPANY NAME") or er.get("NAMA TOKO") or "").strip()
                ect = (er.get("CITY") or "").strip()
                if ec and en and ec not in epp_names:
                    epp_names[ec] = en
                if ec and ect and ec not in epp_cities:
                    epp_cities[ec] = ect

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT epr, epp, epp_name, kat, month_ser, qty, price, total, eim, quarter, remarks, invoice_date, material, description, flag FROM terverifikasi"
    ).fetchall()
    last_proc = con.execute(
        "SELECT waktu, file FROM proses ORDER BY id DESC LIMIT 1"
    ).fetchone()
    proc_logs = [
        dict(r) for r in con.execute(
            "SELECT waktu, file, baris_input, masuk, double, luar_db, nilai "
            "FROM proses ORDER BY id DESC LIMIT 15"
        ).fetchall()
    ]
    rej_rows = con.execute(
        "SELECT keterangan, COUNT(1) AS cnt FROM data_per_q WHERE is_verified = 0 GROUP BY keterangan"
    ).fetchall()
    double_existing = 0
    double_in_file = 0
    luar_db = 0
    for rr in rej_rows:
        ket = (rr["keterangan"] or "").strip()
        if ket.startswith("SUDAH TERVERIFIKASI"):
            double_existing += rr["cnt"]
        elif ket == "KEMBAR DALAM INPUT":
            double_in_file += rr["cnt"]
        elif ket == "LUAR DATABASE EPR":
            luar_db += rr["cnt"]

    recent_rejected = [
        dict(r) for r in con.execute(
            "SELECT invoice_date, invoice_no, epr, epr_name, material, qty, total, keterangan, sumber_file, baris_sumber, "
            "CASE WHEN keterangan = 'LUAR DATABASE EPR' THEN 'luar_db' ELSE 'double' END AS jenis "
            "FROM data_per_q WHERE is_verified = 0 "
            "ORDER BY CASE WHEN keterangan = 'LUAR DATABASE EPR' THEN 1 ELSE 0 END, diproses_pada DESC, baris_sumber ASC LIMIT 500"
        ).fetchall()
    ]
    con.close()

    def _extract_program(rem_text):
        parts = [x.strip() for x in (rem_text or "").split("|")]
        ad_raw = ""
        if len(parts) >= 4 and parts[-1].lower().startswith("src "):
            ad_raw = " | ".join(parts[2:-1]).strip()
        ad_raw = ad_raw.strip().strip('"\'“”‘’').strip()
        if not ad_raw:
            return "Reguler (Tanpa Program)"
        m = re.match(r"^EIN-(\d{2})-(\d+)$", ad_raw, re.I)
        if m:
            return f"EIN-{m.group(1)}-{m.group(2).zfill(6)}"
        if re.match(r"^q3\s+booster(\s+up)?$", ad_raw, re.I):
            return "Q3 Booster Up"
        return ad_raw

    agg = defaultdict(lambda: defaultdict(float))
    midhi = defaultdict(float)
    row_count = defaultdict(int)
    qty_sum = defaultdict(float)
    epp_agg = defaultdict(lambda: defaultdict(lambda: {"total": 0.0, "tx": 0, "name": "", "cats": defaultdict(float)}))
    global_epp = defaultdict(lambda: {"total": 0.0, "tx": 0, "name": "", "cats": defaultdict(float)})
    prog_agg = defaultdict(lambda: defaultdict(lambda: {"total": 0.0, "tx": 0, "qty": 0.0, "cats": defaultdict(float)}))
    global_prog = defaultdict(float)
    prog_items_map = defaultdict(lambda: {"qty": 0.0, "net": 0.0, "tx": 0, "desc": "", "kat": "", "eim": ""})

    for r in rows:
        code = (r["epr"] or "").strip()
        kat = (r["kat"] or "").strip()
        mser = r["month_ser"]
        gross = r["total"] if (r["total"] is not None and r["total"] > 0) else ((r["price"] or 0.0) * (r["qty"] or 0.0))
        is_v3 = (r["flag"] or "").strip() == "Valid (V3)"
        net = gross if is_v3 else (gross / 1.11)
        agg[code][(kat, mser)] += net
        row_count[code] += 1
        qty_sum[code] += r["qty"] or 0.0
        if (r["eim"] or "").strip() == "Mid High":
            midhi[code] += net

        ep_code = (r["epp"] or "").strip() or (r["epp_name"] or "").strip() or "TIDAK DIKETAHUI"
        ep_name = epp_names.get(ep_code) or (r["epp_name"] or "").strip() or ep_code
        ea = epp_agg[code][ep_code]
        ea["total"] += net
        ea["tx"] += 1
        ea["name"] = ep_name
        if kat:
            ea["cats"][kat] += net

        ga = global_epp[ep_code]
        ga["total"] += net
        ga["tx"] += 1
        ga["name"] = ep_name
        if kat:
            ga["cats"][kat] += net

        prog_name = _extract_program(r["remarks"])
        pa = prog_agg[code][prog_name]
        pa["total"] += net
        pa["tx"] += 1
        pa["qty"] += r["qty"] or 0.0
        if kat:
            pa["cats"][kat] += net
        global_prog[prog_name] += net

        inv_date = (r["invoice_date"] or "").strip()
        mat = (r["material"] or "").strip()
        desc = (r["description"] or "").strip()
        pk = (code, prog_name, inv_date, mat)
        pi = prog_items_map[pk]
        pi["qty"] += r["qty"] or 0.0
        pi["net"] += net
        pi["tx"] += 1
        if desc and not pi["desc"]:
            pi["desc"] = desc
        if kat and not pi["kat"]:
            pi["kat"] = kat
        eim_val = (r["eim"] or "").strip()
        if eim_val and not pi["eim"]:
            pi["eim"] = eim_val

    partners = []
    seen_codes = set()
    for m in masters:
        code = (m.get("EPR CODE") or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        try:
            target_fy = float(m.get("TARGET EXCL") or 0)
        except ValueError:
            target_fy = 0.0
        try:
            target_original = float(m.get("TARGET ORIGINAL") or 0) or target_fy
        except ValueError:
            target_original = target_fy

        try:
            target_h1 = round(float(m.get("TARGET CAT H1") or 0)) or round(target_fy * 0.50)
        except ValueError:
            target_h1 = round(target_fy * 0.50)
        try:
            target_h2 = round(float(m.get("TARGET CAT H2") or 0)) or round(target_fy * 0.50)
        except ValueError:
            target_h2 = round(target_fy * 0.50)
        target_original_h1 = round(target_original * 0.52)
        target_original_h2 = round(target_original * 0.48)

        monthly_by_cat = {}
        cat_totals = {}
        for kat in CATS:
            arr = [round(agg[code].get((kat, mser), 0.0), 2) for mser in M12]
            monthly_by_cat[kat] = arr
            cat_totals[kat] = round(sum(arr), 2)

        monthly_total = [
            round(sum(monthly_by_cat[kat][i] for kat in CATS), 2)
            for i in range(len(M12))
        ]
        total_h1 = round(sum(monthly_total[:6]), 2)
        total_h2 = round(sum(monthly_total[6:]), 2)
        total_fy = round(sum(monthly_total), 2)
        mid_hi_val = round(midhi.get(code, 0.0), 2)
        low_end_val = round(max(0.0, total_fy - mid_hi_val), 2)

        epp_sources = [
            {
                "code": ec,
                "name": ev["name"],
                "city": epp_cities.get(ec, ""),
                "total": round(ev["total"], 2),
                "tx": ev["tx"],
                "cats": {k: round(ev["cats"].get(k, 0.0), 2) for k in CATS},
            }
            for ec, ev in sorted(epp_agg[code].items(), key=lambda kv: -kv[1]["total"])
        ]

        program_sources = [
            {
                "name": pn,
                "total": round(pv["total"], 2),
                "tx": pv["tx"],
                "qty": round(pv["qty"]),
                "cats": {k: round(pv["cats"].get(k, 0.0), 2) for k in CATS},
            }
            for pn, pv in sorted(prog_agg[code].items(), key=lambda kv: -kv[1]["total"])
        ]

        partners.append({
            "code": code,
            "name": (m.get("EPR NAME") or "").strip(),
            "city": (m.get("CITY") or "").strip(),
            "tier": (m.get("CATEGORY") or "").strip(),
            "am": (m.get("AM") or "").strip(),
            "target_fy": round(target_fy),
            "target_original": round(target_original),
            "target_original_h1": target_original_h1,
            "target_original_h2": target_original_h2,
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
            "epp_sources": epp_sources,
            "program_sources": program_sources,
        })

    epp_summary = [
        {
            "code": ec,
            "name": ev["name"],
            "city": epp_cities.get(ec, ""),
            "total": round(ev["total"], 2),
            "tx": ev["tx"],
            "cats": {k: round(ev["cats"].get(k, 0.0), 2) for k in CATS},
        }
        for ec, ev in sorted(global_epp.items(), key=lambda kv: -kv[1]["total"])
    ]

    rules_path = os.path.join(tool_dir, "data", "program_rules.json")
    program_rules = {}
    if os.path.exists(rules_path):
        try:
            with open(rules_path, encoding="utf-8") as rf:
                program_rules = json.load(rf)
        except Exception:
            program_rules = {}

    program_items = [
        {
            "epr": k[0],
            "prog": k[1],
            "date": k[2],
            "model": k[3],
            "desc": v["desc"],
            "kat": v["kat"],
            "eim": v["eim"],
            "qty": round(v["qty"]),
            "net": round(v["net"], 2),
            "tx": v["tx"],
        }
        for k, v in prog_items_map.items()
    ]

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
            "programs": [k for k, _ in sorted(global_prog.items(), key=lambda kv: -kv[1])],
            "program_rules": program_rules,
            "tax_note": "Semua nilai revenue exclude PPN 11% (dibagi 1.11)",
        },
        "audit": {
            "double_existing": double_existing,
            "double_in_file": double_in_file,
            "double_total": double_existing + double_in_file,
            "luar_db": luar_db,
            "rejected_total": double_existing + double_in_file + luar_db,
            "process_logs": proc_logs,
            "recent_rejected": recent_rejected,
        },
        "epp_summary": epp_summary,
        "program_items": program_items,
        "partners": partners,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(partners)} EPR partners ({len(rows)} verified rows) -> {out_path}")


if __name__ == "__main__":
    export_data()
