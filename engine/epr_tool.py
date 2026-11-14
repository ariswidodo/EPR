# -*- coding: utf-8 -*-
"""Mesin proses EPR Sell In — dipakai oleh GUI (app.py) maupun CLI.

Membaca file Excel tanpa pustaka eksternal (zipfile + regex), jadi ringan
dan tidak memperberat laptop.
"""
import zipfile, re, io, os, csv, datetime, collections
from xml.sax.saxutils import escape, unescape

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUTD = os.path.join(BASE, "out")
TEMPLATE_Q = os.path.join(DATA, "template_q.xlsx")        # template Data Per Q
TEMPLATE_VER = os.path.join(DATA, "template_verified.xlsx")  # template Data terverifikasi
SKU_FILE = os.path.join(DATA, "sku.xlsx")             # master produk (dari SKU.xlsx)
EPR_CSV = os.path.join(DATA, "epr_master.csv")
EPP_CSV = os.path.join(DATA, "epp_master.csv")
for d in (DATA, OUTD):
    os.makedirs(d, exist_ok=True)

EPOCH = datetime.date(1899, 12, 30)
def ser(d): return (d - EPOCH).days

QUARTERS = {
 "Q1": "PERIODE: 1 Apr - 30 Jun 2026",
 "Q2": "PERIODE: 1 Jul - 30 Sep 2026 (Q2)",
 "Q3": "PERIODE: 1 Oct - 31 Dec 2026 (Q3)",
 "Q4": "PERIODE: 1 Jan - 31 Mar 2027 (Q4)",
}
def quarter_of(d):
    m = d.month
    if 4 <= m <= 6: return "Q1"
    if 7 <= m <= 9: return "Q2"
    if 10 <= m <= 12: return "Q3"
    return "Q4"

# ------------------------------------------------------------------ pembaca xlsx cepat
_ROW = re.compile(r'<row\b[^>]*\br="(\d+)"[^>]*>(.*?)</row>', re.S)
_CELL = re.compile(r'<c r="([A-Z]+)\d+"([^>]*)>(?:<v>([^<]*)</v>|<is><t[^>]*>(.*?)</t></is>)', re.S)
_V = re.compile(r'<v>(.*?)</v>', re.S)
_T = re.compile(r'<t[^>]*>(.*?)</t>', re.S)

def _col(ref):
    c = 0
    for ch in ref: c = c * 26 + (ord(ch) - 64)
    return c - 1

def sheet_names(path):
    z = zipfile.ZipFile(path)
    wb = z.read("xl/workbook.xml").decode("utf-8", "replace")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "replace")
    rel = {}
    for tag in re.findall(r"<Relationship\b[^>]*>", rels):
        i = re.search(r'Id="([^"]+)"', tag); t = re.search(r'Target="([^"]+)"', tag)
        if i and t: rel[i.group(1)] = t.group(1)
    out = []
    for tag in re.findall(r"<sheet\b[^>]*>", wb):
        nm = re.search(r'name="([^"]+)"', tag); rid = re.search(r'r:id="([^"]+)"', tag)
        if not (nm and rid): continue
        tgt = rel.get(rid.group(1), "")
        if not tgt.startswith("xl/"): tgt = "xl/" + tgt.lstrip("/")
        out.append((unescape(nm.group(1)), tgt))
    z.close()
    return out

def read_sheet(path, sheetname):
    """Kembalikan {row_number: {col_index: text}} — cepat, tanpa ElementTree."""
    z = zipfile.ZipFile(path)
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf-8", "replace"), re.S):
            sst.append(unescape("".join(_T.findall(si))))
    part = dict(sheet_names(path)).get(sheetname)
    if not part or part not in z.namelist():
        z.close(); return {}
    txt = z.read(part).decode("utf-8", "replace")
    z.close()
    rows = {}
    for rm in _ROW.finditer(txt):
        rn = int(rm.group(1)); body = rm.group(2); d = {}
        if not body: continue
        for cm in _CELL.finditer(body):
            attrs = cm.group(2) or ""
            v = cm.group(3)
            if v is None:
                v = unescape(cm.group(4) or "")
            elif 't="s"' in attrs and sst:
                v = sst[int(v)]
            else:
                v = unescape(v)
            d[_col(cm.group(1))] = v
        rows[rn] = d
    return rows

