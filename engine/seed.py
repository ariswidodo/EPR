# -*- coding: utf-8 -*-
"""Isi database awal + pasang template dari file yang Anda kirim."""
import os, shutil, stat
import epr_tool as T
import epr_db as D

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(BASE)

def copy_clean(src, dst):
    if not os.path.exists(src):
        print("  (tidak ada)", src); return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.chmod(dst, stat.S_IWRITE | stat.S_IREAD); os.remove(dst)
    shutil.copyfile(src, dst)
    os.chmod(dst, stat.S_IWRITE | stat.S_IREAD)
    return True

# template workbook
copy_clean(os.path.join(SRC, "DB_DataPerQ.xlsx"), T.TEMPLATE_Q)
copy_clean(os.path.join(SRC, "DB_Terverifikasi.xlsx"), T.TEMPLATE_VER)
print("template Data Per Q       :", os.path.basename(T.TEMPLATE_Q))
print("template Data terverifikasi:", os.path.basename(T.TEMPLATE_VER))

# master EPR / EPP
for kind, fname in (("epr", "EPR_FY26.xlsx"), ("epp", "EPP_FY26.xlsx")):
    rows = T.parse_master_file(os.path.join(SRC, fname), kind)
    T.save_master(kind, rows)
    print(f"master {kind:<3}               : {len(rows)} baris")

# master SKU
if copy_clean(os.path.join(SRC, "DB_SKU.xlsx"), T.SKU_FILE):
    n = D.sku_replace(T.import_sku(T.SKU_FILE))
    print("master SKU                :", n, "model")
