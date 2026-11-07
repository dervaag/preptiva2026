# Status implementasi brief panel

Diperbarui 7 November 2026. Acuan tambahan: berkas pengguna `preptiva_panel_interview_brief.md`, versi usulan `2026-11-07.1`. Isi brief diperlakukan sebagai rancangan produk. Keputusan pengguna setelah membaca brief mengganti usulan resume: **pindah tab atau koneksi putus menghentikan pertanyaan aktif; pengguna memilih Retry atau Next**. Tidak otomatis melanjutkan sisa rekaman/waktu.

## Perilaku yang diterapkan

- Satu pembicara aktif, panel HR/User/Manager dan kompetensi tetap mengikuti snapshot sesi.
- Waktu/rekaman pertanyaan aktif dihentikan saat browser mendeteksi tab tersembunyi, offline, perangkat terputus, atau reload. Server menyimpan checkpoint `interrupted`, ID interupsi dan sisa waktu nol. Retry mengulang pertanyaan yang sama dengan waktu penuh; Next melewati pertanyaan tanpa menganggap kemampuan kandidat rendah. Retry interupsi tidak memakai kuota rekam ulang dalam satu percobaan.
- Jawaban yang sudah berhasil disimpan tetap dipertahankan. Interupsi terlambat terhadap jawaban tersebut tidak menghentikan pertanyaan berikutnya. Pengiriman ulang Next/Retry memakai ID pertanyaan/interupsi untuk mencegah giliran ganda.
- Ketika benar-benar offline, status lokal segera menghentikan rekaman; tombol pemulihan aktif setelah status server berhasil disinkronkan. Rekaman yang belum dikirim dibuang. Deteksi offline browser bersifat best-effort; koneksi putus saat pengiriman juga memicu pemulihan ketika terdeteksi.
- Membuka ulang sesi meminta pemeriksaan perangkat atau mode teks, kemudian menawarkan Retry/Next pada pertanyaan yang belum selesai. Tombol Akhiri sesi tetap menutup keseluruhan sesi.
- Kegagalan TTS menghasilkan pertanyaan/tanggapan teks. Mode teks tidak memerlukan kamera/mikrofon. Tombol Hentikan suara menghentikan pemutaran; ini kontrol manual, belum deteksi interupsi suara otomatis.

## Konteks dan bukti

`app/ai/memory.py` membentuk paket dialog dengan maksimal 14.000 karakter JSON: tiga giliran terbaru, maksimal tiga giliran lama yang relevan, indeks giliran lama, kutipan klaim kandidat dan status cakupan pertanyaan. Pemilihan memakai kecocokan kompetensi/kata, tanpa pgvector. Kalimat dipilih sebagai kutipan; jika kalimat tunggal terlalu panjang, dipakai bagian kontinu pada batas kata dan ditandai sebagai cuplikan. Transkrip asli tidak dipotong atau ditimpa di database. Ini anggaran karakter untuk **paket dialog**, bukan jaminan jumlah token seluruh prompt: konteks CV/JD/rubrik merupakan bagian terpisah.

ID giliran `q<question_id>` stabil karena setiap pertanyaan hanya menerima satu jawaban tersimpan. Klaim kandidat tetap `unverified`. Setiap adaptasi/follow-up dengan jawaban tersedia wajib menyertakan setidaknya satu ID giliran dan kutipan literal dalam paket. Rujukan model ke percakapan lama harus memakai ID yang ada dalam paket serta kutipan literal yang tersedia. Validator menolak ID/kutipan buatan; relevansi semantik rujukan masih memerlukan tinjauan. Ringkasan naratif bergulir belum ditambahkan; indeks terstruktur dan retrieval digunakan agar tidak mengubah fakta asli.

Evaluator terpisah memproses pertanyaan utama dan follow-up sebagai satu unit. Setiap kutipan skor dipetakan kembali ke transkrip satu giliran beserta offset karakter; kutipan yang dirangkai melintasi giliran ditolak. Status:

| Status | Arti dan pengaruh |
| --- | --- |
| `measured` | Bukti dinilai cukup; skor ikut agregat, termasuk skor rendah yang punya bukti |
| `insufficient` | Bukti belum cukup; skor sementara disimpan tetapi tidak masuk agregat |
| `not_assessed` | Belum ditanya atau pertanyaan dilewati; tidak diberi skor |
| `unusable_transcript` | Teks tidak memiliki konten yang dapat digunakan; tidak masuk agregat |

Tanpa kutipan valid, skor sementara tetap dibatasi maksimal 2. Kecukupan bukti dengan kutipan merupakan keluaran model, bukan validasi asesor. Confidence STT tidak disediakan oleh jalur saat ini dan dicatat `unknown`; aplikasi tidak mengarang tingkat kepastian dari aksen/kecepatan suara. Halaman hasil memisahkan cakupan bukti dari skor dan menampilkan asal kutipan. Ringkasan AI menerima cakupan agar bukti kurang tidak dirangkum sebagai kelemahan yang terbukti.

## Penyimpanan dan kegagalan

Tabel baru `interview_events` mencatat event domain dengan unique key `(session_id, event_key)` dan cascade saat sesi dihapus. Inisialisasi skema yang sudah ada membuat tabel secara aditif; tidak mengubah kolom, bobot, atau rubrik historis. `script.checkpoint` menyimpan keadaan terbaru, sedangkan jawaban asli dan bukti tetap di tabel jawaban. `script.runtime` menyimpan versi orchestration serta nama model, tanpa kredensial.

Transaksi/row lock PostgreSQL menyerialkan perubahan giliran; SQLite lokal memakai lock proses untuk alur jawaban/pemulihan. Satu event jawaban, checkpoint, perubahan pertanyaan dan jawaban dikomit bersama. Penilaian juga dikunci dan dikomit atomik. Jika evaluator/antrean gagal, jawaban tetap ada dan status `evaluation_failed` menyediakan tombol Nilai ulang. Rubrik sesi lama tetap menggunakan versi/hash/bobot yang telah disimpan. Perbandingan riwayat juga memeriksa versi kebijakan bukti.

## Bagian brief yang belum selesai

| Bagian | Status |
| --- | --- |
| Persona, blueprint, adaptive next, handoff | Sudah ada; ditambah konteks terbatas dan sumber giliran |
| Riwayat event, checkpoint, Retry/Next, idempotensi | Diimplementasikan sesuai koreksi pengguna |
| Bukti kutipan, cakupan, pemulihan evaluasi | Diimplementasikan; kualitas semantik belum dikalibrasi asesor |
| Ringkasan naratif bergulir dan routing berdasarkan waktu sesi total | Belum; indeks/retrieval dan jumlah pertanyaan tetap digunakan |
| Streaming STT/TTS, VAD, barge-in suara otomatis | Belum; audio masih per rekaman/utterance, tersedia penghentian manual dan mode teks |
| Koreksi transkrip tersimpan dengan jejak revisi | Belum; jawaban teks tersedia sebagai alternatif, bukan edit transkrip historis |
| Metrik end-of-turn hingga suara pertama, dashboard kualitas/biaya | Belum; log komponen yang sudah ada tetap tersedia |
| Kalibrasi asesor, fairness, stabilitas pada gold set | Alat pembandingan disiapkan; data penilaian manusia belum tersedia |

Lihat [persiapan validasi asesor](assessor-validation.md) dan [rencana rubrik](rubric-validation-plan.md). Tidak ada perubahan ke `validated: true`.
