# EPR Achievement Dashboard (FY26)

Dashboard web lokal yang bersih dan modern untuk memantau pencapaian **EPR Sell In** (data terverifikasi, *exclude* PPN 11%), lengkap dengan mesin verifikasi Python, monitoring kontribusi EPP & Program berjalan, audit data ditolak, serta **Share to PDF** 1 halaman A4.

## Cara Menjalankan Secara Lokal

Klik ganda **`start_dashboard.bat`**, atau jalankan melalui terminal:

```powershell
python server.py
```

Browser otomatis terbuka ke `http://127.0.0.1:8765/`. Hentikan server dengan `Ctrl+C`.

## Fitur Utama

### 1. Upload & Verifikasi Sell Out Cepat
- Klik **Upload Data** → tab **Verifikasi Lokal** → pilih file Sell Out (`.xlsx` / `.xlsm`, format V1 maupun V2).
- **Mode cepat (default)**: langsung memverifikasi dan memperbarui `data/epr.db` + dashboard dalam hitungan detik. Centang *"Sekalian buat 3 file Excel output"* jika ingin mengunduh `Data Per Q`, `Data terverifikasi`, dan `Data ditolak`.
- **Aturan Verifikasi ([engine/epr_build.py](engine/epr_build.py))**:
  - **Cek Double**: baris kembar dalam satu file (`KEMBAR DALAM INPUT`) maupun yang sudah pernah terverifikasi (`SUDAH TERVERIFIKASI`) otomatis ditolak.
  - **Cek Kode EPR & Kota**: kode `EPR-xxxx` yang tidak terdaftar di `data/epr_master.csv` langsung ditolak (tidak dicocokkan paksa lewat nama), dan kolom `City` ikut diverifikasi agar nama yang sama dari kota berbeda tidak salah masuk.
  - **Alias EPR**: pemetaan nama alternatif diatur di `data/epr_aliases.json`.

### 2. Ringkasan Pencapaian, EPP & Program Berjalan
- **KPI & Grafik**: Total Net Revenue (Excl. PPN 11%), Achievement % (`FY26`, `H1` 52%, `H2` 48%), Tren Bulanan per Kategori (`Consumer`, `Scanner`, `Consumables`, `Dotmatrix`), dan Top EPR Aktual vs Target.
- **Ringkasan Kontribusi EPP di Area**: persentase kontribusi setiap EPP beserta kota dan komposisi kategorinya.
- **Ringkasan Program Berjalan (`Remarks` AD)**:
  - Otomatis mengekstrak program dari kolom `Remarks (AD)` (dan menggabungkan format `EIN-YY-NNNNN` ke 6 digit).
  - Klik baris program untuk membuka **Monitor EPR** (menampilkan **Tipe/Model & Qty**, **Pembelian Program**, **Target EPR**, dan **Kekurangan Target**).
  - Mendukung aturan **Periode Program** (`data/program_rules.json` atau edit langsung di UI) — transaksi di luar periode program otomatis tidak dihitung.

### 3. Share to PDF (1 Halaman A4)
- **Share PDF (Semua EPR)** *(tombol di kanan atas)*: pilih periode **H1**, **H2**, atau **FY26** → menghasilkan laporan **Result Achievement EPR** (`Nama EPR | Target | Kekurangan`) **tanpa nama EPP** agar siap dibagikan ke pihak EPP.
- **Share to PDF (Per EPR)** *(di dalam pop-up Detail Partner)*: mencetak laporan lengkap 1 EPR beserta grafik bulanan, komposisi kategori, dan sumber pembelian EPP-nya.

### 4. Audit Verifikasi & Log Data Ditolak
- Menampilkan riwayat setiap upload serta daftar baris yang ditolak (**Double** & **Luar Database EPR**) lengkap dengan pencarian, filter jenis penolakan, dan **Export CSV**.

## Struktur Folder

```text
EPR_Dashboard/
├─ server.py                 Server lokal (dashboard + API upload/verifikasi)
├─ start_dashboard.bat       Launcher double-click Windows
├─ index.html / styles.css / app.js
├─ engine/
│  ├─ epr_tool.py            Pembaca Excel & normalisasi master
│  ├─ epr_db.py              SQLite append-only (data/epr.db)
│  ├─ epr_build.py           Mesin verifikasi & pembuat workbook
│  └─ seed.py
├─ scripts/
│  ├─ export_from_db.py      Ekspor data/epr.db -> data/epr_data.json
│  └─ process_github.py      Entrypoint opsional untuk GitHub Actions
└─ data/
   ├─ epr.db                 Database SQLite terverifikasi
   ├─ epr_data.json          Data JSON untuk dashboard
   ├─ epr_master.csv         Master EPR & Target
   ├─ epp_master.csv         Master EPP & Kota
   ├─ epr_aliases.json       Mapping alias nama EPR
   ├─ program_rules.json     Aturan periode tanggal per program
   └─ sku.xlsx / template_*.xlsx
```
