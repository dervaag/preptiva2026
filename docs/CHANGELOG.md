# Log perubahan

## 2026-11-05 — Rencana rubrik berbasis referensi

- Menambahkan `rubric-validation-plan.md`: penentuan kompetensi dari pekerjaan, pemetaan indikator ke sumber (diambil/diadaptasi/internal), indikator skor 1–5 konkret, gold set asesor, uji AI, dan target keluaran skor → kutipan → indikator → alasan belum naik tingkat → sumber.
- Alasan: tautan sumber saja belum membuat rubrik berbasis referensi atau teruji. Ruang lingkup awal Engineering Manager/persona Manager.
- Hanya dokumentasi; rubrik `2026-11-05.2`, kode, dan perilaku aplikasi tidak berubah. Ambang uji di dokumen adalah usulan internal, dan contoh indikator belum ditinjau ahli.
- Verifikasi: tautan dari `assessment-reference.md` dan `README.md`; `git diff --check` lulus.

## 2026-11-05 — Penutup akhir dan pemrosesan dokumen

- Tanggapan aksi next pada pertanyaan terakhir tidak lagi mengajak lanjut. Guard Indonesia/English berjalan sebelum TTS; follow-up yang masih diizinkan tetap berjalan. Respons lama tersimpan tidak ditulis ulang.
- Menambahkan cleansing konservatif untuk CV PDF, paste, CV tersimpan yang dipakai ulang, dan JD; struktur teks dan fakta tetap dipertahankan. Menghapus margin PDF berulang secara heuristik.
- Menghapus pemotongan diam-diam CV/JD. Dokumen panjang diproses per chunk dengan maksimal dua panggilan ekstraksi serentak lalu ringkasan digabung. Dokumen pendek tetap satu panggilan; embedding/RAG tidak ditambahkan.
- Menetapkan batas eksplisit: PDF 5 MB/30 halaman, CV 200–60.000 karakter, JD 30–40.000 karakter. Input melebihi batas ditolak dengan pesan jelas.
- Dokumentasi ada di `document-processing.md`; log chunk hanya mencatat metadata tanpa teks pribadi.
- Verifikasi: 32 tes backend lulus, termasuk guard penutup, preservasi fakta, batas PDF, isi halaman ke-11, chunk akhir, dan konkurensi; parser NDJSON Node dan regresi Chrome dengan perangkat/database sintetis lulus. Python compile dan git diff --check lulus. .env dan data lokal dikecualikan dari publikasi.

## 2026-11-05 — Ikon mirror kamera

- Mengganti bentuk mirror dengan dua sisi kamera, sumbu putus-putus, dan panah horizontal yang lebih jelas.
- Form dan ruang wawancara memakai partial SVG yang sama agar bentuk ikon konsisten. Perilaku tombol tidak berubah.
- Verifikasi: sintaks Jinja kedua halaman valid dan memakai partial yang sama; render partial dan SVG valid dan `git diff --check` lulus.

## 2026-11-05 — Bahasa, persona, UUID publik, dan kontrol kamera

- Menambahkan pilihan bahasa Indonesia/English per sesi. Pertanyaan/tanggapan/review mengikuti bahasa sesi, transkrip campuran tetap bahasa asli, dan code-switching tidak dihukum. STT OpenAI yang sama tidak lagi dipaksa language=id.
- Memisahkan fokus HR (perilaku/potensi belajar), User (teknis/fungsional), dan Manager (kepemimpinan serta keputusan teknis/bisnis). Menambahkan 61 variasi sudut, riwayat 35 pertanyaan milik pengguna/persona sama, dan satu retry untuk set yang tidak sesuai. Tidak menjamin variasi semantik tanpa batas.
- Rubrik menjadi 2026-11-05.2. HR technical=0, adaptability=25; sesi lama mempertahankan snapshot dan bobotnya.
- URL/API sesi menggunakan UUID yang sudah tersedia, dengan pemeriksaan kepemilikan. FK/job internal tetap numerik; ID pertanyaan/jawaban tidak diubah. URL numerik lama tidak diterima; gunakan Riwayat untuk tautan baru.
- Menambahkan fullscreen opsional; Escape tidak menggagalkan sesi, perpindahan tab tetap menutup sesi. Tidak mengklaim fullscreen mencegah pergantian tab.
- Preview kamera default non-mirror; tombol mirror konsisten di form/ruang dan hanya mengubah video, bukan logo atau label.
- Verifikasi: 22 tes backend dan parser NDJSON Node lulus. Tes Chrome dengan data/perangkat sintetis lulus untuk UUID, mirror hanya pada video, logo tidak dicerminkan, fullscreen pilihan saat mulai, keluar fullscreen tanpa gagal, dan penutupan lewat simulasi visibilitychange. Generasi API nyata pada data sintetis lulus untuk HR id/en, User en, Manager id; respons terhadap jawaban campuran mengikuti bahasa sesi. Audio di-mock pada tes generasi untuk menghindari kredit TTS; pengujian ini tidak mengukur akurasi STT campuran pada semua aksen. Python compile, JavaScript syntax, dan git diff --check lulus.

