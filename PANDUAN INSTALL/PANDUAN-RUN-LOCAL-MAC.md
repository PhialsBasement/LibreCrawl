# 📘 CARA JALANKAN LibreCrawl DI MAC

> Panduan ini khusus untuk pengguna **macOS** (MacBook / iMac / Mac Mini).
> Setiap langkah sudah dijelaskan pelan-pelan. Ikuti urutannya dari atas ke bawah.
> Tidak perlu takut salah — santai saja.

---

## 🎯 INI PANDUAN BUAT APA?

**LibreCrawl** itu program untuk ngecek isi website. Mirip seperti robot yang jalan-jalan keliling website, terus ngasih laporan:

- Halaman apa aja yang ada
- Link mana yang rusak
- Judul halaman bener atau nggak
- Dan masih banyak lagi

Program jalan di komputer kamu sendiri (kita sebut "local"). Habis jalanin, kamu buka lewat **browser** (Safari / Chrome / Firefox) seperti buka website biasa.

**Yang kamu butuhin:**

1. **Python** → "mesin" yang baca code programnya
2. **File programnya** → "resep" yang mau dijalankan

---

## 1️⃣ CEK PYTHON SUDAH ADA ATAU BELUM

1. Tekan **Command (⌘) + Spasi** (tombol spasi panjang). Atau klik icon **kaca pembesar** di pojok kanan atas menu bar (itu Spotlight).
2. Ketik: **`terminal`**
3. Klik **Terminal** (iconnya kotak hitam dengan tanda `>`).
4. Di jendela yang muncul, ketik lalu tekan Enter:

```
python3 --version
```

**Lihat hasilnya:**

- Muncul `Python 3.11.x` atau lebih baru → **Bagus, lanjut ke langkah 2.**
- Muncul versi lama / tulisan error → Install yang baru (lihat di bawah).

> **Catatan:** Di Mac pakai `python3` (bukan `python`). Bedanya: `python` biasanya ngarah ke versi lama Mac, `python3` ke versi yang kamu install sendiri.

---

## 2️⃣ INSTALL PYTHON (KALAU BELUM ADA / VERSI LAMA)

### Cara Termudah: Download dari python.org

1. Buka browser (Safari / Chrome), ke: **https://www.python.org/downloads/macos/**
2. Klik link **"universal2 installer"** untuk versi terbaru.
3. Tunggu file `.pkg` selesai didownload.
4. Klik 2 kali file `.pkg` di folder Downloads.
5. Ikuti instruksi di layar:
   - Klik **Continue** → **Continue** → **Agree** → **Install**.
6. Mungkin diminta password login Mac kamu. Ketik password → klik **Install Software**.
7. Tunggu sampai selesai (1-3 menit).
8. Klik **Close**.
9. **Tutup & buka lagi Terminal** (close Terminal, buka lagi).
10. Cek lagi dengan `python3 --version`. Kalau muncul versi → sukses.

### Alternatif: Pakai Homebrew (kalau sudah pernah install)

Kalau kamu sudah punya Homebrew, cukup ketik di Terminal:

```
brew install python@3.11
```

---

## 3️⃣ DOWNLOAD FILE PROGRAMNYA

Pilih salah satu cara:

### Cara A: Pake Git

1. Kalau belum punya Git, install dulu: ketik `git --version` di Terminal. Kalau muncul versi → sudah ada. Kalau error → install Xcode Command Line Tools dengan:

```
xcode-select --install
```

2. Lalu download programnya:

```
cd ~/Desktop
git clone https://github.com/PhialsBasement/LibreCrawl.git
```

3. Tunggu download selesai. Akan muncul folder `LibreCrawl` di Desktop.

### Cara B: Download ZIP (lebih gampang)

1. Buka browser ke **https://github.com/PhialsBasement/LibreCrawl**.
2. Klik tombol hijau **"Code"** → klik **"Download ZIP"**.
3. File akan terdownload ke folder Downloads.
4. **Klik 2 kali** file ZIP → otomatis ke-ekstrak.
5. Hasilnya folder `LibreCrawl-main` di folder Downloads.
6. **Rename** jadi `LibreCrawl` (hapus `-main`).
7. **Pindahin** ke Desktop biar gampang dicari: buka Finder, drag folder ke Desktop.

> **Saran:** Taruh folder `LibreCrawl` di **Desktop** biar gampang dicari.

---

## 4️⃣ JALANKAN PROGRAMNYA

Pilih cara yang paling gampang buat kamu.

### ✅ CARA GAMPANG: Lewat Terminal + Script

1. Buka **Terminal** (⌘ + Spasi → ketik `terminal` → Enter).
2. Masuk ke folder LibreCrawl:

```
cd ~/Desktop/LibreCrawl
```

   Kalau folder ada di tempat lain, sesuaikan. Contoh kalau di Downloads:

```
cd ~/Downloads/LibreCrawl
```

3. Kasih izin script biar bisa jalan:

```
chmod +x start-librecrawl.sh
```

4. Jalanin script-nya:

```
./start-librecrawl.sh
```

5. Tunggu. Pertama kali akan otomatis install bahan yang dibutuhkan (3-10 menit).
6. Kalau muncul tulisan **"LibreCrawl is running!"**, browser otomatis kebuka.
7. **SELESAI!** Tinggal pakai.

> **JANGAN TUTUP** jendela Terminal selama pakai LibreCrawl. Kalau ditutup, program mati.

### ✅ CARA MANUAL: Step by Step

Kalau script otomatis error, pakai cara ini.

1. Buka Terminal.
2. Masuk ke folder LibreCrawl:

```
cd ~/Desktop/LibreCrawl
```

3. Install bahan-bahan:

```
pip3 install -r requirements.txt
```

4. Tunggu 2-10 menit. Banyak tulisan jalan. **Itu normal, jangan panik.**
5. Kalau muncul `Successfully installed...` → sukses.

   > **Kalau muncul error permission:** Coba `pip3 install --user -r requirements.txt` (JANGAN pakai `sudo` kalau tidak paham).
   > **Kalau `pip3` tidak ada:** Coba `python3 -m pip install -r requirements.txt`.

6. Install Chromium (browser mini untuk render JavaScript):

```
playwright install chromium
```

   > Kalau error, coba: `python3 -m playwright install chromium`

7. Tunggu sampai selesai.
8. Sekarang jalanin programnya:

```
python3 main.py -l
```

9. Tunggu sampai muncul tulisan `Running on http://...5000`.
10. **Jangan tutup** Terminal.
11. Buka browser (Safari / Chrome / Firefox).
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

1. Klik jendela Terminal yang tadi dibuka.
2. Tekan **Control + C** di keyboard.
3. Tunggu sampai proses berhenti.
4. Baru tutup jendela Terminalnya.
5. Sekarang boleh close browser.

---

## 🆘 MASALAH YANG SERING TERJADI

### ❌ `python3: command not found`

**Artinya:** Python belum di-install atau Terminal tidak ngenali Python.

**Solusi:** Install Python dari python.org (lihat langkah 2). Setelah install, **tutup & buka lagi Terminal**.

---

### ❌ `pip3: command not found`

**Solusi:** Coba pakai `python3 -m pip`代替 `pip3`:

```
python3 -m pip install -r requirements.txt
```

---

### ❌ `Permission denied` saat install

**Solusi:** Install ke user folder (TANPA sudo):

```
pip3 install --user -r requirements.txt
```

> **Jangan pakai `sudo pip`** — bisa bikin masalah权限 / permission di Mac.

---

### ❌ `Address already in use` atau `Port 5000 is already in use`

**Artinya:** Ada program lain yang pakai port 5000.

**Solusi:** Tutup program sebelumnya, atau ganti port:

```
PORT=5001 python3 main.py -l
```

Habis itu buka `localhost:5001` di browser.

---

### ❌ Muncul tulisan merah banyak saat install

**Jangan panik.** Biasanya karena paket gagal download (internet putus sebentar).

**Solusi:** Jalankan ulang command install-nya:

```
pip3 install -r requirements.txt
```

Kadang perlu 2-3 kali coba sampai berhasil semua.

---

### ❌ Browser tidak otomatis terbuka

**Solusi:** Buka manual. Ketik `localhost:5000` di address bar browser, tekan Enter.

> Di Safari: address bar ada di paling atas.
> Di Chrome: juga di paling atas.

---

### ❌ Halaman `localhost:5000` loading terus / kosong

**Solusi:**

1. Cek jendela Terminal masih jalan (tidak error / tidak ketutup).
2. Tunggu 1-2 menit, kadang perlu waktu buat mulai.
3. Tekan **⌘ + R** di browser buat refresh.
4. Coba `http://127.0.0.1:5000` sebagai pengganti `localhost:5000`.

---

### ❌ Mac bilang "cannot be opened because it is from an unidentified developer"

**Artinya:** Mac memblokir script `.sh` dari internet.

**Solusi:**

1. Buka **System Settings** → **Privacy & Security**.
2. Scroll ke bawah, ada pesan tentang file yang diblokir.
3. Klik **"Open Anyway"**.
4. Coba jalankan script-nya lagi.

Atau alternatif: pakai **Cara Manual** (langkah 4 → ✅ CARA MANUAL) — tidak pakai script `.sh`, jadi tidak kena masalah ini.

---

### ❌ Gatekeeper阻止打开 file `.sh`

**Solusi lewat Terminal langsung:**

```
cd ~/Desktop/LibreCrawl
bash start-librecrawl.sh
```

---

## 📝 TIPS PENTING

1. **Selalu masuk ke folder yang benar** sebelum jalanin command. Cek dengan `pwd` di Terminal buat lihat posisi kamu sekarang.
2. **Jangan tutup jendela Terminal** selama pakai LibreCrawl.
3. **Internet harus nyala** waktu pertama kali install.
4. **Pakai Chrome atau Safari** untuk hasil terbaik.
5. **Jangan test ke website yang sangat besar** (kayak google.com) — pakai website kecil dulu, contoh `example.com`.
6. **Jangan hapus folder LibreCrawl** — di situ semua file programnya.
7. **Di Mac pakai `python3` dan `pip3`** (bukan `python` / `pip`) untuk menghindari bentrok sama Python bawaan Mac.

---

## ✅ CHECKLIST: SUDAH BELUM?

- [ ] Python sudah terinstall dan dicek versinya (`python3 --version`)
- [ ] Folder LibreCrawl sudah didownload & ditaruh di Desktop
- [ ] Bahan-bahan sudah terinstall dengan `pip3 install -r requirements.txt`
- [ ] Chromium sudah terinstall dengan `playwright install chromium`
- [ ] Program jalan dengan `python3 main.py -l`
- [ ] Browser terbuka ke `localhost:5000`
- [ ] LibreCrawl siap dipakai!

Kalau semua sudah dicentang → **🎉 Selamat, kamu berhasil!**

---

**Cara pakai lagi di kemudian hari** (lebih cepat, karena sudah terinstall):

1. Buka Terminal
2. `cd ~/Desktop/LibreCrawl`
3. `python3 main.py -l`
4. Buka `localhost:5000` di browser

**Selamat mencoba!** 💪

> Pengguna Windows? Lihat: **PANDUAN-RUN-LOCAL-WINDOWS.md**