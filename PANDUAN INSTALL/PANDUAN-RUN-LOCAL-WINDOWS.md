# 📘 CARA JALANKAN LibreCrawl DI WINDOWS

> Panduan ini khusus untuk pengguna **Windows 10 / Windows 11**.
> Setiap langkah sudah dijelaskan pelan-pelan. Ikuti urutannya dari atas ke bawah.
> Tidak perlu takut salah — santai saja.

---

## 🎯 INI PANDUAN BUAT APA?

**LibreCrawl** itu program untuk ngecek isi website. Mirip seperti robot yang jalan-jalan keliling website, terus ngasih laporan:

- Halaman apa aja yang ada
- Link mana yang rusak
- Judul halaman bener atau nggak
- Dan masih banyak lagi

Program jalan di komputer kamu sendiri (kita sebut "local"). Habis jalanin, kamu buka lewat **browser** (Chrome / Firefox / Edge) seperti buka website biasa.

**Yang kamu butuhin:**

1. **Python** → "mesin" yang baca code programnya
2. **File programnya** → "resep" yang mau dijalankan

---

## 1️⃣ CEK PYTHON SUDAH ADA ATAU BELUM

1. Tekan tombol **Windows** di keyboard (tombol bergambar jendela, pojok kiri bawah).
2. Ketik: **`cmd`**
3. Klik **Command Prompt** (icon layar hitam).
4. Di jendela hitam, ketik lalu tekan Enter:

```
python --version
```

**Lihat hasilnya:**

- Muncul `Python 3.11.x` atau lebih baru → **Bagus, lanjut ke langkah 2.**
- Muncul versi lama → Install yang baru (lihat di bawah).
- Muncul `'python' is not recognized` → **Belum ada, install dulu.**

---

## 2️⃣ INSTALL PYTHON (KALAU BELUM ADA)

1. Buka browser, ke: **https://www.python.org/downloads/**
2. Klik tombol kuning **"Download Python 3.x.x"**.
3. Tunggu file `python-3.x.x-amd64.exe` selesai didownload (ada di folder Downloads).
4. Klik 2 kali file itu untuk mulai install.
5. Muncul jendela install. **JANGAN LANGSUNG KLIK "Install Now".**
6. ✅ **WAJIB CENTANG** dulu kotak kecil `Add Python to PATH` di paling bawah jendela install. **INI PENTING BANGET — kalau tidak dicentang, nanti error.**
7. Setelah dicentang, klik **"Install Now"**.
8. Tunggu 1-3 menit sampai muncul **"Setup was successful"**.
9. Tutup jendela install.
10. **Tutup & buka lagi Command Prompt** (close CMD, buka lagi).
11. Cek lagi dengan `python --version`. Kalau muncul versi → sukses.

---

## 3️⃣ DOWNLOAD FILE PROGRAMNYA

Pilih salah satu cara:

### Cara A: Pake Git (lebih gampang update nanti)

1. Install Git dulu dari **https://git-scm.com/download/win**.
2. Download, jalankan installer, klik **Next** terus sampai selesai (jangan diubah-ubah settingnya).
3. Buka Command Prompt, ketik:

```
cd Desktop
git clone https://github.com/PhialsBasement/LibreCrawl.git
```

4. Tunggu download selesai. Akan muncul folder `LibreCrawl` di Desktop.

### Cara B: Download ZIP (lebih gampang, tanpa install Git)

1. Buka browser ke **https://github.com/PhialsBasement/LibreCrawl**.
2. Klik tombol hijau **"Code"** → klik **"Download ZIP"**.
3. Buka folder Downloads, cari file ZIP-nya.
4. Klik kanan → klik **"Extract All..."** → klik **Extract**.
5. Hasilnya folder `LibreCrawl-main`. **Rename** jadi `LibreCrawl` aja (hapus `-main`).

> **Saran:** Taruh folder `LibreCrawl` di **Desktop** biar gampang dicari.

---

## 4️⃣ JALANKAN PROGRAMNYA

Pilih cara yang paling gampang buat kamu.

### ✅ CARA GAMPANG: Klik 2 Kali Script

1. Buka folder `LibreCrawl` di Desktop.
2. Cari file **`start-librecrawl.bat`**.
3. **Klik 2 kali** file itu.
4. Muncul jendela hitam. Tunggu — script akan otomatis install bahan yang dibutuhkan (3-10 menit pertama kali).
5. Kalau sudah selesai, muncul tulisan **"LibreCrawl is running!"**.
6. Browser otomatis kebuka ke LibreCrawl.
7. **SELESAI!** Tinggal pakai.

> **JANGAN TUTUP** jendela hitam selama pakai LibreCrawl. Kalau ditutup, program mati.

### ✅ CARA MANUAL: Lewat Command Prompt

Kalau script di atas error, pakai cara ini.

1. Buka Command Prompt.
2. Masuk ke folder LibreCrawl (ganti `YourName` dengan username Windows kamu):

```
cd C:\Users\YourName\Desktop\LibreCrawl
```

Kalau folder LibreCrawl ada di tempat lain, sesuaikan. Contoh kalau di `D:\Projects\LibreCrawl`:

```
cd D:\Projects\LibreCrawl
```

3. Install bahan-bahan:

```
pip install -r requirements.txt
```

4. Tunggu 2-10 menit. Banyak tulisan jalan di layar. **Itu normal, jangan panik.**
5. Kalau muncul `Successfully installed...` → sukses.

   > **Kalau error:** Coba `python -m pip install -r requirements.txt` sebagai gantinya.