## 2026-11-05 — Acuan asesmen, persiapan perangkat, dan fokus sesi

- Rubrik 1–5 memakai acuan metodologi OPM, SIOP/APA, SIOP AI, dan ISO 10667. Sumber dan batas klaim dicatat di `assessment-reference.md`; tidak mengklaim sertifikasi atau validitas asesmen seleksi.
- Rubrik Markdown dibaca aplikasi. Sesi baru menyimpan snapshot versi, hash, isi rubrik, sumber, dan bobot dalam JSON `interview_sessions.script.assessment`. Evaluasi menggunakan snapshot, bukan dokumen yang berubah belakangan. Hasil sesi menampilkan tautan acuannya; sesi lama ditandai belum memiliki versi.
- Batas skor tanpa kutipan valid ditegakkan di kode (maksimal 2/5), bukan hanya prompt.
- Transkripsi OpenAI yang sama dipertahankan. Transkrip ditampilkan lebih awal melalui NDJSON; LLM dan suara tetap diproses setelahnya. Filler tidak menahan audio hasil dan rekaman ditargetkan mono 64 kbps.
- Pemeriksaan frame kamera, konfirmasi preview, sinyal mikrofon, tes nada speaker, dan persetujuan aturan wajib sebelum mulai.
- Meninggalkan halaman setelah mulai mengakhiri sesi melalui endpoint close; status terminal tidak bisa dibuka untuk menjawab lagi. Browser diarahkan ke Riwayat. Beacon best-effort, bukan proctoring yang tahan manipulasi.
- `p.ico` dan `pfull.webp` dipindahkan ke `app/static/brand/`; favicon, header, dan halaman login/daftar menggunakan aset tersebut.
- Panduan log JSON tersedia di `logging.md`; aturan pemeliharaan Markdown ditambahkan dalam `AGENTS.md`.
- Verifikasi: 14 tes backend lulus; tes parser NDJSON Node lulus (chunk UTF-8, koneksi terputus, error); smoke test Chrome lulus dengan kamera/mikrofon sintetis, pemeriksaan tombol Mulai, aset logo, simulasi visibilitychange, penutupan database, dan larangan resume. Python compile, JavaScript syntax, dan git diff --check lulus. Tes browser tidak menggantikan pemeriksaan speaker fisik atau event OS pada semua perangkat.

## 2026-11-05 — Perbaikan wawancara nyata

- Mematikan jalur mock wawancara; dummy hanya untuk form development.
- OpenAI menangani pertanyaan, tanggapan, transkripsi, dan evaluasi; ElevenLabs menjadi suara tunggal tanpa fallback suara browser.
- Membatasi konkurensi dan retry 429 ElevenLabs.
- Menghapus pertanyaan tambahan dari tanggapan aksi next ketika batas follow-up habis.
- Tujuh tes regresi backend lulus sebelum pengembangan fitur persiapan perangkat.
# 7 November 2026 — Implementasi awal dari spesifikasi

## Konfigurasi dan pengujian provider

- Menghubungkan durasi per level, follow-up per panjang sesi, sakelar follow-up, dan retry dari `.env`; aturan sesi tersimpan dan divalidasi server.
- Mengaktifkan batas total waktu tanggapan LLM/TTS, format MP3 ElevenLabs, cache berdasarkan format, dan language code hanya untuk model yang mendukungnya.
- Menambahkan diagnostik provider yang aman dan pengujian timeout/retry, snapshot konfigurasi, format/cache audio, serta skrip uji API nyata dengan data sintetis dan database sementara.
- Verifikasi: 21 tes regresi lolos; sesi HR tiga pertanyaan berhasil dengan OpenAI/ElevenLabs nyata sampai hasil akhir. Ketiga voice ID dapat diakses. Ringkasan tanpa rahasia tersedia di `artifacts/live-smoke.json`.

