# EPR Achievement Dashboard (FY26)

Dashboard web lokal yang bersih dan modern untuk memantau pencapaian **EPR Sell In** (data terverifikasi, *exclude* PPN 11%), lengkap dengan mesin verifikasi Python, monitoring **2 target (Target Original & Target Category)**, **Paket Program Berjalan (`Q3 Booster Up`)**, kontribusi EPP, audit data ditolak, serta **Share to PDF** 1 halaman A4.

## Cara Menjalankan Secara Lokal

Klik ganda **`start_dashboard.bat`**, atau jalankan melalui terminal:

```powershell
python server.py
```

Browser otomatis terbuka ke `http://127.0.0.1:8765/`. Hentikan server dengan `Ctrl+C`.

## Fitur Utama

### 1. Upload & Verifikasi Sell Out (Template V1, V2 & V3)
- Klik **Upload Data** → tab **Verifikasi Lokal** → pilih file Sell Out (`.xlsx` / `.xlsm`).
- Mendukung **3 versi template upload** secara otomatis ([engine/epr_tool.py](engine/epr_tool.py) & [engine/epr_build.py](engine/epr_build.py)):
  - **Template V1** (`Sheet1`) & **Template V2** (`Partner Hub`): nilai transaksi masih gross sehingga saat agregasi dibagi `1,11` (*exclude* PPN 11%).
  - **Template V3** (mis. `Report Retail Q1`/`Q2`): memakai **`Product Rebate` (Kolom U)** untuk pemetaan kategori produk (`Consumer`, `Scanner`, `Consumables`, `Dotmatrix`) dan **`Total Price` (Kolom Z)** sebagai nilai pembelian yang dihitung langsung (**tidak dibagi `1,11` lagi**, karena hitungan di Template V3 sudah dipotong PPN 11%).
- **Mode cepat (default)**: langsung memverifikasi dan memperbarui `data/epr.db` + `data/epr_data.json` dalam hitungan detik. Centang *"Sekalian buat 3 file Excel output"* jika ingin membuat `Data Per Q`, `Data terverifikasi`, dan `Data ditolak`.
- **Aturan Verifikasi ([engine/epr_build.py](engine/epr_build.py))**:
  - **Cek Double**: baris kembar dalam satu file (`KEMBAR DALAM INPUT`) maupun yang sudah pernah terverifikasi (`SUDAH TERVERIFIKASI`) otomatis ditolak.
  - **Cek Kode EPR & Kota**: kode `EPR-xxxx` yang tidak terdaftar di `data/epr_master.csv` langsung ditolak (tidak dicocokkan paksa lewat nama), dan kolom `City` ikut diverifikasi agar nama yang sama dari kota berbeda tidak salah masuk.
  - **Alias EPR**: pemetaan nama alternatif diatur di `data/epr_aliases.json`.

### 2. Monitoring 2 Target (Target Original & Target Category) vs Total Pembelian
- Data master EPR di `data/epr_master.csv` menyimpan dua acuan target sekaligus:
  - **Target Original**: target tahunan original (`H1 = 52%`, `H2 = 48%`).
  - **Target Category**: target sesuai tier/kategori (`SUN`, `STAR`, `PLANET`, `MOON`, `CRESCENT`) dengan pembagian **`H1 = 50%`** dan **`H2 = 50%`**.
- **Dashboard & Drawer Detail Partner**:
  - KPI atas, grafik Top EPR, tabel **Rincian Pencapaian per EPR** (`Target Orig`, `Target Cat`, `Total Pembelian`, `Achievement`), serta panel detail partner (`FY26`, `H1`, `H2`) menampilkan perbandingan kedua target terhadap **Total Pembelian (Net)**.

