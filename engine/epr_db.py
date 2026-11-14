# -*- coding: utf-8 -*-
"""Tiga database aplikasi (SQLite, bawaan Python) + log proses.

1. sku          -> master produk (dari SKU.xlsx)
2. data_per_q   -> SELURUH baris input, per kuartal, tidak pernah dihapus
3. terverifikasi-> VIEW dari data_per_q (is_verified=1) = hasil gabungan,
                   dipakai untuk menghitung achievement
"""
import os, csv, sqlite3, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "epr.db")
SCHEMA_VERSION = 3

PQ_COLS = ["kunci", "quarter", "inv_ser", "month_ser", "invoice_date", "invoice_no",
           "epp", "epr", "epr_name", "epp_name", "material", "description",
           "qty", "price", "total", "kat", "am", "status", "eim", "remarks", "flag",
           "is_verified", "keterangan", "sumber_file", "baris_sumber", "diproses_pada"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS sku (
    model           TEXT PRIMARY KEY,
    descr           TEXT,
    cost_center     TEXT,
    individual      TEXT,
    category_prod   TEXT,
    category2       TEXT
);
CREATE TABLE IF NOT EXISTS data_per_q (
    kunci           TEXT PRIMARY KEY,
    quarter         TEXT,
    inv_ser         INTEGER,
    month_ser       INTEGER,
    invoice_date    TEXT,
    invoice_no      TEXT,
    epp             TEXT,
    epr             TEXT,
    epr_name        TEXT,
    epp_name        TEXT,
    material        TEXT,
    description     TEXT,
    qty             REAL,
    price           REAL,
    total           REAL,
    kat             TEXT,
    am              TEXT,
    status          TEXT,
    eim             TEXT,
    remarks         TEXT,
    flag            TEXT,
    is_verified     INTEGER,
    keterangan      TEXT,
    sumber_file     TEXT,
    baris_sumber    INTEGER,
    diproses_pada   TEXT
);
CREATE INDEX IF NOT EXISTS idx_pq_q      ON data_per_q(quarter);
CREATE INDEX IF NOT EXISTS idx_pq_ver    ON data_per_q(is_verified);
CREATE INDEX IF NOT EXISTS idx_pq_epr    ON data_per_q(epr);
CREATE INDEX IF NOT EXISTS idx_pq_month  ON data_per_q(month_ser);
CREATE VIEW IF NOT EXISTS terverifikasi AS
    SELECT * FROM data_per_q WHERE is_verified = 1;
CREATE TRIGGER IF NOT EXISTS pq_no_update BEFORE UPDATE ON data_per_q
BEGIN
    SELECT RAISE(ABORT, 'Data Per Q append-only: baris tidak boleh diubah. Upload data baru untuk menambah.');
END;
CREATE TRIGGER IF NOT EXISTS pq_no_delete BEFORE DELETE ON data_per_q
BEGIN
    SELECT RAISE(ABORT, 'Data Per Q append-only: baris tidak boleh dihapus. Gunakan tombol Reset database.');
END;
CREATE TABLE IF NOT EXISTS proses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    waktu        TEXT,
    file         TEXT,
    baris_input  INTEGER,
    masuk        INTEGER,
    double       INTEGER,
    luar_db      INTEGER,
    nilai        REAL,
    output       TEXT
);
"""


def _con(path=None):
    p = path or DB
    os.makedirs(os.path.dirname(p), exist_ok=True)
    c = sqlite3.connect(p, timeout=20)
    c.execute("PRAGMA journal_mode=DELETE")
    c.execute("PRAGMA synchronous=FULL")
    ver = c.execute("PRAGMA user_version").fetchone()[0]
    if ver != SCHEMA_VERSION:
        c.executescript("DROP VIEW IF EXISTS terverifikasi; DROP TABLE IF EXISTS data_per_q;"
                        "DROP TABLE IF EXISTS sku;")
        c.executescript(SCHEMA)
        c.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        c.commit()
    else:
        c.executescript(SCHEMA)
    return c


# ------------------------------------------------------------------ SKU
def sku_replace(rows):
    """rows: list of (model, desc, cost_center, individual, category_prod, category2)."""
    c = _con()
    c.execute("DELETE FROM sku")
    c.executemany("INSERT OR REPLACE INTO sku VALUES (?,?,?,?,?,?)", rows)
    c.commit(); n = c.execute("SELECT COUNT(*) FROM sku").fetchone()[0]; c.close()
    return n

def sku_all():
    c = _con()
    rows = c.execute("SELECT model,descr,cost_center,individual,category_prod,category2 "
                     "FROM sku ORDER BY model").fetchall()
    c.close()
    return rows

def sku_map():
    """model (huruf besar) -> {'desc','cat','indiv'}"""
    c = _con()
    m = {}
    for model, descr, cc, indiv, catp, cat2 in c.execute(
            "SELECT model,descr,cost_center,individual,category_prod,category2 FROM sku"):
        m[(model or "").upper()] = {"desc": descr or "", "cat": catp or "", "indiv": indiv or ""}
    c.close()
    return m


# ------------------------------------------------------------------ data per Q
def add_input(rows):
    """Simpan SEMUA baris input. rows: list sesuai PQ_COLS."""
    if not rows: return 0
    c = _con()
    n0 = c.execute("SELECT COUNT(*) FROM data_per_q").fetchone()[0]
    c.executemany(f"INSERT OR IGNORE INTO data_per_q ({','.join(PQ_COLS)}) "
                  f"VALUES ({','.join('?'*len(PQ_COLS))})", rows)
    c.commit()
    n1 = c.execute("SELECT COUNT(*) FROM data_per_q").fetchone()[0]
    c.close()
    return n1 - n0

def verified_keys():
    c = _con()
    s = {r[0] for r in c.execute("SELECT kunci FROM data_per_q WHERE is_verified=1")}
    c.close()
    return s

def verified_info():
    c = _con()
    out = {r[0]: (r[1], r[2], r[3]) for r in c.execute(
        "SELECT kunci, quarter, sumber_file, baris_sumber FROM data_per_q WHERE is_verified=1")}
    c.close()
    return out

def rows_by_quarter(q, verified_only=False):
    c = _con()
    c.row_factory = sqlite3.Row
    sql = f"SELECT {','.join(PQ_COLS)} FROM data_per_q WHERE quarter=?"
    if verified_only: sql += " AND is_verified=1"
    sql += " ORDER BY inv_ser, epr, material, kunci"
    out = [dict(r) for r in c.execute(sql, (q,))]
    c.close()
    return out

def rejected_all():
    """Semua baris yang tidak lolos verifikasi (double / luar database EPR)."""
    c = _con()
    c.row_factory = sqlite3.Row
    out = [dict(r) for r in c.execute(
        f"SELECT {','.join(PQ_COLS)} FROM data_per_q WHERE is_verified=0 "
        "ORDER BY (CASE WHEN keterangan='LUAR DATABASE EPR' THEN 1 ELSE 0 END), "
        "quarter, inv_ser, epr, material")]
    c.close()
    return out


def verified_all():
    c = _con()
    c.row_factory = sqlite3.Row
    out = [dict(r) for r in c.execute(
        f"SELECT {','.join(PQ_COLS)} FROM data_per_q WHERE is_verified=1 "
        "ORDER BY quarter, inv_ser, epr, material")]
    c.close()
    return out

def log_run(file, baris_input, masuk, double, luar_db, nilai, output):
    c = _con()
    c.execute("INSERT INTO proses (waktu,file,baris_input,masuk,double,luar_db,nilai,output) "
              "VALUES (?,?,?,?,?,?,?,?)",
              (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), file, baris_input,
               masuk, double, luar_db, nilai, output))
    c.commit(); c.close()


def stats():
    c = _con()
    tot = c.execute("SELECT COUNT(*) FROM data_per_q").fetchone()[0]
    ver, nilai = c.execute("SELECT COUNT(*), COALESCE(SUM(total),0) FROM data_per_q "
                           "WHERE is_verified=1").fetchone()
    per = c.execute("SELECT MIN(invoice_date), MAX(invoice_date) FROM data_per_q WHERE is_verified=1").fetchone()
    files = c.execute("SELECT COUNT(DISTINCT sumber_file) FROM data_per_q").fetchone()[0]
    eprs = c.execute("SELECT COUNT(DISTINCT epr) FROM data_per_q WHERE is_verified=1").fetchone()[0]
    qs = {r[0]: r[1] for r in c.execute("SELECT quarter, COUNT(*) FROM data_per_q "
                                        "WHERE is_verified=1 GROUP BY quarter")}
    qall = {r[0]: r[1] for r in c.execute("SELECT quarter, COUNT(*) FROM data_per_q GROUP BY quarter")}
    sku = c.execute("SELECT COUNT(*) FROM sku").fetchone()[0]
    runs = c.execute("SELECT COUNT(*) FROM proses").fetchone()[0]
    c.close()
    def fmt(s):
        if not s: return ""
        try: return datetime.datetime.strptime(s, "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError: return s
    return {"baris": ver, "nilai": nilai, "input_total": tot, "periode_min": fmt(per[0]),
            "periode_max": fmt(per[1]), "file": files, "epr": eprs, "sku": sku,
            "proses": runs, "quarter": qs, "quarter_all": qall}


def recent(n=5):
    c = _con()
    rows = c.execute("SELECT waktu,file,masuk,double,output FROM proses ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    c.close()
    return [{"waktu": r[0], "file": r[1], "masuk": r[2], "double": r[3], "output": r[4]} for r in rows]


def export_csv(path, only_verified=True):
    c = _con()
    sql = f"SELECT {','.join(PQ_COLS)} FROM data_per_q"
    if only_verified: sql += " WHERE is_verified=1"
    sql += " ORDER BY quarter, inv_ser, epr, material"
    cur = c.execute(sql)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([x.upper() for x in PQ_COLS])
        w.writerows(cur)
    c.close()
    return path


def reset_input():
    """Hapus data per Q (semua). SKU tidak disentuh.

    Trigger append-only dilepas sementara, lalu dipasang lagi.
    """
    c = _con()
    n = c.execute("SELECT COUNT(*) FROM data_per_q").fetchone()[0]
    c.executescript("DROP TRIGGER IF EXISTS pq_no_delete; DROP TRIGGER IF EXISTS pq_no_update;")
    c.execute("DELETE FROM data_per_q")
    c.commit()
    c.executescript(SCHEMA)
    c.close()
    return n
