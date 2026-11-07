# Form simulasi baru

Halaman `/simulasi/baru` memakai fondasi visual baru dari referensi pemilik proyek: navigasi horizontal, panel putih dua kolom di desktop, pratinjau perangkat di kiri dan pengaturan wawancara di kanan. Pada mobile kedua panel tersusun vertikal dan tombol aksi mengikuti isi form tanpa menutupinya.

DM Sans mengikuti teks logo. Latar abu-abu, tipografi charcoal, dan aksen oranye menjaga fokus pada pilihan sesi dan tombol Siapkan wawancara. Bayangan panel membedakan satu ruang kerja dari latar; warna avatar membedakan tiga persona AI. Ikon perangkat menggambarkan tindakan masing-masing, bukan dekorasi. ENERGY 1 / RHYTHM 1 / MOTION 1; tidak ada animasi baru.

## Perilaku

- Kamera dan mikrofon dapat diaktifkan atau dimatikan secara terpisah. Mikrofon menampilkan level sinyal, tanpa memutarnya melalui speaker.
- Preview memakai MediaStream lokal, tanpa MediaRecorder atau upload. Navigasi menghentikan seluruh track dan AudioContext. Hasil permintaan izin dari halaman sebelumnya diabaikan, termasuk saat halaman dipulihkan.
- Mirror menyimpan preferensi di sessionStorage dengan key yang sama dengan ruang wawancara. Fullscreen hanya membuka panel preview.
- Preview di form bersifat opsional. Pemeriksaan perangkat dan konfirmasi speaker di ruang wawancara tetap berlaku setelah sesi disiapkan.
- Persona HR, bahasa Indonesia, dan tujuh pertanyaan tetap menjadi default. Pergantian persona memperbarui deskripsi, tanpa panggilan API. Format Panel menyediakan 2–3 pewawancara dengan input `panel` berulang; format tunggal menonaktifkan input panel. Jumlah pertanyaan tetap total seluruh sesi.
- Bagian Detail kandidat & posisi menyimpan nama, gender, usia, latar pengalaman (`career_stage`), CV PDF/teks/CV terakhir, posisi, level, industri, perusahaan dan JD. Bagian otomatis terbuka saat validasi membutuhkan input di dalamnya.
- PDF dibatasi 5 MB pada browser. Teks CV memerlukan 200 karakter jika tidak memakai PDF/CV tersimpan. Validasi server tetap menjadi acuan, termasuk ekstraksi dan cleansing PDF/CV/JD.
- Consent tetap wajib. POST multipart menggunakan field API yang sama. Loading dan kegagalan submit mempertahankan label serta ikon tombol.

## File

- `app/templates/partials/session-setup.html`: markup dan seluruh input.
- `app/templates/partials/setup-icons.html`: ikon SVG untuk kontrol UI.
- `app/templates/partials/custom-select.html`: macro `select_field(name, label, options, value, translation='')`, dipakai format wawancara, bahasa, gender, level, dan latar pengalaman.
- `app/static/css/session-setup.css`: gaya khusus halaman form.
- `app/static/css/custom-select.css`: trigger, chevron, menu, dan pilihan aktif dropdown.
- `app/static/js/custom-select.js`: interaksi combobox/listbox dan sinkronisasi hidden input ke FormData.
- `app/static/js/session-setup.js`: perangkat, pilihan persona, nama preview, dan validasi CV.
- `app/templates/app.html`: memilih shell/asset form; halaman lain memakai shell sebelumnya.

## Verifikasi

Dengan server development aktif dan akun demo sudah di-seed:

```sh
.venv/bin/pip install playwright
.venv/bin/python tests/setup_smoke.py
```

Tes memakai Google Chrome, perangkat sintetis, dan session POST yang diintersep. Tidak membuat sesi AI atau memakai kredit provider. Pemeriksaan mencakup viewport 320/390/768/1024/1440 px, keyboard, field tersembunyi, payload, kegagalan submit, lifecycle perangkat, izin yang selesai terlambat dan pesan penolakan pada desktop 1440x768.

Dropdown memakai menu custom, bukan popup select bawaan browser. Hidden input mempertahankan nama/nilai API. Menu dipasang di body agar tidak terpotong panel scroll, diposisikan di atas/bawah trigger sesuai ruang viewport, dan ditutup jika trigger tersembunyi. Chevron dropdown dan accordion memakai bentuk SVG serta ukuran yang sama.

Keyboard: Enter/Space membuka atau memilih; panah dan Home/End memindahkan pilihan aktif; ketik huruf untuk mencari, termasuk mengulang huruf untuk beralih antar pilihan; Escape membatalkan; Tab memilih lalu melanjutkan fokus. Klik di luar menutup menu. Hanya satu menu terbuka, reset form memulihkan pilihan awal. Pemilihan mengirim event input/change seperti kontrol form biasa.

```sh
.venv/bin/python tests/dropdown_smoke.py
```

Tes dropdown memeriksa pointer, sentuhan mobile, keyboard, dismissal, FormData/reset, dan menu di dekat batas viewport. Tidak mengirim sesi atau memanggil provider. Screen-reader dan browser non-Chromium belum diuji.

`tests/browser_smoke.py` juga disesuaikan agar alur wawancara lengkap melewati form baru. Perangkat fisik dan browser selain Chromium belum diuji pada perubahan ini.

Pengukuran kontras perubahan ini: helper text 5.31:1, teks CTA 6.03:1, fokus 6.73:1, ikon perangkat 5.11:1. Border input memakai #858a97 di atas putih. Gate ini berlaku pada halaman form baru, bukan audit menyeluruh halaman lain.