- Menambahkan aplikasi FastAPI/SQLAlchemy, autentikasi, sesi UUID, integrasi OpenAI/ElevenLabs, dan worker arq/in-process.
- Menambahkan antarmuka Preptiva: dashboard, form, riwayat, ruang dengan pemeriksaan perangkat/rekaman/stream transkrip, dan hasil berbukti.
- Menambahkan snapshot rubrik, validasi dokumen, chunking, follow-up terbatas, skor berbobot, Docker, serta pengujian otomatis dengan provider terinjeksi.
- Perbedaan terhadap rancangan historis dan batas verifikasi dicatat di [status implementasi](implementation-status.md).


## 2026-11-07 — Logo dan ikon Preptiva

- Menggunakan wordmark WebP dari pemilik proyek pada sidebar, halaman login/daftar, dan footer melalui macro template yang sama.
- Menggunakan ikon PNG dari pemilik proyek untuk favicon dan Apple touch icon. Kedua aset disalin utuh, tanpa modifikasi gambar.
- Menetapkan ukuran responsif, teks alternatif, dan tautan logo ke beranda/dashboard. CSS hanya membingkai ruang transparan wordmark; bidang putih di halaman autentikasi menjaga tulisan hitam terbaca.
- Lingkup desain: penggantian identitas pada UI yang sudah ada, ENERGY 1 / RHYTHM 1 / MOTION 1, tanpa animasi logo baru.
- Verifikasi lingkup logo: aset WebP/PNG mengembalikan HTTP 200; login/daftar dan dashboard diperiksa pada 320, 390, 768, dan 1440 px, ditambah dashboard 1024 px, tanpa overflow horizontal. Tautan logo autentikasi diuji lewat Tab/Enter; logo sidebar dan footer diuji lewat klik menuju dashboard. Gambar memiliki alt dan dimensi; fokus keyboard disesuaikan untuk latar terang/gelap. Tidak ada error/warning console pada pemeriksaan dashboard.

## 2026-11-07: Simbol sementara dan teks Preptiva

- Mengganti wordmark pada macro logo dengan simbol oranye terbaru dari pemilik proyek dan teks HTML Preptiva di sebelah kanan, mengikuti susunan referensi penggunaan.
- Memakai DM Sans 400 yang sudah dimuat aplikasi, dengan jarak huruf rapat untuk mendekati contoh sans-serif tipis. Nama font persis pada gambar referensi tidak diketahui.
- Membingkai PNG asli dalam SVG mandiri agar margin putih tidak mengecilkan simbol. Data PNG tetap utuh; bingkai yang sama dipakai logo halaman dan favicon. Apple touch icon memakai PNG yang sama.
- Ukuran simbol dan teks disesuaikan untuk sidebar, autentikasi, footer, dan layar kecil. Teks nama menjadi nama aksesibel tautan; simbol di sampingnya dekoratif. Arah ENERGY 1 / RHYTHM 1 / MOTION 1 tetap, gradien berasal dari aset pengguna.
- Verifikasi: login pada 320/1440 px, daftar pada 390 px, dashboard pada 320/390/768/1024/1440 px tanpa overflow horizontal; simbol termuat di semua penempatan. DM Sans 400 terkonfirmasi dimuat, favicon SVG HTTP 200, navigasi logo login lewat Tab/Enter serta klik sidebar/footer berfungsi. Tidak ada error/warning console pada pemeriksaan dashboard.

## 2026-11-07: Redesign form simulasi baru

