# EPR Achievement Dashboard (FY26)

Dashboard web lokal yang bersih dan modern untuk memantau pencapaian **EPR Sell In** (data terverifikasi, *exclude* PPN 11%), lengkap dengan mesin verifikasi Python, monitoring **2 target (Target Original & Target Category)**, **Paket Program Berjalan (`Q3 Booster Up`)**, kontribusi EPP, audit data ditolak, serta **Share to PDF** 1 halaman A4.

## Cara Menjalankan Secara Mandiri (Tanpa AI)

Aplikasi ini berjalan mandiri di Windows (`http://127.0.0.1:8765/`) menggunakan Python standard library:

- **Shortcut Desktop (`EPR Dashboard`)** atau klik ganda **`start_dashboard.bat`**: menjalankan server di background (`pythonw.exe`, tanpa jendela CMD) lalu langsung membuka dashboard di browser. Jika server sudah berjalan, otomatis hanya membuka browser.
- **Auto-start saat Login Windows**: jalankan **`install_autostart.bat`** sekali (jika pindah PC/folder) untuk memasang shortcut di folder **Startup Windows** dan **Desktop**.
- **Menghentikan Server Background**: klik ganda **`stop_dashboard.bat`** (atau `Ctrl+C` jika dijalankan manual lewat `python server.py`).

## Fitur Utama

### 1. Upload & Verifikasi Sell Out + Update Master Mandiri
- **Tab `Verifikasi Lokal`**: klik **Upload Data** → pilih file Sell Out (`.xlsx` / `.xlsm`).
- **Tab `Update Master`** (`POST /api/update-master`, [scripts/sync_master.py](scripts/sync_master.py)): update langsung dari browser untuk file master Excel berikut tanpa perlu edit CSV manual:
  1. **Update Target EPR (`db target.xlsx`)** → memperbarui `data/epr_master.csv`.
  2. **Update Peserta Paket Booster & AE/AM (`.xlsx`)** → upsert ke `data/peserta_booster.csv` dan `data/program_rules.json` (mendukung `Peserta Paket Booster.xlsx` maupun `Update Nama AM.xlsx`).
  3. **Update SKU Tinta Paket Booster (`.xlsx`)** → memperbarui `data/booster_consumables_sku.csv` dan `data/program_rules.json`.
  4. **Refresh Hitungan Dashboard**: menyegarkan `data/epr_data.json` langsung dari database & master terbaru.
- Mendukung **3 versi template upload** secara otomatis ([engine/epr_tool.py](engine/epr_tool.py) & [engine/epr_build.py](engine/epr_build.py)):
  - **Template V1** (`Sheet1`) & **Template V2** (`Partner Hub`): nilai transaksi masih gross sehingga saat agregasi dibagi `1,11` (*exclude* PPN 11%).
  - **Template V3** (mis. `Report Retail Q1`/`Q2`): memakai **`Product Rebate` (Kolom U)** untuk pemetaan kategori produk (`Consumer`, `Scanner`, `Consumables`, `Dotmatrix`) dan **`Total Price` (Kolom Z)** sebagai nilai pembelian yang dihitung langsung (**tidak dibagi `1,11` lagi**, karena hitungan di Template V3 sudah dipotong PPN 11%).
- **Mode cepat (default)**: langsung memverifikasi dan memperbarui `data/epr.db` + `data/epr_data.json` dalam hitungan detik. Centang *"Sekalian buat 3 file Excel output"* jika ingin membuat `Data Per Q`, `Data terverifikasi`, dan `Data ditolak`.
- **Aturan Verifikasi ([engine/epr_build.py](engine/epr_build.py))**:
  - **Cek Double**: baris kembar dalam satu file (`KEMBAR DALAM INPUT`) maupun yang sudah pernah terverifikasi (`SUDAH TERVERIFIKASI`) otomatis ditolak.
  - **Cek Kode EPR & Kota**: kode `EPR-xxxx` yang tidak terdaftar di `data/epr_master.csv` langsung ditolak (tidak dicocokkan paksa lewat nama), dan kolom `City` ikut diverifikasi agar nama yang sama dari kota berbeda tidak salah masuk.
  - **Alias EPR**: pemetaan nama alternatif diatur di `data/epr_aliases.json`.

