# Ruang wawancara

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Koreksi bahasa jawaban: event hasil dengan `action: language_retry` menampilkan/membacakan permintaan mengulang dalam bahasa wawancara, lalu mengembalikan kontrol ke pertanyaan yang sama dengan timer penuh. Tidak memanggil finish, tidak mengonsumsi retry rekaman tambahan, dan tidak membuat follow-up. Jawaban belum menjadi unit penilaian sampai dikirim dalam bahasa yang diterima. Rincian deteksi konservatif: [bahasa dan persona](languages-and-personas.md).

Halaman `/sesi/{session_id}/ruang` memakai layout meeting: pewawancara besar, preview kandidat di sudut, percakapan di kanan, dan toolbar bawah. Pada ponsel percakapan berada di bawah stage. Layar pendek dapat di-scroll agar kontrol tetap terjangkau.

Revisi modal mengikuti masukan pemilik proyek: judul singkat `Cek perangkat`, preview di kiri, empat baris pemeriksaan tanpa kotak ikon di kanan, persetujuan singkat di bawah, serta satu catatan privasi di footer. Eyebrow, subtitle, badge AI, motivasi empty state, dan informasi progres/privasi yang berulang di ruang dihapus. Identitas AI tetap terlihat pada nama peran pewawancara. Pesan perangkat mobile dipadatkan menjadi arahan PC/laptop.

## Arah visual

Referensi meeting diberikan pemilik proyek. DM Sans dan oranye mengikuti logo serta form simulasi baru. Panel putih dan latar netral memisahkan percakapan dari video; label gelap menjaga teks di atas background kantor tetap terbaca. Ikon memakai bentuk SVG perangkat yang sama dengan form. ENERGY 1 / RHYTHM 1 / MOTION 2: gerak dibatasi pada ekspresi pewawancara, indikator audio, dan countdown yang diminta.

Rina, Andi, dan Pak Hendra memakai karakter 3D orisinal hasil `image_gen` bawaan, masing-masing sprite RGBA 1254 x 1254 dengan empat frame: idle, kedip, bicara kecil, dan bicara lebar. Background kantor 1672 x 941 dipisahkan dari karakter. Aset berada di `app/static/images/interviewers/`. Prompt dan pemetaan frame dicatat di `interview-room-assets.json`.

Ekspresi mulut mengikuti amplitudo audio yang sedang diputar melalui Web Audio, dengan ritme perkiraan jika analyser tidak tersedia. Ini animasi sprite, bukan avatar video atau sinkronisasi fonem. Kedip dan idle halus memberi tanda karakter sedang hadir. Pengaturan Animasi karakter dapat mematikannya; preferensi reduced motion mematikannya secara default.

## Perilaku

