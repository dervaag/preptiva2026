# Persiapan perangkat, fokus sesi, dan waktu tunggu

Diperbarui: 5 November 2026.

## Pemeriksaan sebelum mulai

Ruang wawancara meminta izin kamera dan mikrofon. Tombol Mulai Wawancara baru aktif setelah:

1. Kamera menghasilkan frame dan pengguna mengonfirmasi preview terlihat jelas.
2. Pengguna menekan Putar suara tes; browser membuka AudioContext dan memutar nada lokal tanpa panggilan API.
3. Pengguna mengonfirmasi nada terdengar. Browser tidak dapat membuktikan speaker benar-benar terdengar, sehingga konfirmasi manusia diperlukan.
4. Mikrofon mendeteksi sinyal saat pengguna berbicara. Meter menunjukkan level; ini tes sinyal, bukan verifikasi identitas atau isi ucapan. Bicara setelah menekan tombol tes suara jika meter belum aktif.
5. Pengguna menyetujui aturan perpindahan tab.

Pada desktop, daftar pemeriksaan dapat digulir di panel agar tombol Mulai tetap terjangkau.

Tes suara tidak memakai suara browser untuk menggantikan ElevenLabs. Preview kamera tidak diunggah. Rekaman jawaban menggunakan mono jika tersedia dan target bitrate 64 kbps; browser bisa menyesuaikan encoding.

## Tab ditinggalkan

Setelah tombol Mulai Wawancara ditekan, `visibilitychange` (halaman hidden) atau `pagehide` menutup sesi. Berpindah tab, meminimalkan browser, mengunci layar pada sebagian perangkat, atau navigasi keluar dapat memicu ini. Persiapan sebelum mulai dan halaman hasil tidak memicu aturan.

Pemutar dan perekam dihentikan, track perangkat dilepas, permintaan jawaban dibatalkan, dan browser mengirim `POST /api/sessions/{id}/close` melalui beacon/keepalive. Sesi aktif menjadi `failed` dengan alasan penutupan; tidak bisa dijawab atau dilanjutkan. Hasil sesi yang sudah selesai tidak diubah. Penutupan tidak memberikan nilai kompetensi nol.

Browser umumnya menolak `window.close()` untuk tab yang dibuka manual; aplikasi menutup sesi lalu mengarahkan halaman ke Riwayat. Ini kontrol UX berbasis browser, bukan sistem proctoring yang tahan manipulasi. Gangguan jaringan, browser crash, atau JavaScript yang dinonaktifkan bisa menggagalkan notifikasi server. Marker lokal mencoba mengirim ulang penutupan ketika ruang yang sama dibuka kembali. Tumpang tindih dua jendela yang tetap visible tidak selalu terdeteksi.

## STT dan penampilan transkrip

Tetap menggunakan `STT_MODEL` saat ini (`gpt-4o-transcribe`); tidak ada realtime audio transcription atau pergantian model. Rekaman dikirim sesudah pengguna menekan Kirim.

`POST /api/sessions/{id}/answers?stream=true` mengembalikan NDJSON bertahap:

- `transcript`: segera setelah STT selesai. UI mengganti gelembung pending dengan teks asli.
- `pending`: heartbeat selama respons belum selesai.
- `result`: payload jawaban yang sudah menyertakan keputusan giliran dan audio ElevenLabs.
- `error`: pemrosesan gagal; pengguna dapat mengirim ulang.

Endpoint tanpa `stream=true` tetap mengembalikan JSON seperti sebelumnya. Streaming ini mengurangi waktu sampai transkrip terlihat, bukan menghilangkan waktu LLM/TTS. Filler audio tidak lagi menahan hasil AI. Rekaman ditargetkan 64 kbps untuk mengurangi ukuran upload; kualitas dan waktu nyata bergantung browser, jaringan, panjang rekaman, dan provider.

Respons streaming menyetel `X-Accel-Buffering: no` dan `Cache-Control: no-store`; proxy lain harus meneruskan chunk tanpa buffering. Pemutus koneksi membatalkan task stream yang belum selesai. Retry setelah commit mengembalikan hasil tersimpan, bukan merekam jawaban kedua.

Lihat [logging.md](logging.md) untuk membedakan latensi STT, LLM, TTS, dan penilaian background.

## Fullscreen dan mirror (5 November 2026)

Fullscreen opsional tersedia melalui pilihan sebelum Mulai dan tombol toolbar. Browser memerlukan tindakan pengguna. Jika tidak didukung atau ditolak, sesi tetap dapat berjalan. Keluar fullscreen (misalnya Escape) bukan pelanggaran dan tidak menutup sesi. Fullscreen tidak dapat mencegah pengguna berpindah tab/OS; aturan halaman hidden tetap berlaku setelah mulai.

Mirror kamera tersedia di form dan ruang wawancara, default non-mirror agar teks pada pakaian/latar tidak terbalik. Pilihan lokal dipertahankan melalui sessionStorage. Transform hanya diterapkan ke elemen video preview; logo aplikasi, ikon, dan label tidak dicerminkan. Ini tampilan lokal dan tidak mengubah audio atau proses penilaian.

Bahasa wawancara dan fokus persona dijelaskan di [languages-and-personas.md](languages-and-personas.md). URL sesi sekarang menggunakan UUID; buka sesi lama lewat Riwayat agar memakai tautan baru.

## Transisi pertanyaan terakhir

Ketika aksi next pada pertanyaan utama terakhir (termasuk setelah follow-up terakhir), tanggapan dibersihkan dari ajakan meneruskan pertanyaan dalam Indonesia/English sebelum audio dibuat, lalu UI memutar penutup. Pada pertanyaan lain transisi lanjut tetap diizinkan. Jawaban yang sudah tersimpan bersifat idempotent dan tidak ditulis ulang otomatis.