def read_pairs(path, sheetname):
    """Untuk sheet kecil; sama seperti read_sheet tetapi string index sudah dipetakan."""
    return read_sheet(path, sheetname)

# ------------------------------------------------------------------ normalisasi nama
def norm(s):
    t = re.sub(r"\s+", " ", (s or "")).upper().strip()
    t = re.sub(r"^(PT|CV|UD|PD|TB|KOPERASI)\s*[\.\s]*", "", t)
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    t = re.sub(r"\s+(CV|PT|UD)$", "", t)
    return re.sub(r"\s+", " ", t).strip()

def lev(a, b):
    if a == b: return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def same_entity(a, b):
    if a == b: return True
    if not a or not b: return False
    if a.replace(" ", "") == b.replace(" ", ""): return True
    # prefllter murah sebelum Levenshtein
    if a[0] != b[0]: return False
    if abs(len(a) - len(b)) > 2 or len(a) < 10: return False
    return lev(a, b) <= 1

# ------------------------------------------------------------------ database CSV
EPR_COLS = ["EPR CODE", "EPR NAME", "CITY", "TARGET EXCL", "CATEGORY", "AM"]
EPP_COLS = ["EPP CODE", "TERRITORY", "AREA", "CITY", "NAMA TOKO", "COMPANY NAME", "TYPE"]

def load_master(kind):
    path = EPR_CSV if kind == "epr" else EPP_CSV
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]

def save_master(kind, rows):
    path = EPR_CSV if kind == "epr" else EPP_CSV
    cols = EPR_COLS if kind == "epr" else EPP_COLS
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({c: r.get(c, "") for c in cols})

def parse_master_file(path, kind):
    """Baca file master (xlsx format Epson atau CSV) -> list dict."""
    ext = os.path.splitext(path)[1].lower()
    out = []
    if ext == ".csv":
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                out.append(r)
        return out
    sheets = dict(sheet_names(path))
    target = next((n for n in sheets if n.lower().startswith("sheet1")), None) or (list(sheets)[0] if sheets else None)
    rows = read_sheet(path, target)
    hdr_rn = min(rows) if rows else None
    if hdr_rn is None: return []
    hdr = rows[hdr_rn]
    # cari baris header yang memuat 'EPR CODE' / 'EPP CODE'
    key = "EPR CODE" if kind == "epr" else "EPP CODE"
    cand = [rn for rn in sorted(rows) if any(str(v).strip().upper() == key for v in rows[rn].values())]
    if not cand: return []
    hr = cand[0]; hdr = {k: str(v).strip().upper() for k, v in rows[hr].items()}
    def colof(name):
        for k, v in hdr.items():
            if v == name: return k
        return None
    C = {
        "code": colof(key),
        "name": colof("EPR NAME" if kind == "epr" else "NAMA TOKO"),
        "city": colof("CITY"),
        "cat": colof("CATEGORY"),
        "am": colof("AM"),
    }
    if kind == "epr":
        tg = colof("ORIGINAL TARGET")
        # kolom D = ORIGINAL TARGET (exclude tax); ambil yang pertama
        cand_t = [k for k, v in hdr.items() if v == "ORIGINAL TARGET"]
        C["target"] = sorted(cand_t)[0] if cand_t else None
    for rn in sorted(rows):
        if rn <= hr: continue
        d = rows[rn]
        def g(k):
            return str(d.get(k, "") or "").strip() if k is not None else ""
        if kind == "epr":
            rec = {"EPR CODE": g(C["code"]), "EPR NAME": g(C["name"]), "CITY": g(C["city"]),
                   "TARGET EXCL": g(C.get("target")), "CATEGORY": g(C["cat"]), "AM": g(C["am"])}
            if rec["EPR CODE"]: out.append(rec)
        else:
            cols_upper = {v: k for k, v in hdr.items()}
            def gc(name):
                k = cols_upper.get(name)
                return str(d.get(k, "") or "").strip() if k is not None else ""
            # company name = kolom F ('COMPANY NAME FY26')
            rec = {"EPP CODE": g(C["code"]), "TERRITORY": gc("TERRITORY"), "AREA": gc("AREA"),
                   "CITY": gc("CITY"), "NAMA TOKO": g(C["name"]),
                   "COMPANY NAME": "", "TYPE": ""}
            for name in ("COMPANY NAME FY26", "COMPANY NAME", "AREA"):
                if name in cols_upper and name != "AREA":
                    rec["COMPANY NAME"] = str(d.get(cols_upper[name], "") or "").strip()
                    break
            if rec["EPP CODE"]: out.append(rec)
    return out