- Sesi `ready` membuka modal pemeriksaan tanpa otomatis memulai atau menutup sesi.
- Wawancara wajib memakai PC atau laptop. HP/tablet, termasuk iPad dengan mode desktop, menerima pesan untuk membuka tautan sesi yang sama di PC/laptop; akses kamera/mikrofon dan Mulai diblokir. Pemeriksaan memakai identitas browser dan karakteristik iPad, bukan lebar viewport, sehingga laptop layar sentuh dan jendela desktop kecil tetap didukung. Identitas browser yang sengaja dipalsukan bukan jaminan identifikasi perangkat.
- Mode suara memerlukan video aktif dengan frame, mikrofon aktif dengan sinyal terdeteksi, suara tes selesai, konfirmasi manusia untuk kamera/speaker, persetujuan aturan fokus, serta pemeriksaan koneksi aplikasi yang masih baru. Level mikrofon mendeteksi sinyal, bukan menguji pemahaman ucapan. Mode teks dapat dipilih tanpa kamera/mikrofon, tetapi tetap wajib PC/laptop dan koneksi aplikasi. Fullscreen opsional.
- Panel memakai 2–3 persona yang sudah ada. Nama anggota dan penanda pewawancara aktif mengikuti metadata backend pada setiap giliran, termasuk respons dan pertanyaan lanjutan. Jumlah peserta mencakup kandidat; tiga pewawancara berarti empat peserta.
- Setelah POST start berhasil, overlay menghitung 3, 2, 1 sebelum intro dan pertanyaan. Klik ganda tidak mengirim start kedua.
- Rekaman jawaban tetap memakai API dan batas waktu/retry sesi. Audio dapat ditinjau atau direkam ulang; mematikan mikrofon saat merekam menghentikan rekaman untuk ditinjau, tanpa mengirimnya.
- Chat menampilkan pertanyaan dan transkrip aktual dari stream respons. Transkrip awal diperbarui oleh hasil akhir tanpa duplikasi, termasuk ketika upload diulang. Follow-up yang sama diputar sekali.
- Sesuai referensi DM dari pemilik proyek, pesan pewawancara memakai bubble putih di kiri dan jawaban kandidat biru di kanan. Lebar bubble mengikuti isi, pesan berurutan dikelompokkan, dan nama tetap tersedia untuk pembaca layar. Indikator respons mengikuti proses upload/AI yang sedang berlangsung. Transkrip memperbarui bubble yang sama; tidak ada tanda dibaca atau jeda mengetik buatan. Animasi masuk singkat dan indikator menghormati reduced motion.
- Subtitle, chat, mirror, fullscreen, dan animasi memiliki kontrol sendiri. Menyembunyikan chat tetap menyisakan tombol menjawab di bawah stage.
- Kegagalan upload menawarkan kirim ulang. Kegagalan audio menawarkan lanjutkan percakapan tanpa mengulang ucapan yang sudah selesai.
- Perpindahan tab, koneksi terputus, dan reload menghentikan pertanyaan aktif melalui checkpoint backend. Pengguna memilih Retry untuk mengulang atau Next untuk melewati pertanyaan tanpa penilaian. Keluar secara eksplisit melalui toolbar tetap memakai konfirmasi dan menutup sesi. Sebelum mulai, navigasi hanya membersihkan perangkat.
- Navigasi menghentikan seluruh track, recorder, analyser, timer, animasi, object URL, dan operasi media yang terlambat. Back-forward cache meminta verifikasi ulang; permintaan state awal yang terputus dimuat kembali.
- Kamera hanya preview lokal. Audio atau jawaban teks dikirim ketika pengguna menekan Kirim. Audio yang tidak tersedia tidak menghalangi pertanyaan teks; pengguna juga dapat menghentikan suara.

## File dan verifikasi

Markup ada di `app/templates/partials/interview-room.html`, ikon di `meeting-icons.html`, style terbatas halaman di `app/static/css/interview-room.css`, dan controller di `app/static/js/interview-room.js`. `app/templates/app.html` memilih shell khusus ruang. API start di `app/api/sessions.py` juga menolak sinyal mobile dari User-Agent, client hints, atau header perangkat dengan HTTP 403 sebelum mengubah status sesi. Integrasi panel menggunakan API `/interrupt`, `/recover`, metadata persona per pertanyaan, serta hasil penilaian berbasis bukti dari pembaruan backend.

```sh
.venv/bin/python -m unittest discover -s tests -q
node tests/room_controller_test.cjs app/static/js/interview-room.js
.venv/bin/python tests/room_smoke.py
```

Tes controller memeriksa blokir mobile/tablet, dukungan laptop Windows layar sentuh, lifecycle perangkat, countdown, start tunggal, deduplikasi stream/follow-up, mute saat merekam, recovery audio, finish, dan pemulihan halaman. Smoke test memeriksa HP, tablet Android, serta iPad mode desktop dengan UI/API yang ditolak tanpa memulai sesi, lalu menjalankan desktop sampai hasil empat jawaban termasuk follow-up dengan database sementara, provider tiruan, kamera serta mikrofon sintetis. Viewport desktop 320 sampai 1440 px dan layar pendek 320x480, 720x390, 1024x390 diperiksa; halaman dapat digulir menuju toolbar.

Kontras terukur pada pasangan utama: teks muted di putih 5.51:1, CTA oranye 6.03:1, tombol keluar 4.59:1, dan fokus di latar halaman 6.09:1. Perangkat fisik, provider berbayar pada perubahan ini, browser non-Chromium, dan screen reader belum diuji. Pengujian tidak memulai atau menutup sesi asli milik pengguna.
