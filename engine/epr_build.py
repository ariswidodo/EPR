# -*- coding: utf-8 -*-
"""Proses EPR Sell In -> DUA workbook sesuai template Anda:

  1. "Data Per Q"         <- template Data Per Q.xlsx  (sheet Report Retail Q1..Q4)
  2. "Data terverifikasi" <- template Data terverifikasi.xlsx (sheet RETAIL, 12 bulan + H1/H2)

Sumber: 3 database (SKU, Data Per Q, Data terverifikasi) di data/epr.db
"""
import zipfile, re, os, time, datetime, collections, json
from xml.sax.saxutils import escape
import epr_tool as T
import epr_db as D

def _num(v):
    if isinstance(v, int): return str(v)
    if v == int(v): return str(int(v))
    return f"{v:.4f}".rstrip("0").rstrip(".")

def _cn(k):
    s = ""; n = k + 1
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s

def c_str(ref, st, v):
    if v is None or v == "": return ""
    return f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'
def c_num(ref, st, v):
    if v is None or v == "": return ""
    return f'<c r="{ref}"{st}><v>{_num(v)}</v></c>'
def c_f(ref, st, fml, cached):
    s = f'<c r="{ref}"{st}><f>{escape(fml)}</f>'
    if cached not in (None, ""): s += f'<v>{_num(cached)}</v>'
    return s + "</c>"
def c_fs(ref, st, fml, cached):
    s = f'<c r="{ref}"{st} t="str"><f>{escape(fml)}</f>'
    if cached: s += f'<v>{escape(str(cached))}</v>'
    return s + "</c>"

def kategori(cat):
    t = (cat or "").strip().upper()
    if not t: return ""
    if t in ("CONSUMABLES", "CONSUMER", "SCANNER", "DOTMATRIX"):
        return t.capitalize()
    if t.endswith("CONS"): return "Consumables"
    if t.startswith("SCN"): return "Scanner"
    if t.startswith("SIDM"): return "Dotmatrix"
    if t.startswith("CISS") or t.startswith("SOHO"): return "Consumer"
    return ""
STATUS_MAP = {"Approved": "HITUNG", "Uploaded": "HITUNG",
              "Pending Approval": "PENDING", "Expired": "EXPIRED", "Rejected": "REJECTED"}
QUARTERS = ("Q1", "Q2", "Q3", "Q4")
QPERIOD = {"Q1": "PERIODE: 1 Apr - 30 Jun 2026", "Q2": "PERIODE: 1 Jul - 30 Sep 2026",
           "Q3": "PERIODE: 1 Oct - 31 Dec 2026", "Q4": "PERIODE: 1 Jan - 31 Mar 2027"}
M12 = [46113, 46143, 46174, 46204, 46235, 46266, 46296, 46327, 46357, 46388, 46419, 46447]
MLBL = ["Apr 26", "Mei 26", "Jun 26", "Jul 26", "Agu 26", "Sep 26",
        "Okt 26", "Nov 26", "Des 26", "Jan 27", "Feb 27", "Mar 27"]
BLK = {"Consumer": 13, "Scanner": 26, "Consumables": 39, "Dotmatrix": 52}
C_GT, C_H1, C_H2, C_A1, C_A2, C_AF, C_MID, C_LOW = 65, 66, 67, 68, 69, 70, 71, 72



def _fix_cols(xml, ncols, default_w=12.5):
    """Tampilkan semua kolom 1..ncols: buang hidden, pertahankan lebar template."""
    m = re.search(r"<cols>(.*?)</cols>", xml, re.S)
    widths = {}
    if m:
        for c in re.findall(r"<col [^>]*/>", m.group(1)):
            mn = re.search(r'min="(\d+)"', c); mx = re.search(r'max="(\d+)"', c)
            if not (mn and mx): continue
            wq = re.search(r'width="([\d.]+)"', c)
            w = float(wq.group(1)) if wq else default_w
            for i in range(int(mn.group(1)), int(mx.group(1)) + 1):
                widths[i] = w
    out = "".join(f'<col min="{i}" max="{i}" width="{widths.get(i, default_w):.2f}" customWidth="1"/>'
                  for i in range(1, ncols + 1))
    newcols = f"<cols>{out}</cols>"
    if m:
        return xml.replace(m.group(0), newcols, 1)
    return xml.replace("<sheetData>", newcols + "<sheetData>", 1)