def _mkey(kind, r):
    """EPR dikunci per (kode, nama) supaya alias nama untuk kode yang sama tetap tersimpan."""
    code = (r.get("EPR CODE" if kind == "epr" else "EPP CODE", "") or "").strip().upper()
    if kind == "epr":
        return code + "|" + norm(r.get("EPR NAME", ""))
    return code

def merge_master(kind, incoming):
    """Gabung: kunci baru ditambah, kunci lama diperbarui. Tidak ada yang dihapus."""
    cur = {_mkey(kind, r): r for r in load_master(kind) if _mkey(kind, r).strip("|")}
    added = updated = 0
    for r in incoming:
        k = _mkey(kind, r)
        if not k.strip("|"): continue
        if k in cur:
            if any(r.get(c) and r.get(c) != cur[k].get(c) for c in r):
                updated += 1
            cur[k].update({c: v for c, v in r.items() if v})
        else:
            cur[k] = r; added += 1
    rows = [cur[k] for k in sorted(cur)]
    save_master(kind, rows)
    return added, updated, len(rows)

def import_sku(path):
    """Baca master produk dari file SKU (sheet 'Product FY26')."""
    rows = read_sheet(path, "Product FY26")
    if not rows:
        names = [n for n, _ in sheet_names(path)]
        target = "Product FY26" if "Product FY26" in names else (names[0] if names else None)
        rows = read_sheet(path, target) if target else {}
    if not rows: return []
    first = min(rows)
    out = []
    for rn in sorted(rows):
        if rn == first: continue
        d = rows[rn]
        model = str(d.get(0, "") or "").strip()
        if not model: continue
        out.append((model,
                    str(d.get(1, "") or "").strip(),
                    str(d.get(2, "") or "").strip(),
                    str(d.get(3, "") or "").strip(),
                    str(d.get(4, "") or "").strip(),
                    str(d.get(5, "") or "").strip()))
    return out


# ------------------------------------------------------------------ deteksi versi input
INPUT_SHEETS = ("Sheet1", "Partner Hub", "Report Retail Q1", "Report Retail Q2", "Report Retail Q3", "Report Retail Q4")

def find_header_row(rows):
    """Cari baris header (baris 1..15) yang memuat 'Material Code' dan 'Invoice Date'."""
    for rn in sorted(rows)[:15]:
        vals = {str(v).strip() for v in rows[rn].values()}
        if "Material Code" in vals and "Invoice Date" in vals:
            return rn
    return min(rows) if rows else None

def detect_input_sheets(path):
    """Kembalikan daftar semua sheet data input yang valid (mendukung V1, V2, V3)."""
    names = [n for n, _ in sheet_names(path)]
    if "Sheet1" in names:
        return ["Sheet1"]
    if "Partner Hub" in names:
        return ["Partner Hub"]
    v3_sheets = [n for n in names if n.startswith("Report Retail Q")]
    if v3_sheets:
        return v3_sheets
    found = []
    for nm in names:
        if nm.upper() in ("CATATAN", "SUMMARY"):
            continue
        try:
            rows = read_sheet(path, nm)
        except Exception:
            continue
        if not rows:
            continue
        hr = find_header_row(rows)
        vals = {str(v).strip() for v in rows[hr].values()}
        if "Material Code" in vals and "Invoice Date" in vals:
            found.append(nm)
    return found or ([names[0]] if names else [])

def detect_input_sheet(path):
    """Cari sheet data input utama: V1 = 'Sheet1', V2 = 'Partner Hub', V3 = 'Report Retail Q*'."""
    shs = detect_input_sheets(path)
    return shs[0] if shs else None


def input_version(path, sheetname):
    if sheetname == "Partner Hub": return "V2"
    if sheetname == "Sheet1": return "V1"
    if str(sheetname).startswith("Report Retail"): return "V3"
    return "V3"


def parse_inv_date(s):
    """Terima teks 'dd-mm-yyyy' (V1) maupun serial Excel (V2)."""
    s = str(s or "").strip()
    if not s: return None
    if re.fullmatch(r"\d{5}(\.0+)?", s):
        try:
            return EPOCH + datetime.timedelta(days=int(float(s)))
        except (ValueError, OverflowError):
            return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %B %Y", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None
