# Log perubahan

## 2026-11-07 — Penyelarasan tes generator panel dengan penutup bilingual

- Memperbarui ekspektasi tes panel yang masih mengharapkan penutup mentah dari provider setelah penutup standar diterapkan. Tes kini memeriksa bahasa Indonesia/Inggris, pemisahan prompt HR/User/Manager dan urutan panel dalam satu alur generasi.
- Mempertahankan kebijakan penutup standar tanpa ajakan Q&A; kegagalan CI berasal dari ekspektasi tes lama.
- Verifikasi lokal: 211 tes Python dijalankan, 210 lulus dan 1 khusus PostgreSQL dilewati pada SQLite; sintaks JavaScript, helper UI dan 29 skenario controller lulus tanpa panggilan AI berbayar.

## 2026-11-07 — Kandidat diminta mengulang ketika bahasa jawaban berbeda

- Memeriksa dominasi Indonesia/Inggris secara lokal sebelum menerima jawaban pada jalur legacy/LangGraph; jawaban singkat/tidak pasti dan istilah teknis diperlakukan konservatif.
- Mengembalikan `language_retry` untuk pertanyaan yang sama tanpa skor, giliran baru, kuota follow-up atau penutupan. Pengingat bilingual tampil di chat dan dapat dibacakan persona aktif; timer jawaban kembali penuh.
- Menambahkan regresi dua arah bahasa, JSON/NDJSON, audio, koreksi pada pertanyaan sama dan controller UI yang tidak memanggil finish atau menambah retry.

## 2026-11-07 — Penutup tidak mengundang kandidat bertanya lalu menutup sesi

- Mengganti slot baru `candidate_questions` menjadi `reflection` dan menolak ajakan Q&A di validasi pertanyaan/adaptasi. Tidak menambahkan fase kandidat bertanya kepada panel.
- Memakai penutup bilingual yang menyatakan wawancara selesai dan hasil akan diproses. Penutup sesi lama yang mengundang pertanyaan diarahkan ke teks dan suara streaming yang sesuai, tanpa memutar audio lama yang bertentangan.
- Tetap mempertahankan tanya jawab utama/follow-up serta finalisasi otomatis. Menambahkan regresi untuk penutup Indonesia/Inggris dan kompatibilitas audio sesi lama.

## 2026-11-07 — Bahasa hasil mengikuti pilihan platform saat pembuatan sesi

- Menyimpan `feedback_language` terpisah dari bahasa wawancara dan meneruskannya ke evaluasi, tinjauan panel serta ringkasan legacy/LangGraph. Sesi lama memakai fallback bahasa wawancara; bukti asli dipertahankan.
- Memperjelas akhir wawancara di prompt evaluasi/ringkasan; feedback harus berupa penjelasan dan tindakan latihan, bukan pertanyaan baru. Validator menolak tanda tanya dengan satu perbaikan terbatas dan jalur kegagalan yang dapat dicoba ulang.
- Memverifikasi snapshot bahasa, prompt bilingual, perbaikan pertanyaan, label UI dua arah dan PDF dengan data sintetis. Tidak mengubah atau menerjemahkan laporan produksi yang sudah tersimpan.

## 2026-11-07 — Jawaban hasil langsung terlihat dan ikut tercetak

- Membuka transkrip dan feedback tiap jawaban secara default; membuka alasan bukti ketika skor belum terukur dan menambahkan penjelasan Indonesia/Inggris tentang skor null.
- Membuka disclosure selama print/PDF dan memulihkan pilihan pengguna setelahnya; menyederhanakan layout cetak. Skor dan data sesi tidak diubah.
- Menambahkan smoke test Chrome dengan payload sintetis untuk visibilitas jawaban, bukti, mobile/desktop, escaping dan isi PDF. Lihat [hasil wawancara](results.md).

## 2026-11-07 — Seeder akun manual

