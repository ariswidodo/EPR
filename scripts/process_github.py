# -*- coding: utf-8 -*-
"""Entrypoint untuk GitHub Actions:
1. Memproses semua file Sell Out (.xlsx/.xlsm) di folder inbox/
2. Menyimpan hasil verifikasi ke data/epr.db & workbook di out/
3. Memindahkan file yang sudah diproses ke processed/
4. Mengekspor data terbaru ke data/epr_data.json untuk Dashboard
"""
import datetime
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT, "engine")
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
sys.path.insert(0, ENGINE_DIR)
sys.path.insert(0, SCRIPTS_DIR)

import epr_build as B
import epr_db as D
import epr_tool as T
import export_from_db


def main():
    inbox_dir = os.path.join(ROOT, "inbox")
    processed_dir = os.path.join(ROOT, "processed")
    out_dir = os.path.join(ROOT, "out")
    os.makedirs(inbox_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    # Pastikan SKU terisi jika db baru
    if not D.sku_all() and os.path.exists(T.SKU_FILE):
        n = D.sku_replace(T.import_sku(T.SKU_FILE))
        print(f"Seeded SKU master: {n} model")

    files = sorted(
        os.path.join(inbox_dir, f)
        for f in os.listdir(inbox_dir)
        if f.lower().endswith((".xlsx", ".xlsm")) and not f.startswith("~$")
    )

    if files:
        print(f"Memproses {len(files)} file dari inbox/ ...")
        B.build(files, emit=print, out_dir=out_dir)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        for src in files:
            name = os.path.basename(src)
            dst = os.path.join(processed_dir, name)
            if os.path.exists(dst):
                stem, ext = os.path.splitext(name)
                dst = os.path.join(processed_dir, f"{stem}_{stamp}{ext}")
            shutil.move(src, dst)
            print(f"Dipindahkan ke processed/: {os.path.basename(dst)}")
    else:
        print("Tidak ada file baru di inbox/. Hanya memperbarui data/epr_data.json ...")

    export_from_db.export_data(
        tool_dir=ROOT,
        out_path=os.path.join(ROOT, "data", "epr_data.json"),
    )


if __name__ == "__main__":
    main()
