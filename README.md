# EPR Achievement Dashboard (FY26)

Dashboard web interaktif, bersih, dan modern untuk memantau pencapaian **EPR Sell In** (data terverifikasi, exclude PPN 11%).

## Fitur Utama

- **Ringkasan KPI Real-time**: Total Net Revenue, Overall Achievement %, Partisipasi Partner, dan rasio Mid High vs Low End.
- **Filter Periode & Segmen**: Switch instan antara **FY26 (Full Year)**, **H1 (Apr–Sep, 52% target)**, dan **H2 (Okt–Mar, 48% target)**, serta filter Tier (`SUN`, `STAR`, `MOON`, `EARTH`, `CRESCENT`), Kota, Status, dan pencarian EPR.
- **Visualisasi Interaktif**:
  - Tren Revenue Bulanan per Kategori (`Consumer`, `Scanner`, `Consumables`, `Dotmatrix`).
  - Komposisi Kategori Produk.
  - Perbandingan Aktual vs Target Top EPR.
- **Detail Partner (Slide-over Drawer)**: Klik baris partner mana pun pada tabel untuk melihat pencapaian H1/H2/FY dan tren bulanannya.
- **Upload Excel Langsung di Browser**: Muat file `Data terverifikasi - *.xlsx` hasil dari `EPR_Tool` langsung tanpa backend.
- **Export CSV & Mode Terang/Gelap**.

## Cara Menjalankan Secara Lokal

```bash
cd EPR_Dashboard
python -m http.server 8080
```

Lalu buka `http://127.0.0.1:8080/` di browser.

## Memperbarui Data dari `EPR_Tool`

Setiap kali ada proses file baru di `EPR_Tool`, jalankan:

```bash
python scripts/export_from_db.py
```

Skrip ini akan memperbarui `data/epr_data.json` dari `EPR_Tool/data/epr.db` dan `epr_master.csv`. Setelah itu cukup `git add`, `git commit`, dan `git push`.

## GitHub Pages

Repositori ini siap langsung diaktifkan di **Settings → Pages → Deploy from branch (`main` / root)**.
