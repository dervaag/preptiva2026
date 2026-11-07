# Log perubahan

## 2026-11-07 — Pertanyaan adaptif, konteks kandidat, dan panel

- Memisahkan panduan/panggilan generator dan konteks evaluator HR, User, Manager. HR menerima latar CV dan tanggung jawab pekerjaan, tanpa daftar skill/persyaratan teknis atau skor User. Kompetensi teknis ditolak untuk pertanyaan HR.
- Menambahkan 61 tujuan penggalian internal pada `question-guidebook.json` beserta pemetaan metodologi empat dokumen di `question-guidebook.md`. Versi/hash disnapshot; rubrik `2026-11-05.2` tetap `validated: false`.
- Menambahkan pilihan latar pengalaman serta profil dari kutipan CV terverifikasi. Perkuliahan, proyek, organisasi dan magang menjadi konteks fresh graduate; usia/level posisi tidak dipakai untuk menebak pengalaman.
- Pertanyaan utama berikutnya dibentuk ulang dari seluruh percakapan, bukti CV dan persona berikutnya. Slot/kompetensi dipertahankan; update atomik dan retry idempoten. Audio rencana masa depan tidak dibuat sebelum adaptasi.
- Menambahkan panel 2–3 interviewer: pembagian giliran, identitas aktif, suara per persona, hasil per persona dan agregat bobot panel. Tidak memerlukan migrasi tabel; sesi lama tetap kompatibel.
- Verifikasi: 45 tes unit/integrasi lulus. Chrome dengan provider/perangkat sintetis memeriksa mode tunggal, panel dua/tiga, pergantian pembicara, adaptasi, hasil dan layout mobile. Probe model nyata menggunakan CV/JD sintetis secara terpisah dari data produksi; hasil ada di `artifacts/question-quality-smoke.json`. Pengujian perangkat lunak ini bukan validasi psikometrik oleh asesor.

## 2026-11-07 — Registrasi runner deployment GitHub

- Memasang runner resmi ARM64 v2.338.2 setelah verifikasi checksum GitHub, di `~/actions-runner-preptiva`.
- Mendaftarkan runner `preptiva-kiri-bima` ke `dervaag/preptiva2026` melalui prompt token interaktif dan menjalankannya sebagai service akun Mac. Koneksi GitHub berhasil dan runner siap menerima job.
- Verifikasi sebelum push: 35 tes lokal, syntax JavaScript, dan `git diff --check` lulus. Token registrasi tidak disimpan dalam source proyek.
- Push `f98470c` berhasil memicu tes GitHub dan deployment ke runner Mac; job deploy selesai `Succeeded`. Release aktif cocok dengan commit, empat service healthy, dan health URL publik lulus. Auto-deploy kini aktif; ringkasan aktivasi pertama ada di `artifacts/kiri-ci-deploy.json`.

## 2026-11-07 — Autostart Kiri Share

- Mengaktifkan LaunchAgent akun Mac `com.preptiva.kiri-share` atas permintaan pengguna. Service dijalankan setelah login dan dipulihkan launchd jika berakhir; tunnel manual lama dihentikan setelah layanan penggantinya siap.
- Menambahkan `deploy/kiri_share_service.py` untuk install/status/restart/stop. Runtime/config/log privat disimpan di Application Support, di luar folder IDE.
- URL baru disinkronkan ke `PUBLIC_ORIGIN` pada environment shared, bootstrap, dan release aktif dengan lock deployment. Kredensial database, secret sesi, tag image, dan volume tetap dipertahankan.
- Tiga tes service lulus. Restart layanan menghasilkan URL baru dan health publik kembali sehat; reboot macOS tidak dilakukan. URL terkini tersedia melalui perintah status karena nama tunnel belum direservasi permanen.
- Smoke test Chrome setelah restart lulus untuk registrasi/login/logout, HTTPS, database/Redis, worker dan volume bersama. Pemeriksaan akhir mencatat satu proses Share aktif, origin tersinkron, serta kredensial tetap sama pada `artifacts/kiri-autostart.json`.

## 2026-11-07 — Publikasi Preptiva melalui Kiri Share

- Menambahkan binding web khusus loopback `127.0.0.1:18080` sebagai target tunnel publik; PostgreSQL/Redis tetap internal dan volume data dipertahankan.
- Menambahkan `PUBLIC_ORIGIN` HTTPS yang dicocokkan persis agar login/registrasi tetap bekerja ketika tunnel mengganti header Host. Pemeriksaan origin lain dan `Sec-Fetch-Site: cross-site` tetap aktif; tidak mempercayai header forwarded dari klien.
- Menambahkan opsi URL pada smoke test Kiri, penanganan konfirmasi pengunjung Kiri, serta artefak pemeriksaan publik terpisah.
- Pada publikasi awal, Share berjalan manual dengan URL acak; autostart kemudian diaktifkan pada pembaruan di atas.
- Verifikasi: 32 tes regresi lokal lulus. Smoke test Chrome pada URL publik lulus untuk HTTPS tepercaya, ketersediaan API kamera/mikrofon, registrasi/login/logout, cookie Secure/HttpOnly, health PostgreSQL/Redis, job worker, dan volume bersama. Akun uji dibersihkan dan tidak ada panggilan AI berbayar. Hasil: `artifacts/kiri-public-smoke.json`.