### 2. Monitoring 2 Target (Target Original & Target Category) vs Total Pembelian (Focus H2, Q3 & Q4)
- Karena **H1 (Apr–Sep) sudah Closed**, dashboard otomatis terbuka pada periode fokus **`H2 (Okt–Mar)`** (tersedia juga pilihan kuartal **`Q3 (Okt–Des)`**, **`Q4 (Jan–Mar)`**, serta arsip `FY26 (Full Year)` dan `H1 (Apr–Sep · Closed)`).
- Data master EPR di `data/epr_master.csv` (24 EPR area `ARIS`) menyimpan dua acuan target sekaligus:
  - **Target Original**: target tahunan original dengan pembobotan kuartal dan bulanan resmi:
    - **Q1**: `22%` (Apr, Mei, Jun)
    - **Q2**: `30%` (Jul, Agu, Sep · 10% per bulan)
    - **H1**: `52%` (Q1 + Q2)
    - **Q3**: `30%` (Okt, Nov, Des · 10% per bulan)
    - **Q4**: `18%` (Jan, Feb, Mar · 6% per bulan)
    - **H2**: `48%` (Q3 + Q4)
  - **Target Category**: target sesuai tier/kategori (`SUN`, `STAR`, `PLANET`, `MOON`, `CRESCENT`) dengan pembagian **`H1 = 50%`** dan **`H2 = 50%`**.
- **Panel Monitoring Target Original (Q3 & Q4 Focus)**:
  - Widget interaktif di halaman Overview yang merangkum Target Original Q3 (30%) & Q4 (18%), aktual pembelian, achievement %, dan gap/kekurangan.
  - Tabel rincian bulanan dinamis untuk **Okt 26, Nov 26, Des 26** (10% Target Original) dan **Jan 27, Feb 27, Mar 27** (6% Target Original).
- **Dashboard, Tabel & Drawer Detail Partner**:
  - Filter Slicer: tombol segmented **Q3**, **Q4**, **H2**, **FY26**, dan **H1**.
  - Tabel Rincian Pencapaian per EPR: dilengkapi switcher tampilan antara **Kategori Produk** dan **Breakdown Q3 & Q4**.
  - Drawer Detail Partner: kartu capaian Q3 & Q4 serta tabel rincian bulanan untuk setiap EPR yang dipilih.

### 3. Ringkasan Program Berjalan & Monitoring Paket (`Q3 Booster Up`)
- Otomatis mengekstrak nama program dari kolom **`Remarks` (AD)** dan menggabungkan variasi penulisan (`Q3 BOOSTER UP`, `Q3 Booster Up`, `“Q3 Booster Up”`, `Q3 Booster`) serta format `EIN-YY-NNNNN` 6 digit ([scripts/export_from_db.py](scripts/export_from_db.py)).
- Mendukung aturan **Periode Program** di `data/program_rules.json` (dapat juga diedit di UI) — transaksi di luar periode program tidak dihitung.
- **Aturan Khusus Program `Q3 Booster Up` (Periode 1 Okt – 31 Des 2026)**:
  - **Sumber Pembelian**: hanya dihitung dari **4 EPP Lokal** (`PT Computek`, `Raka Perkasa`, `Computa`, `Top Distribusi`).
  - **Peserta, Paket & AE/AM Resmi (`data/peserta_booster.csv`)**: terdiri dari **82 EPR** peserta lintas AE/AM (`ARIS`: 20 EPR, `HERDIAN`: 42 EPR, `SIGIT`: 20 EPR):
    - **Khusus Paketan Berjalan**: 62 EPR tambahan dari `HERDIAN` & `SIGIT` (`program_partners`) **hanya** dihitung untuk monitoring **Paketan Berjalan (`Q3 Booster Up`)** dan **tidak** dimasukkan ke perhitungan **Per Q, Per H, maupun Per Tahun**.
    - **Paket Consumer / Unit + Ink Bottle (75 EPR)**: target & hadiah per paket **`SUN`** (`500` Low End / `40` Mid High / `4.200` Ink Bottle — Rp 20 jt), **`STAR`** (`250` / `25` / `2.000` — Rp 10 jt), **`MOON`** (`120` / `10` / `450` — Rp 3,9 jt).
    - **Paket Consumables (7 EPR)**: target **`SUN`** (`18.200` `664/003` / `300` `Lainnya` — Rp 20 jt), **`STAR`** (`9.000` / `200` — Rp 10 jt), **`MOON`** (`4.000` / `100` — Rp 3,9 jt).
  - **Filter 31 SKU Tinta Resmi (`data/booster_consumables_sku.csv`)**: hanya menghitung `8` SKU **`INK BOTTLE`** (`664/003`) dan `23` SKU **`OTHERS INK BOTTLE`** (`Lainnya`); produk `Consumables` di luar daftar tersebut (seperti Ribbon/cartridge non-botol) tidak dihitung ke Paket Booster.
  - **Tampilan Ringkas, Filter AE/AM & Pop-up Detail EPR**:
    - Kolom **Result Pembelian (Ringkasan)** merangkum total per tipe (`Ink Bottle: ... pcs`, `Low End: ... Unit`, `Mid High: ... Unit` atau `664/003: ... pcs`, `Lainnya: ... pcs`).
    - **Klik Nama EPR** di tabel Result Paketan untuk membuka **pop-up detail** berisi perbandingan **Target Paket**, **Sudah Beli**, **Kurang Berapa**, progres bar per tipe, serta rincian SKU yang dibeli.
    - Tersedia filter **`Semua AE/AM` (`ARIS` / `HERDIAN` / `SIGIT`)**, **`Semua Paket (82 EPR)` / `Paket Consumables (7 EPR)` / `Paket Consumer (75 EPR)`**, dan filter status keikutsertaan EPR.

