# Audio realtime dan VAD

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Sesi baru dengan `REALTIME_VOICE_ENABLED=true` memakai transkripsi audio bertahap dan TTS streaming. Sesi lama mengikuti snapshot saat dibuat. Kunci API tetap di server; `.env` yang sudah diisi tidak perlu diganti. PostgreSQL dan Redis tetap dipakai seperti sebelumnya.

## Alur pengguna

1. Pada **Cara menjawab** di preflight, hanya **Rekam suara** yang ditampilkan; kartu **Ketik jawaban** disembunyikan. Aktifkan kamera/mikrofon dan lakukan pemeriksaan perangkat. Kemampuan beralih ke teks selama sesi tetap tersedia. **Transkrip realtime** aktif secara default; klik **Mulai rekam suara** untuk mengirim audio mikrofon. Transkrip muncul selama berbicara.
2. Klik Selesai bicara. Tinjau dan, jika perlu, koreksi transkrip sebelum Kirim jawaban. Teks asli hasil STT tetap disimpan bersama teks koreksi dan event revisi. Ini koreksi sebelum pengiriman, bukan pengubahan jawaban historis.
3. Opsi **Kirim otomatis setelah jeda** dimatikan secara default. Bila dipilih, VAD mendeteksi jeda 1.200 ms, lalu browser menunggu 1.800 ms tambahan. Bicara lagi membatalkan hitungan tambahan. Pengiriman otomatis melewati peninjauan; gunakan pengiriman manual jika ingin selalu memeriksa transkrip.
4. Opsi **Sela suara interviewer** juga dimatikan secara default. Bila dipilih, aktivitas mikrofon lokal sekitar 400 ms dapat menghentikan pembacaan pertanyaan dan mulai menangkap jawaban dengan prarekaman lokal hingga 400 ms. Gunakan headphone: detektor energi lokal tidak bisa memastikan suara berasal dari kandidat, bukan speaker/noise. Tombol Hentikan suara tetap tersedia.
5. Pindah tab, offline, reload, atau perangkat putus menghentikan pertanyaan aktif. Retry mengulang dengan waktu penuh; Next melewati tanpa skor. Audio/transkrip yang belum dikirim pada percobaan itu dibuang. Jawaban tersimpan tetap dipertahankan.

Jika transport realtime/provider gagal, UI menawarkan rekaman biasa atau jawaban teks. Kegagalan suara interviewer tetap menyisakan teks pertanyaan/tanggapan. HTTPS atau localhost diperlukan untuk kamera, mikrofon, dan AudioWorklet.

Saat mode teks aktif, tombol **Gunakan mikrofon** dapat mengembalikan jawaban ke suara dalam pertanyaan yang sama. Jika belum aktif, browser meminta izin mikrofon; kamera tidak diwajibkan untuk perpindahan ini. Setelah berhasil, klik **Mulai rekam suara**. Pilihan mode berlaku juga pada pertanyaan berikutnya. Draf teks dan rekaman selesai tetap tersedia ketika berganti mode pada pertanyaan yang sama, tetapi tidak disimpan sebagai draf setelah reload atau Retry. Izin ditolak mempertahankan mode teks. Izin yang datang setelah tab/offline menghentikan pertanyaan tidak dapat membuka kembali kontrol jawaban; gunakan Retry/Next.

## Transport dan konfigurasi

```dotenv
REALTIME_VOICE_ENABLED=true
VAD_SILENCE_MS=1200
VAD_THRESHOLD=0.5
STT_MODEL=gpt-4o-transcribe
```

Batas konfigurasi: jeda 500–3.000 ms, threshold 0,1–0,95. Model STT dan model/voice ElevenLabs yang sudah dikonfigurasi tetap digunakan. Flag realtime dibaca saat startup dan disnapshot pada sesi baru; perlu restart/redeploy setelah perubahan environment. Pengiriman otomatis dan sela suara adalah pilihan browser, bukan pengaturan global yang dipaksakan.

