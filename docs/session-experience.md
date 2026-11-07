# Persiapan perangkat, fokus sesi, dan waktu tunggu

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Diperbarui: 7 November 2026.

## Pemeriksaan sebelum mulai

Mode suara meminta izin kamera dan mikrofon. Mode teks dapat dipilih tanpa izin perangkat; pengguna tetap menyetujui aturan interupsi. Tombol Mulai Wawancara baru aktif setelah:

1. Kamera menghasilkan frame dan pengguna mengonfirmasi preview terlihat jelas.
2. Pengguna menekan Putar suara tes; browser membuka AudioContext dan memutar nada lokal tanpa panggilan API.
3. Pengguna mengonfirmasi nada terdengar. Browser tidak dapat membuktikan speaker benar-benar terdengar, sehingga konfirmasi manusia diperlukan.
4. Mikrofon mendeteksi sinyal saat pengguna berbicara. Meter menunjukkan level; ini tes sinyal, bukan verifikasi identitas atau isi ucapan. Bicara setelah menekan tombol tes suara jika meter belum aktif.
5. Pengguna menyetujui aturan perpindahan tab.

Pada desktop, daftar pemeriksaan dapat digulir di panel agar tombol Mulai tetap terjangkau.

Tes suara tidak memakai suara browser untuk menggantikan ElevenLabs. Preview kamera tidak diunggah. Rekaman jawaban menggunakan mono jika tersedia dan target bitrate 64 kbps; browser bisa menyesuaikan encoding.

## Tab ditinggalkan atau koneksi terputus

Sesuai keputusan pengguna 7 November 2026, yang dihentikan adalah **pertanyaan aktif**, bukan seluruh wawancara. `visibilitychange`, offline, perangkat terputus, atau pembukaan ulang ruang memicu pemulihan. Rekaman belum terkirim dibuang, timer dihentikan, audio dihentikan dan permintaan jawaban yang belum selesai dibatalkan.

Server menerima `/interrupt` dengan ID pertanyaan dan menyimpan checkpoint. Jika jawaban sudah terkomit sebelum interupsi sampai, jawaban dipertahankan; pertanyaan berikutnya tidak ikut dihentikan. Jika belum, tersedia **Retry** (pertanyaan sama, waktu penuh) dan **Next** (dilewati tanpa skor). Saat offline tombol menunggu sinkronisasi server setelah koneksi kembali. Membuka ulang sesi meminta pemeriksaan perangkat atau mode teks sebelum Retry/Next. Tombol **Akhiri sesi** secara eksplisit menutup seluruh sesi.

Deteksi browser bersifat best-effort, bukan proctoring. Koneksi yang macet mungkin baru terdeteksi setelah browser melaporkan kegagalan; dua jendela yang tetap visible tidak selalu memicu interupsi. Rekaman lokal yang belum dikirim tidak dapat dipulihkan setelah reload. Lihat [implementasi panel](panel-implementation.md).

## STT dan penampilan transkrip

Tetap menggunakan `STT_MODEL` saat ini (`gpt-4o-transcribe`); tidak ada realtime audio transcription atau pergantian model. Rekaman dikirim sesudah pengguna menekan Kirim.

`POST /api/sessions/{id}/answers?stream=true` mengembalikan NDJSON bertahap:

- `transcript`: segera setelah STT selesai. UI mengganti gelembung pending dengan teks asli.
- `pending`: heartbeat selama respons belum selesai.
- `result`: payload jawaban dengan keputusan giliran dan audio ElevenLabs jika tersedia. Audio boleh null; teks tetap dapat dipakai.
- `error`: pemrosesan gagal; pengguna dapat mengirim ulang.

Endpoint tanpa `stream=true` tetap mengembalikan JSON seperti sebelumnya. Streaming ini mengurangi waktu sampai transkrip terlihat, bukan menghilangkan waktu LLM/TTS. Filler audio tidak lagi menahan hasil AI. Rekaman ditargetkan 64 kbps untuk mengurangi ukuran upload; kualitas dan waktu nyata bergantung browser, jaringan, panjang rekaman, dan provider.

Respons streaming menyetel `X-Accel-Buffering: no` dan `Cache-Control: no-store`; proxy lain harus meneruskan chunk tanpa buffering. Pemutus koneksi membatalkan task stream yang belum selesai. Retry setelah commit mengembalikan hasil tersimpan, bukan merekam jawaban kedua.

Lihat [logging.md](logging.md) untuk membedakan latensi STT, LLM, TTS, dan penilaian background.

## Fullscreen dan mirror

Fullscreen opsional tersedia melalui pilihan sebelum Mulai dan tombol toolbar. Browser memerlukan tindakan pengguna. Jika tidak didukung atau ditolak, sesi tetap dapat berjalan. Keluar fullscreen (misalnya Escape) bukan pelanggaran dan tidak menutup sesi. Fullscreen tidak dapat mencegah pengguna berpindah tab/OS; aturan halaman hidden tetap berlaku setelah mulai.

Mirror kamera tersedia di form dan ruang wawancara, default non-mirror agar teks pada pakaian/latar tidak terbalik. Pilihan lokal dipertahankan melalui sessionStorage. Transform hanya diterapkan ke elemen video preview; logo aplikasi, ikon, dan label tidak dicerminkan. Ini tampilan lokal dan tidak mengubah audio atau proses penilaian.

Bahasa wawancara dan fokus persona dijelaskan di [languages-and-personas.md](languages-and-personas.md). URL sesi sekarang menggunakan UUID; buka sesi lama lewat Riwayat agar memakai tautan baru.

## Transisi pertanyaan terakhir

Ketika aksi next pada pertanyaan utama terakhir (termasuk setelah follow-up terakhir), tanggapan dibersihkan dari ajakan meneruskan pertanyaan dalam Indonesia/English sebelum audio dibuat, lalu UI memutar penutup. Pada pertanyaan lain transisi lanjut tetap diizinkan. Jawaban yang sudah tersimpan bersifat idempotent dan tidak ditulis ulang otomatis.

## Bahasa jawaban, penutup dan hasil

Jawaban dominan dalam bahasa lain yang terdeteksi pasti memicu pengingat teks/suara untuk mengulang di pertanyaan sama dengan timer penuh. Tidak mengurangi tambahan kuota rekaman/follow-up dan tidak memanggil finish. Wawancara berakhir dengan penutup yang menyatakan hasil akan diproses, tanpa mengajak kandidat bertanya. Nilai/feedback tampil otomatis setelah finalisasi; transkrip terbuka dan ikut PDF. Detail: [bahasa](languages-and-personas.md), [hasil](results.md).