# ------------------------------------------------------------------ paket xlsx
class Pkg:
    def __init__(self, path):
        z = zipfile.ZipFile(path)
        self.parts = {n: z.read(n) for n in z.namelist()}
        z.close()
        self.name = os.path.basename(path)

    def sheets(self):
        wb = self.parts["xl/workbook.xml"].decode("utf-8")
        rels = self.parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
        rid2t = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
        out = []
        for tag in re.findall(r"<sheet [^>]*/>", wb):
            nm = re.search(r'name="([^"]+)"', tag).group(1)
            rid = re.search(r'r:id="([^"]+)"', tag).group(1)
            tgt = rid2t.get(rid, "")
            if not tgt.startswith("xl/"): tgt = "xl/" + tgt.lstrip("/")
            out.append((nm, tgt, rid))
        return out

    def part_of(self, sheetname):
        for nm, p, rid in self.sheets():
            if nm == sheetname: return p
        raise KeyError(f"sheet {sheetname} tidak ada di {self.name}")

    def rows_xml(self, part):
        xml = self.parts[part].decode("utf-8", "replace")
        m = re.search(r"<sheetData>(.*)</sheetData>", xml, re.S)
        by = {}
        for rx in re.findall(r"<row[^>]*>.*?</row>|<row[^>]*/>", m.group(1), re.S):
            mm = re.match(r"<row[^>]*\br=\"(\d+)\"", rx)
            if mm: by[int(mm.group(1))] = rx
        return xml, by

    def write_sheet(self, part, xml, dim, merge_xml=None):
        x = re.sub(r'<dimension ref="[^"]*"', f'<dimension ref="{dim}"', xml, count=1)
        if merge_xml is not None:
            if re.search(r"<mergeCells.*?</mergeCells>", x, re.S):
                x = re.sub(r"<mergeCells.*?</mergeCells>", merge_xml, x, flags=re.S)
            else:
                x = x.replace("</sheetData>", "</sheetData>" + merge_xml, 1)
        self.parts[part] = x.encode("utf-8")

    def drop_sheet(self, sheetname):
        wb = self.parts["xl/workbook.xml"].decode("utf-8")
        rels = self.parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
        ct = self.parts["[Content_Types].xml"].decode("utf-8")
        for nm, p, rid in self.sheets():
            if nm != sheetname: continue
            wb = re.sub(r'<sheet [^>]*name="%s"[^>]*/>' % re.escape(sheetname), "", wb)
            rels = re.sub(r'<Relationship Id="%s"[^>]*/>' % rid, "", rels)
            ct = re.sub(r'<Override PartName="/%s"[^>]*/>' % re.escape(p), "", ct)
            self.parts.pop(p, None)
        self.parts["xl/workbook.xml"] = wb.encode("utf-8")
        self.parts["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")
        self.parts["[Content_Types].xml"] = ct.encode("utf-8")

    def add_sheet(self, name, xml_bytes, rid, sid):
        wb = self.parts["xl/workbook.xml"].decode("utf-8")
        rels = self.parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
        ct = self.parts["[Content_Types].xml"].decode("utf-8")
        part = f"xl/worksheets/{rid}.xml"
        self.parts[part] = xml_bytes
        wb = wb.replace("</sheets>", f'<sheet name="{name}" sheetId="{sid}" r:id="{rid}"/></sheets>', 1)
        rels = rels.replace("</Relationships>",
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/{rid}.xml"/></Relationships>')
        ct = ct.replace("</Types>",
            f'<Override PartName="/{part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        self.parts["xl/workbook.xml"] = wb.encode("utf-8")
        self.parts["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")
        self.parts["[Content_Types].xml"] = ct.encode("utf-8")

    def save(self, path):
        for dead in ("xl/calcChain.xml",):
            if dead in self.parts:
                self.parts.pop(dead)
                r = self.parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
                r = re.sub(r'<Relationship [^>]*Target="calcChain.xml"[^>]*/>', "", r)
                self.parts["xl/_rels/workbook.xml.rels"] = r.encode("utf-8")
                c = self.parts["[Content_Types].xml"].decode("utf-8")
                c = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", c)
                self.parts["[Content_Types].xml"] = c.encode("utf-8")
        wb = self.parts["xl/workbook.xml"].decode("utf-8")
        if "fullCalcOnLoad" not in wb:
            wb = re.sub(r"<calcPr([^/>]*)/>", r'<calcPr\1 fullCalcOnLoad="1"/>', wb, count=1)
        self.parts["xl/workbook.xml"] = wb.encode("utf-8")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zo:
            for n, d in self.parts.items(): zo.writestr(n, d)


def _styles(rx):
    st = {}
    for cm in re.finditer(r"<c\s+([^>]*?)(/>|>)", rx or ""):
        a = cm.group(1)
        rm = re.search(r'r="([A-Z]+)\d+"', a); sm = re.search(r'\bs="(\d+)"', a)
        if not rm: continue
        st[T._col(rm.group(1))] = f' s="{sm.group(1)}"' if sm else ""
    return st

def _style_in(rx, ref):
    m = re.search(r'<c r="%s"[^>]*?>' % ref, rx or "")
    if not m: return ""
    sm = re.search(r'\bs="(\d+)"', m.group(0))
    return f' s="{sm.group(1)}"' if sm else ""



# ------------------------------------------------------------------ proteksi
def _excel_hash(pwd):
    h = 0
    for ch in reversed(pwd):
        h = ((h >> 14) & 1) | ((h << 1) & 0x7FFF)
        h ^= ord(ch)
    h = ((h >> 14) & 1) | ((h << 1) & 0x7FFF)
    h ^= len(pwd)
    h ^= 0xCE4B
    return h


def _protect(pkg, password="epr26"):
    """Kunci semua sheet + sarankan workbook dibuka read-only."""
    h = _excel_hash(password)
    for nm, part, rid in pkg.sheets():
        if part not in pkg.parts: continue
        x = pkg.parts[part].decode("utf-8")
        if "<sheetProtection" in x: continue
        prot = (f'<sheetProtection sheet="1" objects="1" scenarios="1" formatCells="1" '
                f'formatColumns="1" formatRows="1" insertColumns="1" insertRows="1" '
                f'deleteColumns="1" deleteRows="1" sort="1" autoFilter="1" password="{h:04X}"/>')
        if "<sheetCalcPr" in x:
            x = re.sub(r"(<sheetCalcPr[^>]*/>)", r"\1" + prot, x, count=1)
        else:
            x = x.replace("</sheetData>", "</sheetData>" + prot, 1)
        pkg.parts[part] = x.encode("utf-8")
    # sengaja TIDAK memakai fileSharing/readOnlyRecommended: hanya memunculkan
    # prompt "buka read-only?" setiap kali file dibuka. Cukup proteksi sheet.


STYLES_MIN = (
 '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
 '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
 '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
 '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
 '<fills count="2"><fill><patternFill patternType="none"/></fill>'
 '<fill><patternFill patternType="gray125"/></fill></fills>'
 '<borders count="1"><border/></borders>'
 '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
 '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
 '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
 '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
 '</styleSheet>')


def _rejected_workbook(rows, password="epr26"):
    """Workbook 'Data ditolak': satu sheet + catatan, langsung dari database."""
    cols = ["No", "Quarter", "Invoice Date", "EPP Code", "EPR Code", "EPR Name", "Material Code",
            "Description", "Qty", "Harga", "Total", "Kategori", "EPP Name", "AM", "STATUS",
            "ALASAN", "Sumber file", "Baris"]
    widths = [5, 8, 12, 11, 11, 30, 14, 34, 7, 13, 15, 15, 30, 10, 11, 52, 34, 7]
    out = ['<row r="1">' + "".join(c_str(f"{_cn(i)}1", ' s="1"', c) for i, c in enumerate(cols)) + "</row>"]
    for i, d in enumerate(rows, 1):
        n = i + 1
        cc = [c_num(f"A{n}", "", i),
              c_str(f"B{n}", "", d["quarter"]),
              c_str(f"C{n}", "", datetime.datetime.strptime(d["invoice_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
                    if d["invoice_date"] else ""),
              c_str(f"D{n}", "", d["epp"]), c_str(f"E{n}", "", d["epr"]),
              c_str(f"F{n}", "", d["epr_name"]), c_str(f"G{n}", "", d["material"]),
              c_str(f"H{n}", "", d["description"]), c_num(f"I{n}", "", d["qty"]),
              c_num(f"J{n}", "", d["price"]), c_num(f"K{n}", "", d["total"]),
              c_str(f"L{n}", "", d["kat"]), c_str(f"M{n}", "", d["epp_name"]),
              c_str(f"N{n}", "", d["am"]), c_str(f"O{n}", "", d["status"]),
              c_str(f"P{n}", "", d["keterangan"]), c_str(f"Q{n}", "", d["sumber_file"]),
              c_num(f"R{n}", "", d["baris_sumber"])]
        out.append(f'<row r="{n}">' + "".join(x for x in cc if x) + "</row>")
    h = _excel_hash(password)
    prot = (f'<sheetProtection sheet="1" objects="1" scenarios="1" formatCells="1" formatColumns="1" '
            f'formatRows="1" insertColumns="1" insertRows="1" deleteColumns="1" deleteRows="1" '
            f'sort="1" autoFilter="1" password="{h:04X}"/>')
    colxml = "".join(f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetPr><outlinePr summaryBelow="1" summaryRight="1"/></sheetPr>'
             f'<dimension ref="A1:R{max(1, len(rows)+1)}"/>'
             '<sheetViews><sheetView workbookViewId="0">'
             '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
             '<sheetFormatPr defaultRowHeight="15"/>'
             f'<cols>{colxml}</cols>'
             f'<sheetData>{"".join(out)}</sheetData>' + prot +
             '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
             '</worksheet>')
    notes = [("CATATAN — DATA DITOLAK", None),
             ("Dibuat", datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")),
             ("Isi", f"{len(rows):,} baris yang TIDAK masuk Data terverifikasi."),
             ("ALASAN", "SUDAH TERVERIFIKASI = baris sudah pernah masuk (double) · "
                        "KEMBAR DALAM INPUT = muncul lebih dari sekali di file yang sama · "
                        "LUAR DATABASE EPR = EPR tidak terdaftar"),
             ("Sifat", "Workbook hanya-baca. Isinya mengikuti database, bukan hasil edit manual.")]
    nrows = []
    for i, (a, b) in enumerate(notes, 1):
        cells = (c_str(f"A{i}", ' s="1"', a) if a else "") + (c_str(f"B{i}", ' s="0"', b) if b else "")
        nrows.append(f'<row r="{i}">{cells}</row>')
    noted = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetPr><outlinePr summaryBelow="1" summaryRight="1"/></sheetPr>'
             f'<dimension ref="A1:B{len(notes)}"/>'
             '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
             '<sheetFormatPr defaultRowHeight="15"/>'
             '<cols><col min="1" max="1" width="22" customWidth="1"/>'
             '<col min="2" max="2" width="120" customWidth="1"/></cols>'
             f'<sheetData>{"".join(nrows)}</sheetData>' + prot +
             '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
             '</worksheet>')
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Data ditolak" sheetId="1" r:id="rId1"/>'
            '<sheet name="CATATAN" sheetId="2" r:id="rId2"/></sheets>'
            '<calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>',
        "xl/worksheets/sheet1.xml": sheet.encode("utf-8"),
        "xl/worksheets/sheet2.xml": noted.encode("utf-8"),
        "xl/styles.xml": STYLES_MIN.encode("utf-8"),
    }
    return parts


# ------------------------------------------------------------------ proses
def build(input_paths, emit=lambda s: None, out_dir=None, build_excel=True):
    t0 = time.time(); lines = []
    def log(m):
        lines.append(m); emit(m)
    out_dir = out_dir or T.OUTD

    epr_rows = T.load_master("epr"); epp_rows = T.load_master("epp")
    if not epr_rows: raise RuntimeError("Database EPR kosong.")
    MASTER = [{"code": r.get("EPR CODE","").strip(), "name": r.get("EPR NAME","").strip(),
               "city": r.get("CITY","").strip(), "t_excl": r.get("TARGET EXCL","").strip(),
               "cat": r.get("CATEGORY","").strip(), "am": r.get("AM","").strip(),
               "key": T.norm(r.get("EPR NAME",""))} for r in epr_rows]
    MASTER = [m for m in MASTER if m["code"]]
    CODES = sorted({m["code"] for m in MASTER}); BY_CODE = {}
    for m in MASTER: BY_CODE.setdefault(m["code"], m)
    SKU = D.sku_map()
    log(f"Database EPR : {len(MASTER)} baris, {len(CODES)} kode")
    log(f"Database EPP : {len(epp_rows)} baris")
    log(f"Database SKU : {len(SKU)} model")

    EPP = [{"code": r.get("EPP CODE","").strip(),
            "keys": [T.norm(r.get("NAMA TOKO","")), T.norm(r.get("COMPANY NAME",""))]} for r in epp_rows]
    _epp_cache = {}
    def epp_lookup(name):
        k = T.norm(name)
        if not k: return ""
        if k in _epp_cache: return _epp_cache[k]
        res = ""
        for strict in (True, False):
            hits = [e for e in EPP if (k in e["keys"] if strict else
                    k.replace(" ","") in [x.replace(" ","") for x in e["keys"]])]
            if len({e["code"] for e in hits}) == 1:
                res = hits[0]["code"]; break
        if not res:
            for e in EPP:
                for x in e["keys"]:
                    if x and T.same_entity(k, x):
                        res = e["code"]; break
                if res: break
        _epp_cache[k] = res
        return res

    st0 = D.stats()
    log(f"Data per Q tersimpan : {st0['input_total']:,} baris ({st0['baris']:,} terverifikasi)")

    NEEDS = {"Invoice Date","Invoice No","Material Code","Quantity","Actual Unit Price",
             "Actual Total Amount","UID","Item No","Reseller Name","Dealer Name",
             "T2 Partner code","T3 Partner code","Product","Rebate product category","Status","Remarks",
             "City","Reseller City","SN"}
    HDR_ALIAS = {
        "epp code": "T2 Partner code",
        "epr code": "T3 Partner code",
        "epr name": "Reseller Name",
        "description": "Product",
        "qty": "Quantity",
        "reseller price (idr)": "Actual Unit Price",
        "new price (idr)": "_NewPrice",
        "total price": "Actual Total Amount",
        "epp name": "Dealer Name",
        "product rebate": "Rebate product category",
        "remaks": "Remarks",
        "remarks": "Remarks",
        "status": "Status",
        "sn": "SN",
        "area": "City",
    }
    src = []
    for path in input_paths:
        sheets = T.detect_input_sheets(path)
        if not sheets:
            raise RuntimeError(f"Sheet data tidak ditemukan di {os.path.basename(path)}")
        fname = os.path.basename(path)
        for sh in sheets:
            rows = T.read_sheet(path, sh)
            if not rows:
                continue
            first = T.find_header_row(rows)
            hdr = {i: str(v).strip() for i, v in rows[first].items()}
            norm_hdr = {}
            for i in sorted(hdr):
                raw_h = hdr[i]
                canon = raw_h if raw_h in NEEDS else HDR_ALIAS.get(raw_h.lower(), raw_h)
                if canon in NEEDS or canon == "_NewPrice":
                    norm_hdr[i] = canon
            vals_set = set(norm_hdr.values())
            if "Invoice Date" not in vals_set or "Material Code" not in vals_set:
                if len(sheets) == 1:
                    raise RuntimeError(f"Kolom wajib tidak ditemukan di {fname}.")
                continue
            log(f"Format       : {T.input_version(path, sh)} (sheet '{sh}')")
            n0 = len(src)
            for rn in sorted(rows):
                if rn <= first: continue
                d = rows[rn]
                r = {n: "" for n in NEEDS}
                for i, n in norm_hdr.items():
                    val = (d.get(i) or "").strip()
                    if val and not r.get(n):
                        r[n] = val
                if not r.get("Actual Unit Price") and r.get("_NewPrice"):
                    r["Actual Unit Price"] = r["_NewPrice"]
                if not r.get("Invoice Date") and not r.get("Material Code"): continue
                r["__rn"] = rn; r["__file"] = fname
                src.append(r)
            log(f"Input        : {fname} ({sh}) — {len(src)-n0} baris")
    if not src: raise RuntimeError("File input tidak berisi baris data.")

    self_map = collections.defaultdict(set)
    for r in src:
        if r.get("T3 Partner code") and r.get("Reseller Name"):
            self_map[T.norm(r["Reseller Name"])].add(r["T3 Partner code"])
    SELF_EPR = {k: next(iter(v)) for k, v in self_map.items() if len(v) == 1}
    BYKEY = {m["key"]: m for m in MASTER}; BYTIGHT = {}
    for m in MASTER: BYTIGHT.setdefault(m["key"].replace(" ", ""), m)
    ALIASES = {}
    alias_path = os.path.join(T.DATA, "epr_aliases.json")
    if os.path.exists(alias_path):
        try:
            with open(alias_path, encoding="utf-8") as af:
                raw_al = json.load(af)
            for ak, av in raw_al.items():
                ALIASES[T.norm(ak)] = av.strip()
        except Exception:
            pass
    def _norm_city(c):
        s = re.sub(r"[^A-Z0-9 ]", " ", (c or "").upper()).strip()
        s = re.sub(r"^(KOTA|KAB|KABUPATEN)\s+", "", s).strip()
        return re.sub(r"\s+", " ", s)

    def _city_ok(in_city, master_city):
        ic = _norm_city(in_city)
        mc = _norm_city(master_city)
        if not ic or not mc:
            return True
        return ic == mc or ic in mc or mc in ic

    _cache = {}
    def resolve_epr(r):
        c = (r.get("T3 Partner code") or "").strip().upper()
        in_city = r.get("City") or r.get("Reseller City") or ""
        if c in CODES:
            return c if _city_ok(in_city, BY_CODE[c].get("city", "")) else None
        # Jika sudah punya kode EPR-xxxx yang eksplisit tapi tidak ada di master,
        # jangan dicocokkan paksa lewat nama (mencegah salah masuk ke EPR lain).
        if c and c.startswith("EPR-"):
            return None
        raw_name = r.get("Reseller Name", "")
        k = T.norm(raw_name)
        if not k: return None
        ck = (k, _norm_city(in_city))
        if ck in _cache: return _cache[ck]
        k_clean = re.sub(r"^UNMANAGED[\s\-]+", "", k).strip()

        def _pick(code_cand):
            if not code_cand or code_cand not in BY_CODE:
                return None
            return code_cand if _city_ok(in_city, BY_CODE[code_cand].get("city", "")) else None

        res = None
        if k in ALIASES:
            res = _pick(ALIASES[k])
        if not res and k_clean in ALIASES:
            res = _pick(ALIASES[k_clean])
        if not res:
            # Cek semua master yang namanya cocok + kota cocok
            for cand in MASTER:
                if cand["key"] in (k, k_clean) or cand["key"].replace(" ", "") in (k.replace(" ", ""), k_clean.replace(" ", "")):
                    if _city_ok(in_city, cand.get("city", "")):
                        res = cand["code"]; break
        if not res:
            for cand in MASTER:
                if T.same_entity(k_clean, cand["key"]) and _city_ok(in_city, cand.get("city", "")):
                    res = cand["code"]; break
        if not res:
            c2 = SELF_EPR.get(k) or SELF_EPR.get(k_clean)
            if c2 and c2 in CODES:
                res = _pick(c2)
        _cache[ck] = res
        return res

    def make_key(r, code):
        if r.get("Invoice No"):
            return "|".join([code, r["Invoice No"], r["Material Code"].upper(),
                             r["Quantity"], r["Actual Unit Price"], r.get("Item No","")])
        if r.get("UID"):
            return "UID|" + r["UID"]
        if r.get("SN"):
            return "|".join(["SN", code, r["Material Code"].upper(), r["SN"]])
        return "|".join(["V3", code, r.get("Invoice Date",""), r["Material Code"].upper(),
                         r.get("Quantity",""), r.get("Actual Unit Price",""), r["__file"], str(r["__rn"])])

    REG = D.verified_info(); seen = set()
    ins = []; dbl_rows = []
    n_ver = n_dbl = n_out = 0; nilai_baru = 0.0
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in src:
        code = resolve_epr(r)
        d0 = T.parse_inv_date(r.get("Invoice Date", ""))
        if d0 is None: continue
        mat = r["Material Code"].upper()
        def _flt(x):
            try: return float(x) if x else 0.0
            except ValueError: return 0.0
        qty = _flt(r["Quantity"]); price = _flt(r["Actual Unit Price"])
        tot = _flt(r["Actual Total Amount"]) or qty * price
        rem = f"{r.get('Rebate product category','')} | {r.get('Status','')}"
        if r.get("Remarks"): rem += f" | {r['Remarks']}"
        rem += f" | src {r['__rn']}"
        rec = {"quarter": T.quarter_of(d0), "inv_ser": T.ser(d0),
               "month_ser": T.ser(d0.replace(day=1)), "invoice_date": d0.isoformat(),
               "invoice_no": r.get("Invoice No",""),
               "epp": r.get("T2 Partner code") or epp_lookup(r.get("Dealer Name","")),
               "epr": code or "", "epr_name": r.get("Reseller Name",""),
               "epp_name": r.get("Dealer Name",""), "material": mat,
               "description": r.get("Product",""), "qty": qty, "price": price, "total": tot,
               "kat": kategori(r.get("Rebate product category","")),
               "am": BY_CODE[code]["am"] if code else "",
               "status": STATUS_MAP.get(r.get("Status",""), r.get("Status","")),
               "eim": (SKU.get(mat) or {}).get("cat",""), "remarks": rem, "flag": "Valid"}
        if not code:
            n_out += 1
            k = "OUT|" + (r.get("UID") or f"{r['__file']}|{r['__rn']}")
            ins.append([k, rec["quarter"], rec["inv_ser"], rec["month_ser"], rec["invoice_date"],
                        rec["invoice_no"], rec["epp"], "", rec["epr_name"], rec["epp_name"],
                        rec["material"], rec["description"], rec["qty"], rec["price"], rec["total"],
                        rec["kat"], "", rec["status"], rec["eim"], rec["remarks"], rec["flag"],
                        0, "LUAR DATABASE EPR", r["__file"], r["__rn"], now])
            continue
        k = make_key(r, code)
        note = None
        if k in REG:
            q0, f0, r0 = REG[k]; note = f"SUDAH TERVERIFIKASI - {q0 or '?'} {f0 or '?'} baris {r0}"
        elif k in seen:
            note = "KEMBAR DALAM INPUT"
        if note:
            n_dbl += 1
            d = dict(rec); d["keterangan"] = note; d["is_verified"] = 0
            dbl_rows.append(d)
            dk = k + "|D|" + r["__file"] + "|" + str(r["__rn"])
            ins.append([dk, rec["quarter"], rec["inv_ser"], rec["month_ser"], rec["invoice_date"],
                        rec["invoice_no"], rec["epp"], rec["epr"], rec["epr_name"], rec["epp_name"],
                        rec["material"], rec["description"], rec["qty"], rec["price"], rec["total"],
                        rec["kat"], rec["am"], rec["status"], rec["eim"], rec["remarks"], rec["flag"],
                        0, note, r["__file"], r["__rn"], now])
            continue
        seen.add(k); n_ver += 1; nilai_baru += tot
        ins.append([k, rec["quarter"], rec["inv_ser"], rec["month_ser"], rec["invoice_date"],
                    rec["invoice_no"], rec["epp"], rec["epr"], rec["epr_name"], rec["epp_name"],
                    rec["material"], rec["description"], rec["qty"], rec["price"], rec["total"],
                    rec["kat"], rec["am"], rec["status"], rec["eim"], rec["remarks"], rec["flag"],
                    1, "", r["__file"], r["__rn"], now])
    added = D.add_input(ins)
    log(f"Hasil filter : {n_ver} terverifikasi, {n_dbl} double, {n_out} di luar database EPR")
    log(f"Disimpan ke Data Per Q: +{added} baris")
    if n_ver == 0 and n_dbl == 0 and n_out == 0:
        raise RuntimeError("File input tidak berisi baris data yang bisa diproses.")
    if n_ver == 0:
        log("Catatan      : tidak ada baris baru yang masuk. Semua baris masuk workbook Data ditolak.")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    files = []

    if not build_excel:
        log("Mode cepat   : melewati pembuatan 3 file Excel (hanya update database & dashboard)")
        D.log_run(", ".join(os.path.basename(p) for p in input_paths), len(src), n_ver, n_dbl,
                  n_out, nilai_baru, "dashboard-only")
        st2 = D.stats()
        log(f"Selesai dalam {time.time()-t0:.1f} detik")
        return {"ok": True, "files": [], "name": "", "log": lines,
                "stats": {"input": len(src), "kept": n_ver, "doubles": n_dbl, "outside": n_out,
                          "nilai": nilai_baru, "retail_net": 0.0, "retail_h2": 0.0,
                          "epr_db": len(CODES), "registry": st2["baris"], "added": added,
                          "sku": st2["sku"], "input_total": st2["input_total"],
                          "quarters": dict(st2["quarter"])}}

    # ================= 1. workbook DATA PER Q =================
    q = Pkg(T.TEMPLATE_Q)
    q.drop_sheet("Summary")
    for quarter in QUARTERS:
        part = q.part_of(f"Report Retail {quarter}")
        xml, rows = q.rows_xml(part)
        ST = _styles(rows.get(8) or rows.get(7, ""))
        def S(i, d=""):
            return ST.get(i, d)
        head = []
        for i in (1, 2, 3, 4, 5, 6, 7):
            if i not in rows: continue
            rx = rows[i]
            if i == 3:
                head.append(f'<row r="3">{c_str("A3", _style_in(rx,"A3"), f"EPR SELL IN {quarter} FY26")}</row>')
            elif i == 4:
                head.append(f'<row r="4">{c_str("A4", _style_in(rx,"A4"), QPERIOD[quarter])}</row>')
            elif i == 7:
                hst = _style_in(rx, "AE7")
                head.append(rx.replace("</row>", c_str("AF7", hst, "Quarter") +
                                       c_str("AG7", hst, "Data") + c_str("AH7", hst, "Keterangan") + "</row>"))
            else:
                head.append(rx)
        data = [d for d in D.rows_by_quarter(quarter) if d["is_verified"] == 1]
        out = []
        for n, d in enumerate(data, 1):
            rn = 7 + n
            cc = [c_num(f"A{rn}", S(0), n),
                  c_num(f"B{rn}", S(1), d["inv_ser"]),
                  c_str(f"C{rn}", S(2), d["epp"]),
                  c_str(f"D{rn}", S(3), d["epr"]),
                  c_str(f"E{rn}", S(4), d["epr_name"]),
                  c_str(f"F{rn}", S(5), d["material"]),
                  c_str(f"G{rn}", S(6), d["description"]),
                  c_num(f"I{rn}", S(8), d["qty"]),
                  c_num(f"J{rn}", S(9), d["price"]),
                  c_str(f"K{rn}", S(10), d["flag"]),
                  c_num(f"L{rn}", S(11), d["month_ser"]),
                  c_str(f"N{rn}", S(13), d["epp_name"]),
                  c_str(f"O{rn}", S(14), d["epr_name"]),
                  c_str(f"P{rn}", S(15), d["material"]),
                  c_str(f"Q{rn}", S(16), d["description"]),
                  c_str(f"S{rn}", S(18), "check"),
                  c_str(f"T{rn}", S(19), "check"),
                  c_str(f"U{rn}", S(20), d["kat"]),
                  c_num(f"V{rn}", S(21), d["price"]),
                  c_num(f"Y{rn}", S(24), d["price"]),
                  c_num(f"Z{rn}", S(25), round(d["qty"]*d["price"], 4)),
                  c_str(f"AA{rn}", S(26), f"EPR SELL IN {quarter} FY26"),
                  c_str(f"AB{rn}", S(27), d["am"]),
                  c_str(f"AC{rn}", S(28), d["remarks"]),
                  c_str(f"AD{rn}", S(29), d["status"]),
                  c_str(f"AE{rn}", S(30), d["eim"]),
                  c_str(f"AF{rn}", S(30), quarter),
                  c_str(f"AG{rn}", S(30), "VERIFIED" if d["is_verified"] == 1 else "DOUBLE")]
            if d["is_verified"] != 1:
                cc.append(c_str(f"AH{rn}", S(30), d["keterangan"]))
            out.append(f'<row r="{rn}">' + "".join(x for x in cc if x) + "</row>")
        last = max(7 + len(data), 7)
        x = re.sub(r"<sheetData>.*</sheetData>", "<sheetData>" + "".join(head) + "".join(out) + "</sheetData>",
                   xml, flags=re.S)
        q.write_sheet(part, x, f"A1:AH{last}")
        log(f"  Data Per Q · {quarter}: {len(data)} baris")
    q.add_sheet("CATATAN", _catatan([
        ("CATATAN — DATA PER Q", None),
        ("Dibuat", datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")),
        ("Isi", "Seluruh baris input per kuartal. Kolom AF = Quarter, AG = VERIFIED / DOUBLE, AH = keterangan."),
        ("Kuartal", "Q1 Apr-Jun · Q2 Jul-Sep · Q3 Oct-Dec · Q4 Jan-Mar"),
        ("Sumber", "database Data Per Q (data/epr.db) — kumulatif, tidak pernah dihapus"),
        ("Proses ini", f"{n_ver} terverifikasi, {n_dbl} double, {n_out} di luar database EPR"),
        ("Tersimpan", ", ".join(f"{k}={v}" for k, v in sorted(D.stats()["quarter"].items())) or "-"),
    ]), "rIdTQ", 90)
    fq = os.path.join(out_dir, f"Data Per Q - {stamp}.xlsx")
    _protect(q)
    q.save(fq); files.append(("Data Per Q", fq))
    log(f"Workbook     : {os.path.basename(fq)} ({os.path.getsize(fq)/1e6:.1f} MB)")

    # ================= 2. workbook DATA TERVERIFIKASI =================
    allv = D.verified_all()
    agg = collections.defaultdict(lambda: collections.defaultdict(float))
    midhi = collections.defaultdict(float)
    for d in allv:
        agg[d["epr"]][(d["kat"], d["month_ser"])] += d["price"] * d["qty"]
        if d["eim"] == "Mid High": midhi[d["epr"]] += d["price"] * d["qty"]

    v = Pkg(T.TEMPLATE_VER)
    part = v.part_of("RETAIL")
    xml, rows = v.rows_xml(part)
    ST = _styles(rows.get(17) or "")
    def V(i):
        return ST.get(i, ST.get(0, ""))
    hA = _style_in(rows[13], "A13"); hJ = _style_in(rows[13], "J13")
    hM13 = _style_in(rows[13], "M13"); hAO13 = _style_in(rows[13], "AO13")
    hM14 = _style_in(rows[14], "M14"); hAO14 = _style_in(rows[14], "AO14")
    hM15 = _style_in(rows[15], "M15"); hS15 = _style_in(rows[15], "S15")
    hJ15 = _style_in(rows[15], "J15"); hK15 = _style_in(rows[15], "K15")

    h13 = [c_str(f"{_cn(i)}13", hA, n) for i, n in enumerate(
        ["NO","EPR CODE","EPR NAME","PROVINCE","CITY","SAP No","COMPLIANCE STATUS","AE PIC FY26","COORD.","CATEGORY"])]
    h13 += [c_str("K13", hM13, "TARGET"),
            c_str("N13", hM13, "REVENUE (12 BULAN: APR 2026 - MAR 2027)"),
            c_str("BN13", hAO13, "TOTAL & ACHIEVEMENT"), c_str("BT13", hAO13, "SPLIT")]
    h14 = [c_str("K14", hM14, "FY26"), c_str("L14", hM14, "H1"), c_str("M14", hM14, "H2")]
    for k, f0 in BLK.items(): h14.append(c_str(f"{_cn(f0)}14", hM14, k))
    for ref, lbl in (("BN14","Grand Total FY"),("BO14","Total H1"),("BP14","Total H2"),
                     ("BQ14","ACH H1"),("BR14","ACH H2"),("BS14","ACH FY"),
                     ("BT14","Mid Hi"),("BU14","Low End")):
        h14.append(c_str(ref, hAO14, lbl))
    h15 = [c_str("K15", hK15, "Y TARGET"), c_str("L15", hJ15, "H TARGET"), c_str("M15", hJ15, "H2 TARGET")]
    for k, f0 in BLK.items():
        for j, lbl in enumerate(MLBL):
            h15.append(c_str(f"{_cn(f0+j)}15", hM15, lbl))
        h15.append(c_str(f"{_cn(f0+12)}15", hS15, "Total"))

    out = [rows[i] for i in sorted(rows) if i <= 12]
    out.append(f'<row r="13">' + "".join(x for x in h13 if x) + "</row>")
    out.append(f'<row r="14">' + "".join(x for x in h14 if x) + "</row>")
    out.append(f'<row r="15">' + "".join(x for x in h15 if x) + "</row>")
    if 16 in rows: out.append(rows[16])

    for idx, code in enumerate(CODES, 1):
        rn = 16 + idx
        mr = BY_CODE[code]
        try: yt = float(mr["t_excl"]) if mr["t_excl"] else None
        except ValueError: yt = None
        cc = [c_num(f"A{rn}", V(0), idx), c_str(f"B{rn}", V(1), code), c_str(f"C{rn}", V(2), mr["name"])]
        if mr["city"]: cc.append(c_str(f"E{rn}", V(4), mr["city"]))
        cc.append(c_str(f"H{rn}", V(7), mr["am"]))
        if mr["cat"]: cc.append(c_str(f"J{rn}", V(9), mr["cat"]))
        if yt:
            cc.append(c_num(f"K{rn}", V(10), round(yt)))
            cc.append(c_f(f"L{rn}", V(11), f"K{rn}*0.52", round(yt*0.52)))
            cc.append(c_f(f"M{rn}", V(11), f"K{rn}*0.48", round(yt*0.48)))
        else:
            cc.append(c_f(f"L{rn}", V(11), 'IF(K{rn}="","",K{rn}*0.52)', None))
            cc.append(c_f(f"M{rn}", V(11), 'IF(K{rn}="","",K{rn}*0.48)', None))
        tot_c = {}
        for kname, f0 in BLK.items():
            sub = 0.0
            for j, mser in enumerate(M12):
                mc = f0 + j
                val = agg[code].get((kname, mser), 0.0) / 1.11
                sub += val
                cc.append(c_num(f"{_cn(mc)}{rn}", V(12), round(val, 4)))
            tc = f0 + 12
            cc.append(c_f(f"{_cn(tc)}{rn}", V(18), f"SUM({_cn(f0)}{rn}:{_cn(f0+11)}{rn})", round(sub, 4)))
            tot_c[kname] = tc
        gt = sum(sum(agg[code].get((k, m), 0.0) for m in M12) for k in BLK) / 1.11
        h1 = sum(sum(agg[code].get((k, m), 0.0) for m in M12[:6]) for k in BLK) / 1.11
        h2 = sum(sum(agg[code].get((k, m), 0.0) for m in M12[6:]) for k in BLK) / 1.11
        mid = midhi.get(code, 0.0) / 1.11
        cc.append(c_f(f"BN{rn}", V(40), "+".join(_cn(tot_c[k]) + str(rn) for k in BLK), round(gt, 4)))
        cc.append(c_f(f"BO{rn}", V(40), "+".join(
            f"SUM({_cn(BLK[k])}{rn}:{_cn(BLK[k]+5)}{rn})" for k in BLK), round(h1, 4)))
        cc.append(c_f(f"BP{rn}", V(40), "+".join(
            f"SUM({_cn(BLK[k]+6)}{rn}:{_cn(BLK[k]+11)}{rn})" for k in BLK), round(h2, 4)))
        cc.append(c_f(f"BQ{rn}", V(41), f'IFERROR(BO{rn}/L{rn},"")', round(h1/(yt*0.52), 6) if yt else None))
        cc.append(c_f(f"BR{rn}", V(41), f'IFERROR(BP{rn}/M{rn},"")', round(h2/(yt*0.48), 6) if yt else None))
        cc.append(c_f(f"BS{rn}", V(41), f'IFERROR(BN{rn}/K{rn},"")', round(gt/yt, 6) if yt else None))
        cc.append(c_num(f"BT{rn}", V(42), round(mid, 4)))
        cc.append(c_f(f"BU{rn}", V(42), f"BN{rn}-BT{rn}", round(gt-mid, 4)))
        out.append(f'<row r="{rn}">' + "".join(x for x in cc if x) + "</row>")

    last3 = 16 + len(CODES)
    merges = ([f"{_cn(i)}13:{_cn(i)}15" for i in range(10)] +
              ["K13:M13", "N13:BM13", "BN13:BS13", "BT13:BU13",
               "N14:Z14", "AA14:AM14", "AN14:AZ14", "BA14:BM14"])
    mx = ('<mergeCells count="%d">' % len(merges) +
          "".join(f'<mergeCell ref="{m}"/>' for m in merges) + "</mergeCells>")
    x = re.sub(r"<sheetData>.*</sheetData>", "<sheetData>" + "".join(out) + "</sheetData>", xml, flags=re.S)
    x = _fix_cols(x, 73)          # tampilkan semua kolom A..BU (template menyembunyikan 23 kolom)
    v.write_sheet(part, x, f"A1:BU{last3}", mx)

    h1_net = sum(sum(agg[c].get((k, m), 0.0) for k in BLK for m in M12[:6]) for c in agg) / 1.11
    h2_net = sum(sum(agg[c].get((k, m), 0.0) for k in BLK for m in M12[6:]) for c in agg) / 1.11
    v.add_sheet("CATATAN", _catatan([
        ("CATATAN — DATA TERVERIFIKASI", None),
        ("Dibuat", datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")),
        ("Isi", f"Data Achievement per EPR dari {len(allv):,} baris terverifikasi."),
        ("Sumber", "view Data terverifikasi (gabungan Data Per Q yang lolos verifikasi)"),
        ("Pengurangan 11%", "SEMUA angka revenue sudah dikurangi 11% (dibagi 1,11)."),
        ("Target", "K = target tahunan (exclude tax). L = 52% x K (H1). M = 48% x K (H2)."),
        ("Perhitungan", "H1 = Apr-Sep (6 kolom pertama tiap kategori). H2 = Oct-Mar (6 kolom terakhir). "
                        "BQ = ACH H1 (BO/L) · BR = ACH H2 (BP/M) · BS = ACH FY (BN/K)."),
        ("Nilai H1", f"Rp {h1_net:,.0f}"),
        ("Nilai H2", f"Rp {h2_net:,.0f}"),
        ("Catatan rumus", "Kolom bulan berisi nilai (workbook terpisah dari Data Per Q). "
                          "Total, Grand Total, H1, H2, dan ACH tetap berupa formula hidup di sheet ini."),
    ]), "rIdTV", 91)
    fv = os.path.join(out_dir, f"Data terverifikasi - {stamp}.xlsx")
    _protect(v)
    v.save(fv); files.append(("Data terverifikasi", fv))
    log(f"Workbook     : {os.path.basename(fv)} ({os.path.getsize(fv)/1e6:.1f} MB)")

    # ================= 3. workbook DATA DITOLAK =================
    rej = D.rejected_all()
    fr = os.path.join(out_dir, f"Data ditolak - {stamp}.xlsx")
    rparts = _rejected_workbook(rej)
    with zipfile.ZipFile(fr, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zo:
        for n, d in rparts.items(): zo.writestr(n, d)
    files.append(("Data ditolak", fr))
    log(f"Workbook     : {os.path.basename(fr)} ({len(rej):,} baris ditolak, "
        f"{os.path.getsize(fr)/1e6:.1f} MB)")
    log(f"RETAIL       : {len(CODES)} EPR · H1 Rp {h1_net:,.0f} · H2 Rp {h2_net:,.0f}")

    D.log_run(", ".join(os.path.basename(p) for p in input_paths), len(src), n_ver, n_dbl,
              n_out, nilai_baru, "; ".join(os.path.basename(f) for _, f in files))
    st2 = D.stats()
    log(f"Selesai dalam {time.time()-t0:.1f} detik")
    return {"ok": True, "files": [{"label": l, "path": p, "name": os.path.basename(p)} for l, p in files],
            "name": files[0][1] if files else "", "log": lines,
            "stats": {"input": len(src), "kept": n_ver, "doubles": n_dbl, "outside": n_out,
                      "nilai": nilai_baru, "retail_net": h1_net, "retail_h2": h2_net,
                      "epr_db": len(CODES), "registry": st2["baris"], "added": added,
                      "sku": st2["sku"], "input_total": st2["input_total"],
                      "quarters": dict(st2["quarter"])}}


def _catatan(notes):
    rows = []
    for i, (a, b) in enumerate(notes, 1):
        cells = (c_str(f"A{i}", ' s="1"', a) if a else "") + (c_str(f"B{i}", ' s="0"', b) if b else "")
        rows.append(f'<row r="{i}">{cells}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetPr><outlinePr summaryBelow="1" summaryRight="1"/></sheetPr>'
            f'<dimension ref="A1:B{len(notes)}"/>'
            '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
            '<sheetFormatPr defaultRowHeight="15"/>'
            '<cols><col min="1" max="1" width="26" customWidth="1"/>'
            '<col min="2" max="2" width="115" customWidth="1"/></cols>'
            f'<sheetData>{"".join(rows)}</sheetData>'
            '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
            '</worksheet>').encode("utf-8")
