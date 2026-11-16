# -*- coding: utf-8 -*-
"""Sync master Excel files (Targets, Booster Participants/AE, Booster Ink SKUs)
into data/*.csv and data/program_rules.json, then regenerate data/epr_data.json.
"""
import csv
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile

import export_from_db


def _col_idx(ref):
    m = re.match(r"([A-Z]+)", (ref or "").upper())
    if not m:
        return 0
    idx = 0
    for ch in m.group(1):
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def read_xlsx_rows(path):
    """Return list of row lists (dense, 0-based columns) from the first worksheet."""
    with zipfile.ZipFile(path) as z:
        ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        ss = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ss = ["".join(si.itertext()) for si in root.findall("a:si", ns)]

        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in z.namelist():
            sheets = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
            if not sheets:
                raise ValueError("Worksheet tidak ditemukan di file Excel.")
            sheet_name = sheets[0]

        ws = ET.fromstring(z.read(sheet_name))
        out = []
        for row in ws.findall(".//a:row", ns):
            cells = {}
            max_col = -1
            for c in row.findall("a:c", ns):
                ci = _col_idx(c.attrib.get("r", ""))
                max_col = max(max_col, ci)
                t = c.attrib.get("t")
                v = c.find("a:v", ns)
                is_el = c.find("a:is", ns)
                if is_el is not None:
                    val = "".join(is_el.itertext())
                elif v is None:
                    val = ""
                elif t == "s":
                    val = ss[int(v.text)]
                else:
                    val = v.text or ""
                cells[ci] = str(val).strip()
            if max_col >= 0:
                arr = [cells.get(i, "") for i in range(max_col + 1)]
                if any(x != "" for x in arr):
                    out.append(arr)
        return out


def _num_str(val, default=0):
    s = str(val or "").replace(",", "").strip()
    if not s:
        return str(default)
    return str(round(float(s)))