### 3. Ringkasan Program Berjalan & Monitoring Paket (`Q3 Booster Up`)
- Otomatis mengekstrak nama program dari kolom **`Remarks` (AD)** dan menggabungkan variasi penulisan (`Q3 BOOSTER UP`, `Q3 Booster Up`, `“Q3 Booster Up”`, `Q3 Booster`) serta format `EIN-YY-NNNNN` 6 digit ([scripts/export_from_db.py](scripts/export_from_db.py)).
- Mendukung aturan **Periode Program** di `data/program_rules.json` (dapat juga diedit di UI) — transaksi di luar periode program tidak dihitung.
- **Aturan Khusus Program `Q3 Booster Up` (Periode 1 Okt – 31 Des 2026)**:
  - **Sumber Pembelian**: hanya dihitung dari **4 EPP Lokal** (`PT Computek`, `Raka Perkasa`, `Computa`, `Top Distribusi`).
  - **Peserta & Paket Resmi (`data/peserta_booster.csv`)**: terdiri dari **20 EPR** peserta:
    - **Paket Consumer / Unit + Ink Bottle (18 EPR)**: target & hadiah per paket **`SUN`** (`500` Low End / `40` Mid High / `4.200` Ink Bottle — Rp 20 jt), **`STAR`** (`250` / `25` / `2.000` — Rp 10 jt), **`MOON`** (`120` / `10` / `450` — Rp 3,9 jt).
    - **Paket Consumables (2 EPR)** — `EPR-1768 CV Karya Hidup Mulya` (`SUN Consumables`) & `EPR-2013 CV Jaya Makmur Stationary` (`MOON Consumables`): target **`SUN`** (`18.200` `664/003` / `300` `Lainnya` — Rp 20 jt), **`STAR`** (`9.000` / `200` — Rp 10 jt), **`MOON`** (`4.000` / `100` — Rp 3,9 jt).
  - **Filter 31 SKU Tinta Resmi (`data/booster_consumables_sku.csv`)**: hanya menghitung `8` SKU **`INK BOTTLE`** (`664/003`) dan `23` SKU **`OTHERS INK BOTTLE`** (`Lainnya`); produk `Consumables` di luar daftar tersebut (seperti Ribbon/cartridge non-botol) tidak dihitung ke Paket Booster.
  - **Tampilan Ringkas & Pop-up Detail EPR**:
    - Kolom **Result Pembelian (Ringkasan)** merangkum total per tipe (`Ink Bottle: ... pcs`, `Low End: ... Unit`, `Mid High: ... Unit` atau `664/003: ... pcs`, `Lainnya: ... pcs`).
    - **Klik Nama EPR** di tabel Result Paketan untuk membuka **pop-up detail** berisi perbandingan **Target Paket**, **Sudah Beli**, **Kurang Berapa**, progres bar per tipe, serta rincian SKU yang dibeli.
    - Tersedia filter **`Semua Paket (20 EPR)` / `Paket Consumables (2 EPR)` / `Paket Consumer (18 EPR)`** dan filter status keikutsertaan EPR.

### 4. Share to PDF (1 Halaman A4)
- **Share PDF Achievement (Semua EPR)** *(tombol di kanan atas)*: pilih periode **H1**, **H2**, atau **FY26** → mencetak daftar **Target Original**, **Target Category**, **Total Pembelian**, **Ach Orig**, **Ach Cat**, dan **Kekurangan (Cat)** **tanpa nama EPP**.
- **Share PDF Achievement (Per EPR)** *(di dalam Drawer Detail Partner)*: mencetak laporan lengkap 1 EPR (`FY26`, `H1`, `H2` untuk Target Original & Category), grafik bulanan, komposisi kategori, dan sumber pembelian EPP-nya.
- **Share PDF Result Paket** *(di toolbar Monitor EPR Program Berjalan, tombol **`PDF`** di tiap baris EPR, dan di dalam pop-up detail EPR)*: mencetak ringkasan pembelian paket semua peserta sesuai filter aktif atau laporan khusus 1 EPR.

### 5. Audit Verifikasi & Log Data Ditolak
- Menampilkan riwayat setiap upload serta daftar baris yang ditolak (**Double** & **Luar Database EPR**) lengkap dengan pencarian, filter jenis penolakan, dan **Export CSV**.

## Struktur Folder

```text
EPR_Dashboard/
├─ server.py                 Server lokal (dashboard + API upload/verifikasi)
├─ start_dashboard.bat       Launcher double-click Windows
├─ index.html / styles.css / app.js
├─ engine/
│  ├─ epr_tool.py            Pembaca Excel (V1/V2/V3) & normalisasi master
│  ├─ epr_db.py              SQLite append-only (data/epr.db)
│  ├─ epr_build.py           Mesin verifikasi & pembuat workbook
│  └─ seed.py
├─ scripts/
│  ├─ export_from_db.py      Ekspor data/epr.db -> data/epr_data.json
│  └─ process_github.py      Entrypoint opsional untuk GitHub Actions
└─ data/
   ├─ epr.db                 Database SQLite terverifikasi (git-ignored)
   ├─ epr_data.json          Data JSON untuk dashboard
   ├─ epr_master.csv         Master EPR, Target Original & Target Category (H1/H2)
   ├─ epp_master.csv         Master EPP & Kota
   ├─ epr_aliases.json       Mapping alias nama EPR
   ├─ program_rules.json     Aturan periode tanggal & skema paket program
   ├─ peserta_booster.csv    Daftar resmi 20 EPR peserta Paket Booster
   ├─ booster_consumables_sku.csv  Daftar resmi 31 SKU tinta Paket Booster
   └─ sku.xlsx / template_*.xlsx
```
