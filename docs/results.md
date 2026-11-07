# Hasil wawancara

Halaman `/sesi/{uuid}/hasil` memakai shell dashboard/riwayat: navigasi horizontal, DM Sans, lebar konten 1160 px, latar netral dan aksi oranye. Sidebar hasil versi lama tidak lagi ditampilkan.

- Skor /100, ringkasan, perubahan terhadap sesi sebanding, cakupan bukti dan jumlah jawaban menjadi ringkasan utama.
- Hasil panel menampilkan nama dan skor tiap pewawancara. Skor null tetap ditampilkan sebagai belum terukur.
- Kompetensi, kekuatan dan perbaikan dipisahkan; kutipan bukti, STAR, alasan rekomendasi dan rincian tiap jawaban dapat dibuka melalui disclosure native.
- Transkrip, follow-up, pertanyaan dilewati, status bukti, rubrik historis, serta indikator dan sumber rubrik EM tetap berasal dari API yang sama. Status draf/belum divalidasi tetap terlihat.
- Loading, kegagalan, hasil belum tersedia dan tombol penilaian ulang tetap ditangani `loadResult` di `app.js`; tidak ada perubahan backend atau pemicu penilaian otomatis baru.

Markup shell: `partials/result.html`. Renderer: `static/js/result.js`, dimuat sebelum `app.js`; memakai helper escaping dan bukti yang sudah ada. Style: `static/css/result.css`, terbatas pada halaman hasil.

Arah visual: ENERGY 1 / RHYTHM 1 / MOTION 1. Ring skor menjadi fokus utama, pemisah membedakan kelompok informasi, dan accordion menjaga rincian tetap tersedia tanpa memenuhi tampilan awal.

Verifikasi perubahan ini dibatasi pada syntax/diff, helper rubrik Node, dan satu pemeriksaan Chrome dengan payload sintetis: panel, skor null, bukti/rubrik khusus, keyboard, state penilaian tertunda, serta viewport 320/390/768/1440 px. Seluruh mutasi API diblokir; tidak ada provider atau data sesi asli yang diubah. Browser non-Chromium dan screen reader belum diuji.
