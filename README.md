# EPR Achievement Dashboard (FY26)

Dashboard web interaktif, bersih, dan modern untuk memantau pencapaian **EPR Sell In** (data terverifikasi, exclude PPN 11%), lengkap dengan **proses verifikasi otomatis di GitHub Actions**.

## Alur Kerja Otomatis di GitHub

1. **Upload file Sell Out (`.xlsx` / `.xlsm`)** ke folder `inbox/` (langsung lewat GitHub Web UI: *Add file → Upload files*, atau `git push`).
2. **GitHub Actions (`.github/workflows/verify-epr.yml`)** berjalan otomatis:
   - Menjalankan mesin verifikasi Python (`engine/epr_build.py` + `engine/epr_db.py`) tanpa dependensi eksternal.
   - Memperbarui database append-only `data/epr.db` dan memindahkan file input ke `processed/`.
   - Mengekspor hasil terbaru ke `data/epr_data.json` dan melakukan commit otomatis.
   - Menyediakan 3 workbook hasil (`Data Per Q`, `Data terverifikasi`, `Data ditolak`) sebagai **Workflow Artifacts** di tab **Actions**.
3. **Dashboard (GitHub Pages)** otomatis menampilkan angka pencapaian terbaru.

## Fitur Dashboard

- **Ringkasan KPI Real-time**: Total Net Revenue, Overall Achievement %, Partisipasi Partner, dan rasio Mid High vs Low End.
- **Filter Periode & Segmen**: Switch instan antara **FY26 (Full Year)**, **H1 (Apr–Sep, 52% target)**, dan **H2 (Okt–Mar, 48% target)**, serta filter Tier (`SUN`, `STAR`, `MOON`, `EARTH`, `CRESCENT`), Kota, Status, dan pencarian EPR.
- **Visualisasi Interaktif**: Tren Revenue Bulanan per Kategori, Komposisi Produk, dan Top EPR Aktual vs Target.
- **Detail Partner (Slide-over Drawer)**: Klik baris partner mana pun pada tabel untuk melihat pencapaian H1/H2/FY dan tren bulanannya.
- **Upload Excel Manual di Browser**: Bisa juga memuat file `Data terverifikasi - *.xlsx` langsung di browser.
- **Export CSV & Mode Terang/Gelap**.

## Cara Menjalankan Secara Lokal

```bash
cd EPR_Dashboard
python -m http.server 8080
```

Lalu buka `http://127.0.0.1:8080/` di browser.

## Aktivasi GitHub Pages

1. Buka repositori di GitHub → **Settings** → **Pages**.
2. Pada **Build and deployment**, pilih **Deploy from a branch** → Branch `main` / `/ (root)` → **Save**.
3. Pastikan di **Settings → Actions → General → Workflow permissions**, opsi **Read and write permissions** aktif agar GitHub Actions bisa menyimpan hasil verifikasi ke `data/epr_data.json`.