def sync_targets(xlsx_path, tool_dir):
    rows = read_xlsx_rows(xlsx_path)
    hdr_idx = None
    for i, r in enumerate(rows[:10]):
        up = [x.upper() for x in r]
        if "EPR CODE" in up and ("CATEGORY TARGET" in up or "TARGET EXCL" in up or "ORIGINAL TARGET" in up):
            hdr_idx = i
            break
    if hdr_idx is None:
        raise ValueError("Header 'EPR CODE' / 'CATEGORY TARGET' tidak ditemukan di file Target.")

    hdr = [x.upper() for x in rows[hdr_idx]]
    sub = [x.upper() for x in rows[hdr_idx + 1]] if hdr_idx + 1 < len(rows) else []
    has_sub = any("H1" in x or "H2" in x for x in sub)
    start_row = hdr_idx + (2 if has_sub else 1)

    def _find(names):
        for nm in names:
            if nm in hdr:
                return hdr.index(nm)
        return None

    c_code = _find(["EPR CODE"])
    c_name = _find(["EPR NAME"])
    c_city = _find(["CITY"])
    c_orig = _find(["ORIGINAL TARGET", "TARGET ORIGINAL"])
    c_cat_tgt = _find(["CATEGORY TARGET", "TARGET EXCL"])
    c_cat = _find(["CATEGORY"])
    c_am = _find(["AM", "AE"])

    c_cat_h1 = None
    c_cat_h2 = None
    if has_sub and c_cat_tgt is not None:
        # Find H1/H2 columns belonging to CATEGORY TARGET (usually last two H1/H2 columns)
        h1_cols = [i for i, x in enumerate(sub) if x.startswith("H1")]
        h2_cols = [i for i, x in enumerate(sub) if x.startswith("H2")]
        if h1_cols:
            c_cat_h1 = h1_cols[-1]
        if h2_cols:
            c_cat_h2 = h2_cols[-1]

    master_path = os.path.join(tool_dir, "data", "epr_master.csv")
    existing = {}
    if os.path.exists(master_path):
        with open(master_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                existing[(r.get("EPR CODE") or "").strip().upper()] = r

    rows_out = []
    for r in rows[start_row:]:
        code = (r[c_code] if c_code is not None and c_code < len(r) else "").strip().upper()
        if not code:
            continue
        name = (r[c_name] if c_name is not None and c_name < len(r) else "").strip()
        city = (r[c_city] if c_city is not None and c_city < len(r) else "").strip()
        orig_excl = _num_str(r[c_orig] if c_orig is not None and c_orig < len(r) else 0)
        cat_tgt = _num_str(r[c_cat_tgt] if c_cat_tgt is not None and c_cat_tgt < len(r) else orig_excl)
        cat = (r[c_cat] if c_cat is not None and c_cat < len(r) else "").strip()
        cat_h1 = _num_str(
            r[c_cat_h1] if c_cat_h1 is not None and c_cat_h1 < len(r) else round(float(cat_tgt) * 0.5)
        )
        cat_h2 = _num_str(
            r[c_cat_h2] if c_cat_h2 is not None and c_cat_h2 < len(r) else round(float(cat_tgt) * 0.5)
        )
        am_in = (r[c_am] if c_am is not None and c_am < len(r) else "").strip()
        am = am_in or (existing.get(code, {}).get("AM") or "ARIS").strip() or "ARIS"
        rows_out.append({
            "EPR CODE": code,
            "EPR NAME": name,
            "CITY": city,
            "TARGET EXCL": cat_tgt,
            "CATEGORY": cat,
            "AM": am,
            "TARGET ORIGINAL": orig_excl,
            "TARGET CAT H1": cat_h1,
            "TARGET CAT H2": cat_h2,
        })

    if not rows_out:
        raise ValueError("Tidak ada baris EPR yang valid di file Target.")

    fieldnames = [
        "EPR CODE", "EPR NAME", "CITY", "TARGET EXCL",
        "CATEGORY", "AM", "TARGET ORIGINAL", "TARGET CAT H1", "TARGET CAT H2",
    ]
    with open(master_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    export_from_db.export_data(tool_dir=tool_dir, out_path=os.path.join(tool_dir, "data", "epr_data.json"))
    return {"updated": len(rows_out), "message": f"Target EPR diperbarui: {len(rows_out)} partner."}


def sync_booster_participants(xlsx_path, tool_dir):
    rows = read_xlsx_rows(xlsx_path)
    hdr_idx = None
    for i, r in enumerate(rows[:10]):
        up = [x.upper() for x in r]
        if "EPR CODE" in up and "PACK NAME" in up:
            hdr_idx = i
            break
    if hdr_idx is None:
        raise ValueError("Header 'EPR CODE' dan 'PACK NAME' tidak ditemukan di file Peserta Booster.")

    hdr = [x.upper() for x in rows[hdr_idx]]

    def _find(names):
        for nm in names:
            if nm in hdr:
                return hdr.index(nm)
        return None

    c_code = _find(["EPR CODE"])
    c_name = _find(["EPR NAME"])
    c_area = _find(["AREA"])
    c_city = _find(["CITY"])
    c_cat = _find(["FY26 TARGET CATOGORY", "FY26 TARGET CATEGORY", "CATEGORY"])
    c_pack = _find(["PACK NAME"])
    c_ae = _find(["AE", "AM"])

    peserta_path = os.path.join(tool_dir, "data", "peserta_booster.csv")
    merged = {}
    order = []
    if os.path.exists(peserta_path):
        with open(peserta_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                ec = (r.get("EPR CODE") or "").strip().upper()
                if not ec:
                    continue
                merged[ec] = {
                    "EPR CODE": ec,
                    "EPR NAME": (r.get("EPR NAME") or "").strip(),
                    "AREA": (r.get("AREA") or "JATENG").strip() or "JATENG",
                    "CITY": (r.get("CITY") or "").strip(),
                    "FY26 TARGET CATEGORY": (r.get("FY26 TARGET CATEGORY") or "").strip(),
                    "PACK NAME": (r.get("PACK NAME") or "").strip(),
                    "AE": (r.get("AE") or "ARIS").strip() or "ARIS",
                }
                order.append(ec)

    upserted = 0
    for r in rows[hdr_idx + 1:]:
        ec = (r[c_code] if c_code is not None and c_code < len(r) else "").strip().upper()
        pack = (r[c_pack] if c_pack is not None and c_pack < len(r) else "").strip()
        if not ec or not pack:
            continue
        prev = merged.get(ec, {})
        ae_val = (r[c_ae] if c_ae is not None and c_ae < len(r) else "").strip()
        merged[ec] = {
            "EPR CODE": ec,
            "EPR NAME": (r[c_name] if c_name is not None and c_name < len(r) else prev.get("EPR NAME", "")).strip(),
            "AREA": (r[c_area] if c_area is not None and c_area < len(r) else prev.get("AREA", "JATENG")).strip() or "JATENG",
            "CITY": (r[c_city] if c_city is not None and c_city < len(r) else prev.get("CITY", "")).strip(),
            "FY26 TARGET CATEGORY": (r[c_cat] if c_cat is not None and c_cat < len(r) else prev.get("FY26 TARGET CATEGORY", "")).strip(),
            "PACK NAME": pack,
            "AE": ae_val or prev.get("AE", "ARIS") or "ARIS",
        }
        if ec not in order:
            order.append(ec)
        upserted += 1

    if upserted == 0:
        raise ValueError("Tidak ada baris peserta Booster yang valid ditemukan.")

    fieldnames = ["EPR CODE", "EPR NAME", "AREA", "CITY", "FY26 TARGET CATEGORY", "PACK NAME", "AE"]
    rows_out = [merged[ec] for ec in order]
    with open(peserta_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    rules_path = os.path.join(tool_dir, "data", "program_rules.json")
    if os.path.exists(rules_path):
        with open(rules_path, encoding="utf-8") as rf:
            rules = json.load(rf)
        if "Q3 Booster Up" in rules:
            parts = {}
            for rr in rows_out:
                pk = rr["PACK NAME"]
                parts[rr["EPR CODE"]] = {
                    "scheme": "consumables" if "CONSUMABLES" in pk.upper() else "unit_ink",
                    "pkg": pk.split()[0].upper(),
                    "pack_name": pk,
                    "fy_cat": rr["FY26 TARGET CATEGORY"],
                    "ae": rr["AE"],
                }
            rules["Q3 Booster Up"]["participants"] = parts
            with open(rules_path, "w", encoding="utf-8") as wf:
                json.dump(rules, wf, ensure_ascii=False, indent=2)

    export_from_db.export_data(tool_dir=tool_dir, out_path=os.path.join(tool_dir, "data", "epr_data.json"))
    return {
        "upserted": upserted,
        "total": len(rows_out),
        "message": f"Peserta Booster diperbarui: {upserted} baris diproses (total {len(rows_out)} EPR).",
    }


def sync_booster_skus(xlsx_path, tool_dir):
    rows = read_xlsx_rows(xlsx_path)
    hdr_idx = None
    for i, r in enumerate(rows[:10]):
        up = [x.upper() for x in r]
        if "MATERIAL CODE" in up and "TYPE" in up:
            hdr_idx = i
            break
    if hdr_idx is None:
        raise ValueError("Header 'Material Code' dan 'Type' tidak ditemukan di file SKU Tinta.")

    hdr = [x.upper() for x in rows[hdr_idx]]
    c_mat = hdr.index("MATERIAL CODE")
    c_desc = hdr.index("DESCRIPTION") if "DESCRIPTION" in hdr else None
    c_type = hdr.index("TYPE")

    rows_out = []
    ink_list = []
    oth_list = []
    for r in rows[hdr_idx + 1:]:
        mc = (r[c_mat] if c_mat < len(r) else "").strip().upper()
        tp = (r[c_type] if c_type < len(r) else "").strip().upper()
        if not mc or not tp:
            continue
        desc = (r[c_desc] if c_desc is not None and c_desc < len(r) else "").strip()
        rows_out.append({"Material Code": mc, "Description": desc, "Type": tp})
        if tp == "INK BOTTLE":
            ink_list.append(mc)
        elif tp == "OTHERS INK BOTTLE":
            oth_list.append(mc)

    if not rows_out:
        raise ValueError("Tidak ada baris SKU tinta yang valid ditemukan.")

    sku_path = os.path.join(tool_dir, "data", "booster_consumables_sku.csv")
    with open(sku_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Material Code", "Description", "Type"])
        w.writeheader()
        w.writerows(rows_out)

    rules_path = os.path.join(tool_dir, "data", "program_rules.json")
    if os.path.exists(rules_path):
        with open(rules_path, encoding="utf-8") as rf:
            rules = json.load(rf)
        if "Q3 Booster Up" in rules:
            rules["Q3 Booster Up"]["ink_bottle_skus"] = ink_list
            rules["Q3 Booster Up"]["other_ink_skus"] = oth_list
            with open(rules_path, "w", encoding="utf-8") as wf:
                json.dump(rules, wf, ensure_ascii=False, indent=2)

    export_from_db.export_data(tool_dir=tool_dir, out_path=os.path.join(tool_dir, "data", "epr_data.json"))
    return {
        "total": len(rows_out),
        "ink_bottle": len(ink_list),
        "other_ink": len(oth_list),
        "message": f"SKU Tinta Booster diperbarui: {len(rows_out)} SKU ({len(ink_list)} INK BOTTLE, {len(oth_list)} OTHERS).",
    }


def refresh_export(tool_dir):
    export_from_db.export_data(tool_dir=tool_dir, out_path=os.path.join(tool_dir, "data", "epr_data.json"))
    return {"message": "Dashboard berhasil di-refresh dari database & master terbaru."}