- Menambahkan `python -m app.scripts.seed_account --email ... --name ...` dengan password melalui prompt tersembunyi, secret environment sementara atau stdin; password tidak dimasukkan ke argumen command/kode.
- Pemanggilan ulang atomik tidak menggandakan akun atau menimpa profil/CV. Password yang berbeda dilaporkan tanpa perubahan; `--reset-password` menyediakan reset eksplisit dengan pencabutan login akun terkait.
- Menambahkan regresi akun baru, pemanggilan ulang/bersamaan, preservasi profil/login, reset terarah, serta redaksi input tidak valid. Petunjuk: [deployment Kiri](deployment-kiri.md#menyiapkan-akun-melalui-seeder).

## 2026-11-07 — Keamanan akun, penghapusan dan retensi

- Membatasi percobaan login per akun dan peer IP dengan penghitung database atomik, respons 429 dan `Retry-After`. Satu akun memiliki satu token aktif; browser kedua ditolak 409. Logout/password baru mencabut token, dengan kedaluwarsa idle 30 menit dan mutlak 12 jam.
- Menambahkan konfirmasi password untuk perubahan email/password dan penghapusan CV, satu/seluruh riwayat serta akun. Antarmuka ID/EN menyediakan konfirmasi tertulis dan unduhan tanda terima setelah penghapusan, termasuk saat akun sudah tidak ada.
- Menambahkan jurnal pembersihan berkas, status `pending_files` yang jujur, retry worker serta retensi audio 7 hari, riwayat/transkrip/hasil 90 hari dan receipt selesai 30 hari. CV profil bertahan sampai dihapus; salinan dalam riwayat ikut penghapusan riwayat/akun.
- Memisahkan cache TTS per sesi dan mengunci penulisan/penghapusan lintas proses. Penanda penghapusan mencegah respons provider terlambat menghidupkan kembali berkas. Cache global lama dibersihkan karena tidak memiliki indeks kepemilikan.
- Memperketat origin HTTP/WebSocket, cache halaman privat, batas total request dan redaksi error. Cookie pada pemeriksaan pasif tidak ditulis ulang agar respons yang terlambat tidak menimpa login baru. Pengguna perlu login kembali setelah pembaruan token sesi ini.
- Mencegah penggunaan ulang ID SQLite setelah penghapusan, termasuk peningkatan transaksional database lama. Permintaan lama tidak dapat membaca data akun baru yang kebetulan mendapatkan ID sama. PostgreSQL tetap memakai sequence.
- Bukti regresi, PostgreSQL terisolasi dan Chrome tercatat dalam `artifacts/security-privacy-evidence.json`. Panduan dan batas cakupan: [keamanan dan privasi](security-and-privacy.md). Tidak mengklaim penghapusan backup/provider, sertifikasi keamanan, atau validasi rubrik oleh manusia.

## 2026-11-07 — Pemulihan validasi jawaban dan diagnostik error

- Memperbaiki aturan kutipan yang sebelumnya mustahil dipenuhi jawaban pendek seperti “Belum.”: kutipan pendek harus merupakan seluruh jawaban asli, bukan potongan jawaban panjang. Aturan bukti untuk skor kompetensi tetap sama.
- Memperbaiki pemilihan konteks ketika jawaban panjang hanya menghasilkan fragmen pendek. Potongan tetap literal dari sumber asli; opsi kutipan diperiksa sebelum diberikan ke model.
- Memasukkan validasi format, aksi, kutipan dan pertanyaan ke dalam satu kesempatan perbaikan keluaran AI. Probe yang dilarang oleh batas follow-up dibuang beserta kutipannya. Pertanyaan adaptif yang tetap tidak valid ditolak, tanpa menerima sumber yang dikarang.
- Log `answer_failed` pada stream maupun JSON biasa menyertakan ID sesi/pertanyaan, tahap, kode alasan dan lokasi kode. Log serta instruksi repair tidak mencetak keluaran model, pesan exception mentah, isi CV, atau transkrip.
- Penolakan keluaran AI setelah dua percobaan memberi respons 502 atau event error pada stream. Jawaban legacy tetap atomik; retry yang berhasil tidak menggandakan jawaban. HTTP 200 stream bukan penanda bahwa pemrosesan telah berhasil.
- Verifikasi: 149 tes Python lulus dengan database sementara dan provider tiruan, termasuk 25 regresi baru, tanpa panggilan AI berbayar. Log lama tidak cukup untuk memastikan bahwa seluruh kejadian `ValueError` memiliki penyebab yang sama. Panduan: [log runtime](logging.md).

## 2026-11-07 — Orkestrasi LangGraph dengan versi per sesi

- Menambahkan graph persiapan, satu giliran dan finalisasi, memakai fungsi/provider yang sudah ada. `ORCHESTRATION_ENGINE` default `legacy`; sesi baru dapat memilih `langgraph`, sedangkan sesi lama mempertahankan engine. Versi graph yang tidak didukung ditolak tanpa fallback diam-diam.
- Checkpoint SQLAlchemy menyimpan referensi; ledger menyimpan hasil operasi, durasi, retry, model dan usage. Lease lintas proses serta pemeriksaan input mencegah jawaban ganda. Transkrip diterima disimpan sebelum respons AI; worker memulihkan pekerjaan yang ditinggalkan dan merekonsiliasi commit aplikasi yang mendahului checkpoint.
- Koordinator mengutamakan cakupan/topik yang belum ditanyakan tanpa mengubah batas pertanyaan atau alokasi panel. Follow-up tetap milik persona utama. Handoff menyertakan sumber asli; Retry/Next, perangkat dan rekaman tetap dikendalikan browser.
- Menambahkan penilaian awal independen per persona, tinjauan perbedaan yang tidak menimpa skor awal, serta agregasi `panel-evidence-equal-persona-v1`. Hasil dan tren dipisahkan menurut kebijakan penilaian. Rubrik tetap `validated: false`.
- Operasi provider yang hasilnya ambigu memerlukan retry eksplisit. CLI inspeksi/pemulihan tidak mencetak dokumen atau kredensial; kasus STT sebelum transkrip tersimpan dapat diberi izin satu kali untuk kirim ulang audio yang sama.
- Verifikasi: 124 tes Python lulus; 11 tes runtime juga lulus pada PostgreSQL terisolasi, termasuk proses mati/restart dan konkurensi. 29 skenario controller dan Chrome sintetis panel, audio–teks–audio, realtime/VAD, interupsi/Retry/Next hingga hasil lulus. Benchmark 12 sampel membandingkan overhead sintetis; token, biaya provider dan kualitas nyata belum diukur. Panduan: [orkestrasi LangGraph](langgraph-orchestration.md).

## 2026-11-07 — Penggabungan frontend `codex/enhance-fe` ke `main`

- Menggabungkan desain login, dashboard, form, ruang wawancara, hasil dan riwayat; menambahkan profil/CV serta pilihan bahasa antarmuka Indonesia–Inggris. Bahasa antarmuka terpisah dari bahasa wawancara.
- Menyelesaikan konflik ruang wawancara dengan mempertahankan pilihan suara/teks, kembali ke mikrofon tanpa otomatis merekam, preservasi draf/rekaman, dan perlindungan izin terlambat setelah interupsi. Panel, realtime/VAD, rubrik pekerjaan dan alat benchmark Mohler tetap tersedia.
- Menambahkan regresi akses/CSRF/isolasi profil, perubahan identitas/CV dan pergantian bahasa. CI memeriksa seluruh JavaScript dan menjalankan 29 skenario controller. Suite backend lokal: 84 tes lulus; uji Chrome memakai data dan provider sintetis, tanpa panggilan AI berbayar.

## 2026-11-07 — Pilihan jawaban suara dan kembali dari mode teks

- Memisahkan pilihan **Rekam suara saya** (default) dan **Ketik jawaban** dari checklist kesiapan, serta menampilkan mode aktif di dekat jawaban.
- Menambahkan **Gunakan mikrofon** pada jawaban teks agar pengguna dapat kembali ke rekaman dalam sesi yang sama. Perekaman tetap dimulai melalui **Mulai rekam suara**; draf teks dan rekaman selesai dipertahankan ketika berganti mode pada pertanyaan yang sama.
- Izin mikrofon yang ditolak mempertahankan mode teks. Izin yang baru datang setelah tab/offline menghentikan pertanyaan tidak dapat melewati Retry/Next. Sela suara otomatis tidak aktif saat mode teks dipilih.
- Verifikasi: Chrome sintetis untuk izin ditolak/terlambat, panel dengan jawaban audio/teks/audio, preservasi draf dan layout 390/768/1440px; regresi interview tunggal/panel serta sintaks JavaScript lulus. Tidak menggunakan akun atau suara pengguna.

## 2026-11-07 — Dataset Mohler dan benchmark eksternal

- Mengunduh Mohler ASAG dari revisi `dac06732b42d01a5169f543f6d272f1476cced3e`: 2.442 jawaban dengan rating manusia (2.273 open-ended, 169 closed-ended). Manifest menyimpan atribusi, lisensi yang dinyatakan distributor, URL, hash dan perubahan; data berada di `data/external/`, di luar Git/image.
- Mempertahankan skor asli 0–5/0–10 dan rata-rata sumber 0–5. Menandai 214 ketidaksesuaian rata-rata tanpa memperbaikinya otomatis; mengecualikannya dari pilot deterministik 50 jawaban. Label manusia dipisahkan dari masukan AI dan diikat hash.
- Menambahkan CLI `validation/mohler.py` (download/prepare/run/report), dependensi Parquet opsional, penyimpanan hasil per kasus dan provenance model/prompt. Runner memakai klien aplikasi dengan prompt akademik terpisah; report menghitung Spearman, MAE 0–5 dan persentase selisih maksimal satu poin.
- Menambahkan audit kesiapan serta pembanding skor eksternal. RecruitView tidak diimpor karena pembatasan penggunaan; MIT/AVI tetap memerlukan akses sesuai ketentuan. Rincian ada di [benchmark eksternal](external-benchmark.md).
- Verifikasi terpisah: 3 tes impor/persiapan Mohler, 3 tes pembanding eksternal dan 3 tes audit lulus. Ini bukan klaim bahwa seluruh suite dijalankan ulang. Tidak ada run Mohler berbayar atau metrik AI–manusia; rubrik produksi dan `validated: false` dipertahankan.
- Menyelaraskan dokumentasi setup, pipeline, API, penyimpanan, asesmen dan hasil pemeriksaan. Panduan operasional: [benchmark Mohler](mohler-benchmark.md).

## 2026-11-07 — Perbaikan pilihan panel dan cache antarmuka

- Menyamakan kartu avatar format tunggal dan panel. Panel memakai checkbox terpisah pada setiap kartu, warna pilihan oranye, serta jarak 20 px dari dropdown.
- Menambahkan hash isi pada URL CSS/JavaScript agar browser mengambil controller dan style yang sesuai HTML terbaru. Tes Chrome mereproduksi mode Panel yang tetap menampilkan radio tunggal ketika bundle lama sudah tersimpan di cache.
- Menambahkan tes cache dan pemilihan beberapa anggota dengan data sementara tanpa panggilan AI. Selector tes form lama dibatasi ke kelompok tunggal karena kartu kini dipakai di kedua format.
- Verifikasi: 52 tes backend, Chrome untuk cache lama, pemilihan panel, payload form, dropdown dan keyboard lulus. Layout 320–1440 px diperiksa; server lokal juga memuat tiga checkbox aktif dengan jarak 20 px.

## 2026-11-07 — Integrasi panel pada antarmuka Preptiva

- Menggabungkan pembaruan backend sampai `9ac2f90` dengan logo, form, ruang wawancara, dashboard, dan riwayat yang sudah diperbarui secara lokal. Checkpoint UI sebelum integrasi: `40844ca`.
- Form memakai dropdown khusus untuk format tunggal/panel dan latar pengalaman. Panel memerlukan 2–3 pewawancara; jumlah pertanyaan berlaku untuk seluruh panel.
- Ruang mengikuti nama, karakter, dan suara pewawancara aktif; chat mempertahankan penulis tiap giliran dan jumlah peserta mencakup kandidat. Mode teks, penghentian suara, Retry/Next, dan pemulihan penilaian terhubung ke kontrak backend terbaru. PC/laptop tetap wajib.
- Dashboard dan riwayat mengenali seluruh anggota panel serta status penilaian tertunda. Memperbaiki penguncian tombol pemulihan ketika interupsi kedua terjadi saat permintaan Retry belum selesai.
- Verifikasi lokal: 52 tes backend, 19 skenario controller, serta Chrome untuk form, dropdown, dashboard/riwayat, ruang, dan alur tunggal/panel hingga hasil lulus. Seluruh uji memakai data/perangkat sintetis dan provider tiruan; tidak melakukan panggilan AI berbayar atau deployment Kiri.
## 2026-11-07 — Draf rubrik Engineering Manager dan alur validasi asesor

- Menambahkan profil latihan EM/Manager opt-in dengan lima kompetensi, 25 jangkar, bobot usulan dan pemetaan sumber/tugas. Seluruh indikator disusun internal, ahli belum meninjau, dan validated tetap false.
- Menambahkan snapshot lengkap dan pemisahan tren kompetensi menurut hash rubrik. Form/API menolak penerapan profil di HR/User/panel atau pekerjaan lain; snapshot dan hasil lama dipertahankan.
- Menampilkan skor, kutipan asli, indikator, alasan belum naik tingkat dan rujukan sumber. ID/level/kutipan diverifikasi kode dan sumber hanya diambil dari snapshot. Keluaran evaluator tidak lengkap mendapat satu kesempatan perbaikan.
- Menambahkan paket offline 20 kasus tanpa skor AI, rating independen, konsensus koordinator setelah minimal tiga asesor, provenance lima run AI, serta laporan yang menjelaskan kasus bukti kurang dan denominator metrik. Tidak ada penilaian manusia atau konsensus yang dibuat otomatis.
- Verifikasi: 71 tes Python dan pemeriksaan keamanan/gating UI lulus; Chrome end-to-end EM lima pertanyaan pada lebar 390/768/1440px lulus. Probe model asli berhasil menyiapkan lima kompetensi serta membedakan contoh bukti cukup dan jawaban tanpa contoh setelah perbaikan.
- Probe sintetis model asli menemukan kelemahan penggolongan jawaban tanpa contoh dan kelengkapan struktur; aturan prompt dan pemeriksaan struktur diperketat. Pengujian ini adalah regresi perangkat lunak, bukan kalibrasi atau validasi psikometrik.

## 2026-11-07 — Audio realtime dan paket asesor

- Menambahkan transkripsi WebSocket dengan PCM AudioWorklet, VAD, delta transkrip dan receipt bertanda tangan. Sesi baru memakai TTS streaming saat diputar; kunci API tetap di server. Model/provider yang sudah dikonfigurasi dipertahankan.
- Menambahkan tinjau/koreksi transkrip sebelum pengiriman dengan arsip teks STT asli, pilihan kirim otomatis setelah jeda, dan pilihan sela pembacaan pertanyaan. Tab/offline/putus transport tetap menghentikan pertanyaan dan membuka Retry/Next; lease rekaman lama dibersihkan.
- Mencatat event waktu akhir rekaman hingga audio respons mulai diputar. Waktu review manual ikut terhitung; belum tersedia dashboard distribusi latensi/biaya.
- Menyiapkan paket HTML offline tanpa skor AI untuk tiga calon asesor, tujuh contoh sintetis dengan skor kosong, validasi hasil JSON dan runner AI lima kali per kasus yang harus dipilih secara eksplisit. Asesor belum tersedia, penilaian manusia belum dilakukan, `validated` tetap false. Lihat [panduan asesor](assessor-validation.md).
- Verifikasi: tes otomatis receipt, koreksi, pembatasan akses, idempotensi, cache streaming dan integritas paket; Chrome sintetis untuk realtime/VAD/Retry/sela suara/form asesor serta regresi panel. Probe STT/TTS asli lulus tanpa LLM atau data kandidat nyata; satu sampel TTS chunk pertama 449 ms bukan jaminan latensi produksi. Lihat [audio realtime](realtime-voice.md) dan artefak smoke terkait.

## 2026-11-07 — Konteks panel, bukti dan pemulihan pertanyaan

- Membaca brief panel tambahan dan menerapkan keputusan pengguna: tab tersembunyi/koneksi putus menghentikan pertanyaan aktif; Retry mengulang dengan waktu penuh, Next melewati tanpa skor. Jawaban yang sudah terkomit tidak digandakan; penutupan seluruh sesi tetap melalui Akhiri sesi.
- Menambahkan context packet terbatas dengan giliran terbaru/retrieval, kutipan klaim berstatus unverified, validasi rujukan sumber, serta event/checkpoint persisten. Tabel event baru bersifat aditif; snapshot historis dipertahankan.
- Memisahkan bukti cukup/kurang/belum dinilai/transkrip tak dapat digunakan. Skor tanpa bukti valid tetap maksimal 2 dan provisional, tetapi dikeluarkan dari agregat baru. Hasil menampilkan cakupan dan asal kutipan literal per giliran.
- Menambahkan mode teks, fallback saat suara gagal, penghentian suara manual, serta penilaian ulang setelah evaluator gagal tanpa menghapus jawaban.
- Menyiapkan `validation/compare.py` untuk data skor independen asesor dan AI; belum ada penilaian manusia. `validated` tetap false. Status bagian brief yang belum diterapkan dicatat di `panel-implementation.md`.
- Verifikasi: 51 tes backend lulus; Chrome sintetis lulus untuk interupsi rekaman, offline, reload, Retry/Next, jawaban teks, cakupan dan hasil mobile. Probe model nyata pada tiga CV/JD sintetis juga lulus dengan rujukan giliran/kutipan terverifikasi. Uji ini tidak membuktikan validitas psikometrik atau akurasi semua transkrip nyata.

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