6. Install Chromium (browser mini untuk render JavaScript):

```
playwright install chromium
```

7. Tunggu sampai selesai.
8. Sekarang jalanin programnya:

```
python main.py -l
```

9. Tunggu sampai muncul tulisan `Running on http://...5000`.
10. **Jangan tutup** jendela hitam ini.
11. Buka browser (Chrome / Edge / Firefox).
12. Di address bar (bagian paling atas), ketik:

```
localhost:5000
```

13. Tekan Enter. **LibreCrawl siap dipakai!**

---

## 5️⃣ CARA PAKAI (SINGKAT)

Begitu LibreCrawl terbuka di browser:

1. Ada **kotak input** besar di tengah.
2. Ketik alamat website yang mau dicek, contoh: `https://example.com`.
3. Klik tombol **Start Crawl**.
4. Tunggu beberapa detik / menit — dia akan jalan-jalan di website itu.
5. Hasil muncul di tab sebelah kiri:
   - **URLs** → daftar halaman
   - **Links** → daftar link
   - **Issues** → masalah SEO
   - **Stats** → statistik
6. Klik tiap tab untuk lihat detail.
7. Mau download hasil? Klik **Export** → pilih format (CSV / JSON / XML).

---

## 6️⃣ CARA MATIKIN PROGRAMNYA

1. Klik jendela hitam (Command Prompt) yang tadi dibuka.
2. Tekan **Ctrl + C** di keyboard.
3. Tunggu sampai proses berhenti.
4. Baru tutup jendela hitamnya.
5. Sekarang boleh close browser.

---

## 🆘 MASALAH YANG SERING TERJADI

### ❌ `'python' is not recognized as an internal or external command`

**Artinya:** Python belum di-install, atau waktu install tidak dicentang "Add to PATH".

**Solusi:** Install ulang Python (lihat langkah 2). **Jangan lupa centang `Add Python to PATH`.**

---

### ❌ `pip is not recognized`

**Solusi:**

```
python -m pip install -r requirements.txt
```

---

### ❌ `Permission denied` atau `Access is denied`

**Solusi:** Buka Command Prompt sebagai Administrator.

1. Tekan tombol Windows → ketik `cmd`.
2. Klik kanan **Command Prompt** → klik **"Run as administrator"**.
3. Klik **Yes** di popup yang muncul.
4. Coba lagi command-nya.

---

### ❌ `Address already in use` atau `Port 5000 is already in use`

**Artinya:** Ada program lain yang pakai port 5000.

**Solusi:** Ganti port. Tutup dulu program sebelumnya, atau:

```
set PORT=5001
python main.py -l
```

Habis itu buka `localhost:5001` di browser.

---

### ❌ Muncul tulisan merah banyak saat install

**Jangan panik.** Biasanya karena paket gagal download (internet putus sebentar).

**Solusi:** Jalankan ulang command install-nya:

```
python -m pip install -r requirements.txt
```

Kadang perlu 2-3 kali coba sampai berhasil semua.

---

### ❌ Browser tidak otomatis terbuka

**Solusi:** Buka manual. Ketik `localhost:5000` di address bar browser, tekan Enter.

---

### ❌ Halaman `localhost:5000` loading terus / kosong

**Solusi:**

1. Cek jendela hitam masih jalan (tidak error / tidak ketutup).
2. Tunggu 1-2 menit, kadang perlu waktu buat mulai.
3. Tekan **F5** di browser buat refresh.
4. Coba `http://127.0.0.1:5000` sebagai pengganti `localhost:5000`.

---

### ❌ File `.bat` kedip-kedip terus lalu nutup sendiri

**Artinya:** Ada error tapi langsung tertutup.

**Solusi:** Jalankan manual biar keliatan error-nya:

```
cd C:\Users\YourName\Desktop\LibreCrawl
start-librecrawl.bat
```

---

## 📝 TIPS PENTING

1. **Selalu masuk ke folder yang benar** sebelum jalanin command.
2. **Jangan tutup jendela hitam** selama pakai LibreCrawl.
3. **Internet harus nyala** waktu pertama kali install.
4. **Pakai Chrome atau Edge** untuk hasil terbaik.
5. **Jangan test ke website yang sangat besar** (kayak google.com) — pakai website kecil dulu, contoh `example.com`.
6. **Jangan hapus folder LibreCrawl** — di situ semua file programnya.

---

## ✅ CHECKLIST: SUDAH BELUM?

- [ ] Python sudah terinstall dan dicek versinya
- [ ] Folder LibreCrawl sudah didownload & ditaruh di Desktop
- [ ] Bahan-bahan sudah terinstall dengan `pip install -r requirements.txt`
- [ ] Chromium sudah terinstall dengan `playwright install chromium`
- [ ] Program jalan dengan `python main.py -l`
- [ ] Browser terbuka ke `localhost:5000`
- [ ] LibreCrawl siap dipakai!

Kalau semua sudah dicentang → **🎉 Selamat, kamu berhasil!**

---

**Cara pakai lagi di kemudian hari** (lebih cepat, karena sudah terinstall):

1. Buka Command Prompt
2. `cd C:\Users\YourName\Desktop\LibreCrawl`
3. `python main.py -l`
4. Buka `localhost:5000` di browser

**Selamat mencoba!** 💪

> Pengguna Mac? Lihat: **PANDUAN-RUN-LOCAL-MAC.md**