### 4. Share to PDF (1 Halaman A4)
- **Share PDF Achievement (Semua EPR)** *(tombol di kanan atas)*: kini mendukung pilihan periode **Q3 (Okt–Des · Kuartal Berjalan)**, **Q4 (Jan–Mar · Kuartal Penutup)**, **H2 (Fokus Berjalan)**, **FY26**, atau **H1 (Closed)** → mencetak daftar **Target Original**, **Target Category**, **Total Pembelian**, **Ach Orig**, **Ach Cat**, dan **Kekurangan (Cat)** **tanpa nama EPP**.
- **Share PDF Achievement (Per EPR)** *(di dalam Drawer Detail Partner)*: mencetak laporan lengkap 1 EPR (`FY26`, `H1`, `H2` untuk Target Original & Category), grafik bulanan, komposisi kategori, dan sumber pembelian EPP-nya.
- **Share PDF Result Paket** *(di toolbar Monitor EPR Program Berjalan, tombol **`PDF`** di tiap baris EPR, dan di dalam pop-up detail EPR)*: mencetak ringkasan pembelian paket semua peserta sesuai filter aktif atau laporan khusus 1 EPR.

### 5. Audit Verifikasi & Log Data Ditolak
- Menampilkan riwayat setiap upload serta daftar baris yang ditolak (**Double** & **Luar Database EPR**) lengkap dengan pencarian, filter jenis penolakan, dan **Export CSV**.

## Struktur Folder

```text
EPR_Dashboard/
├─ server.py                 Server lokal (dashboard + API upload/verifikasi/update master)
├─ start_dashboard.bat       Launcher background (pythonw) + buka browser
├─ stop_dashboard.bat        Menghentikan proses background server.py
├─ install_autostart.bat     Pasang shortcut Startup Windows & Desktop
├─ index.html / styles.css / app.js
├─ engine/
│  ├─ epr_tool.py            Pembaca Excel (V1/V2/V3) & normalisasi master
│  ├─ epr_db.py              SQLite append-only (data/epr.db)
│  ├─ epr_build.py           Mesin verifikasi & pembuat workbook
│  └─ seed.py
├─ scripts/
│  ├─ export_from_db.py      Ekspor data/epr.db -> data/epr_data.json
│  ├─ sync_master.py         Sinkronisasi Excel master (Target/Peserta/SKU)
│  └─ process_github.py      Entrypoint opsional untuk GitHub Actions
└─ data/
   ├─ epr.db                 Database SQLite terverifikasi (git-ignored)
   ├─ epr_data.json          Data JSON untuk dashboard
   ├─ epr_master.csv         Master EPR, Target Original & Target Category (H1/H2)
   ├─ epp_master.csv         Master EPP & Kota
   ├─ epr_aliases.json       Mapping alias nama EPR
   ├─ program_rules.json     Aturan periode tanggal & skema paket program
   ├─ peserta_booster.csv    Daftar resmi 82 EPR peserta Paket Booster & AE/AM (ARIS, HERDIAN, SIGIT)
   ├─ booster_consumables_sku.csv  Daftar resmi 31 SKU tinta Paket Booster
   └─ sku.xlsx / template_*.xlsx
```

## LAN Access

- **Binding address**: server kini mendengarkan pada `0.0.0.0` (semua interface) sehingga dapat diakses dari komputer lain di jaringan LAN.
- **Cara menjalankan**: pastikan server sudah dijalankan dengan `start_dashboard.bat` atau `python server.py`. URL yang dapat diakses dari jaringan lain adalah `http://<IP_LAN_HOST>:8765/` (contoh `http://192.168.1.10:8765/`).
- **Firewall**: buka inbound TCP pada port **8765**. Jika Anda memiliki hak admin, jalankan di PowerShell:
  ```powershell
  New-NetFirewallRule -DisplayName "EPR Dashboard (8765)" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow
  ```
  Jika tidak, tambahkan rule secara manual melalui *Windows Defender Firewall → Inbound Rules → New Rule…* → *Port* → masukkan `8765`.
- **Uji konektivitas**: dari komputer lain, buka browser ke URL di atas atau gunakan `curl`/`Invoke-WebRequest` untuk mengecek `/api/status`.