## 2026-11-07 — Deployment otomatis ke satu Mac Kiri

- Menambahkan workflow tes GitHub-hosted dan deployment `main` ke runner Mac ARM64 berlabel `preptiva-kiri-bima`; job PR tidak memakai runner deployment.
- Menambahkan release terpisah, salinan environment lokal yang dipertahankan, image unik, lock deployment, pemeriksaan commit terbaru, healthcheck, dan pemulihan container release sebelumnya saat aktivasi gagal. Volume PostgreSQL/Redis/audio tetap pada project `preptiva`.
- Mendokumentasikan registrasi runner sekali, alur push/PR/merge, dan batasan akses domain lokal serta pemulihan database. Auto-deploy belum aktif sampai runner terdaftar dan workflow dipush serta dijalankan sukses.
- Menambahkan tes deployment untuk perlindungan kredensial, pengecualian key/data, kegagalan build/health, dan pencegahan commit kedaluwarsa.
- Verifikasi: 30 tes lulus pada Python lokal dan container Python 3.12 tanpa jaringan; syntax JavaScript dan Compose valid; empat service Kiri healthy dan HTTPS `/health` mengembalikan PostgreSQL/Redis aktif. Environment deployment terpisah sudah disalin identik dengan permission `600`. Eksekusi workflow GitHub belum diuji.

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
- Memisahkan fokus HR (perilaku/potensi belajar), User (teknis/fungsional), dan Manager (kepemimpinan serta keputusan teknis/bisnis). Menambahkan sembilan variasi sudut, riwayat 35 pertanyaan milik pengguna/persona sama, dan satu retry untuk set yang tidak sesuai. Tidak menjamin variasi semantik tanpa batas.
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

## Deployment lokal Kiri

- Menambahkan `compose.kiri.yaml` dengan web, worker, PostgreSQL, Redis, volume persisten, dan healthcheck. Worker menunggu web sehat agar inisialisasi skema pertama tidak bersamaan.
- Menambahkan helper `deploy/kiri.sh`, pembuatan `.env.kiri` lokal dengan secret acak/mode `600`, dan panduan akses HTTPS `preptiva.kiri.local`.
- Domain mengikuti resolver/CA lokal Kiri; konteks Docker ditargetkan secara eksplisit ke `kiri`. Deployment SSH tetap dibatalkan sesuai instruksi pengguna.
- Verifikasi Kiri 0.1.18 berhasil: empat service healthy, HTTPS dipercaya Chrome/curl, autentikasi PostgreSQL, cookie aman, job arq, dan volume audio bersama. Pengujian tidak memanggil provider AI dan akun/file uji dibersihkan.

## Persiapan akses VM

- Membatasi izin private key lokal menjadi `400`, mengecualikan key dari Git/Docker, dan mengeluarkan key yang sudah terlacak dari index Git. Riwayat lama belum diubah.
- Menambahkan pembuat paket source dengan allowlist dan panduan deployment VM. Akses SSH target timeout pada port 22; belum ada deployment atau perubahan layanan remote.

## Konfigurasi dan pengujian provider

- Menghubungkan durasi per level, follow-up per panjang sesi, sakelar follow-up, dan retry dari `.env`; aturan sesi tersimpan dan divalidasi server.
- Mengaktifkan batas total waktu tanggapan LLM/TTS, format MP3 ElevenLabs, cache berdasarkan format, dan language code hanya untuk model yang mendukungnya.
- Menambahkan diagnostik provider yang aman dan pengujian timeout/retry, snapshot konfigurasi, format/cache audio, serta skrip uji API nyata dengan data sintetis dan database sementara.
- Verifikasi: 21 tes regresi lolos; sesi HR tiga pertanyaan berhasil dengan OpenAI/ElevenLabs nyata sampai hasil akhir. Ketiga voice ID dapat diakses. Ringkasan tanpa rahasia tersedia di `artifacts/live-smoke.json`.

- Menambahkan aplikasi FastAPI/SQLAlchemy, autentikasi, sesi UUID, integrasi OpenAI/ElevenLabs, dan worker arq/in-process.
- Menambahkan antarmuka Preptiva: dashboard, form, riwayat, ruang dengan pemeriksaan perangkat/rekaman/stream transkrip, dan hasil berbukti.
- Menambahkan snapshot rubrik, validasi dokumen, chunking, follow-up terbatas, skor berbobot, Docker, serta pengujian otomatis dengan provider terinjeksi.
- Perbedaan terhadap rancangan historis dan batas verifikasi dicatat di [status implementasi](implementation-status.md).

