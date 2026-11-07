# Hasil wawancara

## Visibilitas kompetensi berdasarkan catatan evaluasi

Atas pilihan tampilan pengguna, kartu dengan key `teamwork` disembunyikan meski memiliki catatan evaluasi. Ini mencakup nama khusus untuk key tersebut pada profil EM. Data, rincian bukti jawaban, perhitungan skor dan denominator cakupan tetap dipertahankan; filter hanya berlaku pada daftar kartu kompetensi.

UI menyembunyikan placeholder rubrik dengan `status: not_assessed`, tanpa skor, unit penilaian atau bukti. Kompetensi tetap tampil jika ada skor numerik valid, `assessed_units > 0`, status evaluasi (`measured`, `insufficient`, `unusable_transcript`), kutipan atau referensi sumber. Dengan demikian bukti terbatas tetap terlihat meski skor null; ketiadaan skor saja tidak menjadi alasan menyembunyikan hasil. Jika seluruh kompetensi belum dinilai, tampilkan keadaan kosong. Ini hanya filter presentasi; API, data tersimpan, skor, bobot dan denominator cakupan tidak diubah.

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Halaman `/sesi/{uuid}/hasil` memakai shell dashboard/riwayat: navigasi horizontal, DM Sans, lebar konten 1160 px, latar netral dan aksi oranye. Sidebar hasil versi lama tidak lagi ditampilkan.

- Skor /100, ringkasan, perubahan terhadap sesi sebanding, cakupan bukti dan jumlah jawaban menjadi ringkasan utama.
- Hasil panel menampilkan nama dan skor tiap pewawancara. Skor null tetap ditampilkan sebagai belum terukur.
- Kompetensi, kekuatan dan perbaikan dipisahkan; transkrip dan feedback tiap jawaban terbuka secara default dan tetap dapat ditutup melalui disclosure native. Kutipan bukti, STAR dan alasan rekomendasi juga tersedia melalui disclosure.
- Transkrip, follow-up, pertanyaan dilewati, status bukti, rubrik historis, serta indikator dan sumber rubrik EM tetap berasal dari API yang sama. Status draf/belum divalidasi tetap terlihat.
- Loading, kegagalan, hasil belum tersedia dan tombol penilaian ulang tetap ditangani `loadResult` di `app.js`; tidak ada perubahan backend atau pemicu penilaian otomatis baru.

Markup shell: `partials/result.html`. Renderer: `static/js/result.js`, dimuat sebelum `app.js`; memakai helper escaping dan bukti yang sudah ada. Style: `static/css/result.css`, terbatas pada halaman hasil.

Arah visual: ENERGY 1 / RHYTHM 1 / MOTION 1. Ring skor menjadi fokus utama dan pemisah membedakan kelompok informasi. Jawaban asli langsung terlihat agar hasil tidak tampak hanya berisi pertanyaan.

## Perbaikan visibilitas jawaban dan cetak — 7 November 2026

- Transkrip serta feedback jawaban terbuka saat halaman hasil dimuat. Jika skor total null, rincian alasan penilaian juga dibuka dan penjelasan Indonesia/Inggris menyatakan bahwa bukti belum cukup untuk skor terukur; tanda — bukan nilai nol.
- Sebelum print/PDF, seluruh disclosure hasil dibuka, termasuk yang ditutup pengguna. Setelah pencetakan, status buka/tutup sebelumnya dipulihkan. Style print menyederhanakan layout dan menyembunyikan skip-link/navigasi yang tidak relevan.
- Kebijakan skor, ambang bukti, data tersimpan dan API tidak diubah. Perbaikan tampilan tidak mengubah skor null menjadi angka atau mengklaim hasil sudah dinilai ulang.
- Verifikasi: `tests/result_visibility_smoke.py` memakai renderer asli dengan data sintetis pada lebar 390/1440 px, menguji transkrip/feedback, escaping, alasan skor null, pertanyaan dilewati, pemulihan disclosure dan isi PDF. Tidak mengakses sesi pengguna atau memakai kredit AI.

## Bahasa hasil dan akhir wawancara

Saat sesi dibuat, browser mengirim bahasa platform sebagai `feedback_language` (`id`/`en`). Bahasa ini disimpan pada snapshot `script.settings`, terpisah dari `language` untuk pertanyaan/STT. Evaluasi per jawaban, rationale/gap, tinjauan perbedaan panel dan ringkasan akhir diarahkan mengikuti bahasa hasil tersebut pada jalur legacy maupun LangGraph. Sesi lama tanpa field baru mengikuti bahasa wawancaranya; laporan yang sudah tersimpan tidak diterjemahkan atau dinilai ulang otomatis.

Label UI tetap mengikuti pemilih bahasa website. Mengganti bahasa website setelah sesi dimulai tidak mengubah bahasa feedback AI yang sudah disnapshot. Kutipan/transkrip asli dan teks indikator snapshot tetap dipertahankan untuk keterlacakan; tidak diterjemahkan sebagai bukti baru.

Penilaian berjalan setelah finalisasi; ringkasan merupakan akhir percakapan, bukan pertanyaan berikutnya. Model diperintahkan memberi penjelasan langsung dan tindakan latihan. Validasi feedback/ringkasan menolak keluaran berbentuk pertanyaan dengan tanda tanya dan memberi satu kesempatan perbaikan. Jika tetap gagal, jalur pemulihan evaluasi yang ada digunakan. Ini tidak menonaktifkan pertanyaan utama/follow-up saat wawancara sedang berlangsung. Pemeriksaan tanda tanya bukan pengenal sempurna semua kalimat tanya; kualitas bahasa model tetap perlu uji nyata.

Verifikasi tambahan: tes kebijakan bahasa dan feedback tanpa pertanyaan, penyimpanan bahasa hasil terpisah pada API, regresi finalisasi graph/rubrik, serta label Indonesia/Inggris di browser. Provider AI ditiru dalam tes; belum ada evaluasi ulang pada sesi produksi.

Verifikasi perubahan ini dibatasi pada syntax/diff, helper rubrik Node, dan satu pemeriksaan Chrome dengan payload sintetis: panel, skor null, bukti/rubrik khusus, keyboard, state penilaian tertunda, serta viewport 320/390/768/1440 px. Seluruh mutasi API diblokir; tidak ada provider atau data sesi asli yang diubah. Browser non-Chromium dan screen reader belum diuji.

## Hasil sesudah koreksi bahasa jawaban

Respons `language_retry` bukan jawaban penilaian dan tidak masuk daftar jawaban/coverage hasil. Hanya jawaban yang diterima yang dipakai finalisasi. Deteksi bahasa tidak menghasilkan penalti kompetensi atau skor nol. Bahasa feedback hasil tetap mengikuti snapshot dari platform, terpisah dari bahasa pengingat selama wawancara.