- Mengikuti referensi pemilik proyek: top bar horizontal, layout dua panel, preview kamera lokal, pilihan persona, bahasa dan jumlah soal. DM Sans dan aksen oranye mengikuti logo terbaru.
- Mempertahankan seluruh input wajib/API multipart; detail kandidat/CV/JD dapat dibuka dan otomatis terbuka saat validasi. Loading/error submit memulihkan isi tombol.
- Menambahkan kontrol kamera/mikrofon terpisah, meter mikrofon, mirror, fullscreen, penanganan izin dan cleanup perangkat termasuk hasil izin yang terlambat setelah navigasi. Preview tidak merekam/mengunggah audio/video.
- Gaya hanya dimuat untuk halaman form. Perilaku dan batas implementasi ada di [session-setup.md](session-setup.md).
- Verifikasi: 21 tes backend, setup smoke responsif/keyboard/permission lifecycle/payload/error, dan alur Chrome login sampai hasil tiga pertanyaan dengan provider tiruan lulus. Review independen menemukan clipping pada desktop pendek; reproducer gagal sebelum perbaikan dan lolos sesudahnya. Preview desktop/mobile diperiksa. Perangkat fisik dan browser non-Chromium belum diuji.

## 2026-11-07: Dropdown custom dan chevron seragam

- Mengganti select browser Bahasa, Gender, dan Level dengan satu macro/komponen custom. Trigger dan menu mengikuti DM Sans, panel putih, aksen oranye, dan pilihan bertanda centang.
- Menyamakan bentuk/ukuran/posisi chevron dropdown dan accordion. Menu berada di atas panel scroll dan dapat membuka ke atas ketika ruang viewport terbatas.
- Menjaga nama/nilai API melalui hidden input, event input/change dan reset. Mendukung pointer, sentuhan, panah/Home/End, ketik huruf, Enter/Space, Escape, Tab, klik di luar, serta hanya satu menu aktif.
- Verifikasi: tes dropdown dan setup smoke lulus; alur Chrome login sampai hasil tiga pertanyaan dengan provider tiruan lulus di salinan sementara. Review independen memeriksa semua dropdown pada 320x480 sampai 1440x768 tanpa temuan baru. Tidak ada panggilan provider berbayar.

## 2026-11-07: Ruang sesi dengan tampilan meeting

- Menambahkan stage pewawancara, preview kandidat, percakapan terstruktur, toolbar compact, dan modal pemeriksaan kamera/mikrofon/speaker/koneksi sebelum mulai. Countdown 3-2-1 mendahului intro.
- Menggunakan karakter 3D orisinal Rina, Andi, dan Pak Hendra dari image_gen bawaan. Ekspresi sprite mengikuti audio, dengan kedip/idle serta kontrol animasi dan reduced motion.
- Menjaga rekaman, retry, transkrip streaming, dan hasil; memperbaiki duplikasi playback follow-up serta pemulihan audio/upload. Menambahkan cleanup media dan konfirmasi keluar.
- Memperbaiki dua temuan review: toolbar layar pendek dapat dicapai dengan scroll, dan state awal dimuat kembali setelah pemulihan back-forward cache. Keduanya memiliki regresi yang gagal sebelum perbaikan.
- Menambahkan verifikasi wajib PC/laptop sesuai instruksi tambahan: HP/tablet/iPad mode desktop diblokir pada UI, akses media, serta API start. Penolakan tidak mengubah status sesi; laptop layar sentuh tetap didukung.
- Memadatkan modal menjadi `Cek perangkat`, preview kiri dan pemeriksaan ringkas kanan, tanpa eyebrow/badge dekoratif. Menghapus teks motivasi serta progres dan catatan privasi yang berulang dari ruang sesuai masukan pemilik proyek.
- Mengubah chat mengikuti referensi DM: bubble pewawancara putih di kiri, kandidat biru di kanan, pesan berurutan dikelompokkan, animasi masuk singkat, dan indikator pemrosesan sesuai aktivitas sebenarnya. Teks putih di biru memiliki kontras 5.17:1.
- Verifikasi chat: 14 skenario controller dan smoke Chrome empat jawaban sampai hasil lulus. Review terisolasi mengonfirmasi scrollback, tombol pesan baru, penggantian transkrip tanpa duplikasi, cleanup indikator, reduced motion, dan overflow teks pada 320–1440 px. Sesi nyata tidak disentuh.
- Verifikasi: 22 tes backend, 12 skenario controller, dan smoke Chrome yang memeriksa blokir tiga jenis mobile lalu desktop empat turn termasuk follow-up sampai hasil lulus memakai database/provider/perangkat sintetis. Pengujian tidak mengirim start/close ke sesi asli. Perangkat fisik dan browser non-Chromium belum diuji. Perilaku dan prompt aset dicatat di [interview-room.md](interview-room.md).