AudioWorklet mengirim PCM16 mono 24 kHz melalui WebSocket `/api/sessions/{sid}/voice/{qid}` ke server, yang meneruskan ke OpenAI Realtime transcription. Server menerapkan kepemilikan sesi, pemeriksaan Origin, pertanyaan aktif, satu lease capture per sesi, batas durasi/ukuran dan timeout. Event commit menentukan urutan segmen; completion STT yang tiba tidak berurutan tidak mengubah urutan jawaban. Finish mematikan VAD dengan acknowledgement barrier, commit sisa audio, lalu menunggu seluruh segmen final.

Hasil final diberi token bertanda tangan yang berlaku sepuluh menit dan terikat pada pengguna, sesi, pertanyaan serta percobaan Retry. Jawaban diterima lewat endpoint jawaban yang sama, tanpa STT kedua. Raw audio kandidat tidak disimpan. Tab/offline/retry membatalkan capture; lease lama dibersihkan tanpa menghapus lease percobaan yang lebih baru.

Endpoint GET `/speech/{kind}/{id}` hanya membaca teks milik sesi, tidak menerima teks bebas atau membocorkan pertanyaan masa depan. Server meneruskan chunk MP3 ElevenLabs saat tersedia. Cache dipromosikan atomik hanya setelah stream selesai; pembatalan membersihkan file sementara. Pemutaran dihentikan ketika pertanyaan terinterupsi. Nginx contoh sudah meneruskan Upgrade WebSocket; proxy lain juga harus mengizinkan WSS dan streaming response.

Event `voice_first_playing` mencatat selisih waktu browser dari Selesai bicara/pengiriman otomatis hingga event `playing` audio tanggapan. Pada mode manual, waktu meninjau transkrip ikut terhitung. Metrik ini dilaporkan klien, tidak dipercaya untuk penilaian, dan dicatat sekali per jawaban. Ini bukan TTFT model atau jaminan latensi produksi; dashboard distribusi latensi/biaya belum dibuat.

## Pemeriksaan

- `python -m unittest discover -s tests -v`: receipt/correction/ownership/idempotensi, lease Retry, urutan transkrip, cache streaming dan paket asesor; provider tiruan.
- `python tests/realtime_browser_smoke.py`: Chrome dan mikrofon sintetis, PCM AudioWorklet, WebSocket, delta, koreksi, VAD auto-send, interupsi/Retry, sela suara, serta unduhan paket asesor. Tidak memakai kredit AI.
- `python tests/voice_mode_browser_smoke.py`: Chrome panel tiga interviewer, teks → suara, izin ditolak/terlambat, preservasi draf, unggah audio/teks/audio dan tampilan mobile. Perangkat, provider, database dan penyimpanan terisolasi.
- `python tests/realtime_live_smoke.py --run-paid`: ucapan sintetis lewat ElevenLabs dan OpenAI asli pada database sementara, tanpa LLM berbayar. Mengonsumsi kredit STT/TTS. Ringkasan berada di `artifacts/realtime-live-smoke.json`.

Probe asli 7 November mencatat delta transkrip, VAD mulai/berhenti, receipt tersimpan dan TTS chunk pertama 449 ms dari permintaan audio. Itu satu sampel lokal sintetis, tidak mencakup waktu LLM/pengguna atau kualitas aksen nyata. Pengujian suara fisik, kebisingan, jaringan lambat, aksesibilitas dan distribusi latensi produksi tetap perlu dilanjutkan.

Protokol mengikuti [OpenAI Realtime transcription](https://developers.openai.com/api/docs/guides/realtime-transcription), [VAD](https://developers.openai.com/api/docs/guides/realtime-vad), dan [ElevenLabs TTS stream](https://elevenlabs.io/docs/api-reference/text-to-speech/stream). Alur percakapan dan penilaian tetap ditangani orchestrator aplikasi, bukan model audio yang bebas membuat giliran.

## Pemeriksaan bahasa sesudah transkrip

Transkrip final yang dikirim, termasuk koreksi, melewati gate bahasa yang sama dengan teks/audio unggahan. Jika dominan berbeda dari bahasa wawancara dengan keyakinan tinggi, server tidak menerima jawaban sebagai unit penilaian dan mengirim `language_retry`. Controller membuang capture pengiriman lama, membacakan pengingat bila audio tersedia, lalu memberi kesempatan menjawab ulang pada pertanyaan yang sama. Tidak ada perubahan model STT atau provider/fallback. Lihat [kebijakan bahasa](languages-and-personas.md).
