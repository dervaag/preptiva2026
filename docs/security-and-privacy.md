# Keamanan akun dan pengelolaan data

Kebijakan yang dipilih pemilik aplikasi pada 7 November 2026: tolak login kedua selama sesi pertama aktif; audio tersimpan 7 hari; riwayat, transkrip dan hasil 90 hari; CV profil sampai dihapus pengguna. Ini dokumentasi kontrol aplikasi dan hasil pengujian, bukan sertifikasi keamanan atau pernyataan kepatuhan hukum.

## Login dan sesi

| Kontrol | Perilaku |
| --- | --- |
| Batas akun | Maksimal 5 percobaan login dalam jendela 15 menit. Login yang berhasil menghapus penghitung akun. |
| Batas IP | Maksimal 50 percobaan dalam 15 menit; tidak dihapus oleh login berhasil. Registrasi dan konfirmasi password memiliki bucket terpisah. |
| Respons pembatasan | HTTP 429 dengan `Retry-After`; antarmuka menampilkan waktu tunggu. Kredensial salah atau akun tidak ditemukan memberi pesan 401 yang sama. |
| Satu login aktif | Login dari browser/perangkat kedua ditolak dengan 409. Tab yang berbagi cookie pada browser yang sama tetap menggunakan satu sesi. |
| Kedaluwarsa | 30 menit tanpa request terautentikasi dan maksimum 12 jam sejak login. Menutup browser bukan logout; gunakan Keluar atau tunggu kedaluwarsa idle. |
| Pencabutan | Logout mencabut token di database. Cookie lama tidak dapat digunakan kembali. Mengganti password mencabut sesi dan meminta login ulang. |
| Penyimpanan | Password tetap bcrypt. Database hanya menyimpan hash token acak; penghitung email/IP memakai HMAC dengan tujuan terpisah. Tidak ada password/token mentah dalam log. |
| Tindakan sensitif | Mengganti email/password serta menghapus CV/riwayat/akun memerlukan password saat ini. Penghapusan juga memerlukan teks konfirmasi. |

Satu baris sesi per pengguna dan operasi database bersyarat menjaga aturan ini di banyak proses, bukan hanya satu worker Python. PostgreSQL memakai row lock; SQLite memakai pembaruan bersyarat untuk mencegah kredensial lama diterima setelah perubahan password. WebSocket suara memeriksa login saat terhubung dan selama rekaman. Cookie lama yang hanya memuat `user_id` ditolak; setelah pembaruan ini pengguna perlu login kembali sekali.

Alamat IP berasal dari peer ASGI, bukan pembacaan langsung `X-Forwarded-For` yang dikirim klien. Di belakang proxy, beberapa pengguna dapat berbagi bucket IP. Atur daftar proxy tepercaya pada server hanya setelah topologi diverifikasi; jangan mempercayai semua alamat proxy. Batas akun tetap berlaku walaupun alamat IP berubah. Tabel pembatasan persisten di PostgreSQL/SQLite, sehingga restart web tidak menghapus batas dan perlindungan tidak bergantung pada Redis.

## Alur pengguna dan tanda terima

- **Profil → Hapus CV:** ketik password dan `HAPUS CV`. Yang dihapus adalah CV tersimpan untuk isian sesi berikutnya. CV yang sudah disalin ke sesi lama tetap merupakan bagian riwayat; hapus riwayat atau akun untuk menghapus salinan tersebut.
- **Riwayat → Hapus:** password dan `HAPUS` menghapus satu sesi milik pengguna. **Hapus seluruh riwayat** memerlukan `HAPUS RIWAYAT`.
- **Profil → Hapus akun:** password dan `HAPUS AKUN` menghapus akun, login aktif, CV profil, seluruh sesi beserta data turunannya, serta audio/cache terkait.
- Setelah penghapusan, pengguna dapat mengunduh tanda terima JSON. Penghapusan akun menampilkan tanda terima sebelum pengguna berpindah ke halaman login.

Tanda terima memuat ID, lingkup, waktu, jumlah baris/berkas dan status. Tidak memuat email, nama, CV, transkrip, password, atau token login. `complete` berarti penghapusan database dan pembersihan berkas oleh aplikasi selesai; `pending_files` berarti data database sudah dihapus tetapi pembersihan berkas perlu dicoba kembali. Riwayat tanda terima hanya dapat dibaca pemilik akun yang masih ada. Setelah akun dihapus, simpan unduhan yang ditampilkan; tidak ada endpoint publik untuk mengambil tanda terima akun lain.

Tanda terima adalah catatan aplikasi yang dapat dicocokkan dengan jurnal server, bukan bukti audit independen atau dokumen bertanda tangan digital. Unduhan pengguna bisa disalin atau diedit. Status awal `pending_files` dalam unduhan tidak berubah otomatis ketika worker kemudian menyelesaikan pembersihan.

## Cakupan penyimpanan dan retensi

| Data | Kebijakan |
| --- | --- |
| CV profil | Disimpan sampai Hapus CV atau Hapus akun. |
| Riwayat sesi | Dihapus setelah 90 hari dari `finished_at`, atau `created_at` bila sesi belum selesai. Meliputi CV/JD sesi, pertanyaan, jawaban, skor, hasil, event dan seluruh ledger/checkpoint/input LangGraph. |
| Audio/cache tersimpan | Berkas yang berumur lebih dari 7 hari berdasarkan mtime dihapus. Audio baru yang dibuat atas permintaan pengguna memiliki umur baru. |
| Audio kandidat dan PDF asli | Aplikasi saat ini memprosesnya untuk transkripsi/ekstraksi dan tidak mengarsipkan berkas mentah tersebut. Audio lokal yang persisten adalah suara interviewer/cache TTS; transkrip masuk retensi riwayat. |
| Tanda terima | Catatan selesai disimpan 30 hari. Pekerjaan berkas yang belum selesai tetap dipertahankan agar penghapusan dapat dituntaskan. |
| Login dan penghitung | Akses berhenti langsung ketika kedaluwarsa; metadata kedaluwarsa dibersihkan saat maintenance. |

Worker menjalankan maintenance saat startup dan setiap jam pada menit 17. Kebijakan bergantung pada worker yang hidup; data kedaluwarsa menunggu maintenance berikutnya, termasuk setelah downtime. `RETENTION_ENABLED=false` menghentikan penghapusan berdasarkan umur tetapi **tidak** membatalkan permintaan penghapusan pengguna yang sudah masuk jurnal.

Penghapusan database dan jurnal berkas berada dalam satu transaksi. Jika transaksi gagal, berkas tidak dihapus. Jika proses mati setelah commit, worker dapat mengulang jurnal. Penulisan audio dan penghapusan memakai lock berkas lintas proses; penanda penghapusan mencegah hasil provider yang terlambat membuat ulang berkas. Penanda berisi hash ID acak sesi dan kata `deleted`, tanpa konten kandidat, dipertahankan setelah tanda terima kedaluwarsa untuk menolak penulis terlambat.

Cache TTS baru dipisahkan per sesi. Cache global versi lama tidak memiliki indeks pemilik dan dibersihkan saat maintenance atau permintaan penghapusan; ini dapat menyebabkan suara berikutnya dibuat ulang. Volume pengguna lain dan riwayatnya tidak dihapus oleh penghapusan satu akun.

Penghapusan ini berlaku pada database dan volume aktif aplikasi. Backup/snapshot eksternal, salinan yang sudah diunduh, log platform hosting, serta data yang telah dikirim ke penyedia AI berada di luar kontrol endpoint ini. Jangan menyatakan bahwa semuanya ikut terhapus. Pengelola harus menetapkan masa simpan backup/log dan memastikan pemulihan backup tidak menghidupkan kembali permintaan penghapusan; mekanisme pemulihan lintas backup itu belum diotomatisasi di sini.

## Perlindungan tambahan

Cookie produksi memakai Secure, HttpOnly, dan SameSite. Mutasi HTTP memeriksa Origin/Referer yang tepat termasuk skema, serta Fetch Metadata; origin dengan kredensial, path, atau subdomain lain ditolak. Klien API non-browser tetap boleh tidak mengirim header browser, tetapi tetap membutuhkan cookie sesi yang sah. Halaman pribadi dan API, termasuk audio, memakai `Cache-Control: no-store`. Header anti-framing, nosniff, HSTS produksi, dan pembatasan dasar CSP ditambahkan; CSP ini tidak mengklaim menutup seluruh jalur XSS.

WebSocket memakai kebijakan origin HTTPS yang sama. Permintaan HTTP dibatasi total 30 MiB sebelum parsing, termasuk transfer chunked; batas PDF 5 MiB dan audio jawaban 25 MiB tetap lebih kecil. Dependensi Starlette minimal 1.10 memakai cookie yang hanya ditulis ketika sesi berubah. Pemeriksaan login pasif tidak menghapus cookie, sehingga respons lama yang terlambat tidak menimpa login baru.

Error validasi tidak memuat `input` atau `ctx` dari Pydantic, karena keduanya dapat memuat password. Error HTTP tak terduga dicatat sebagai tipe dan lokasi kode, bukan pesan exception atau parameter SQL. Pembatasan kepemilikan tetap berlaku untuk sesi, hasil, audio, profil, dan tanda terima. Path traversal serta symlink audio ditolak.

Belum termasuk MFA/passkey, verifikasi kepemilikan email, pemulihan password mandiri lewat email, pengujian penetrasi independen, atau verifikasi enkripsi/siklus hidup backup pada host. Password baru masih mengikuti aturan kompatibilitas aplikasi (8–72 karakter, maksimum 72 byte, huruf dan angka); itu bukan klaim memenuhi seluruh rekomendasi kekuatan password terbaru.

## Operasional dan bukti

Konfigurasi ada di `.env.example`: `AUTH_LOGIN_*`, `AUTH_IDLE_SECONDS`, `AUTH_ABSOLUTE_SECONDS`, `RETENTION_*`, dan `MAX_REQUEST_BYTES`. Password/secret tidak perlu diganti untuk mengaktifkan fitur ini. Tabel PostgreSQL baru dibuat secara aditif; data wawancara yang belum jatuh tempo tidak dimigrasikan ke engine lain.

Untuk SQLite pengembangan, ID akun/sesi dan data turunan tidak boleh dipakai ulang setelah dihapus. Startup meningkatkan tabel lama menjadi `AUTOINCREMENT` dalam satu transaksi, mempertahankan data, kolom tambahan, relasi, indeks, trigger dan view; kegagalan membatalkan perubahan. Tidak dibuat salinan backup tambahan yang tertinggal. **Hentikan seluruh web/worker versi lama sebelum menjalankan pembaruan SQLite**, agar tidak ada permintaan lama yang masih memegang ID dari sebelum migrasi. PostgreSQL menggunakan sequence dan tidak menjalankan rebuild ini.

Pratinjau tanpa menghapus data:

```sh
python -m app.scripts.retention
```

Terapkan kebijakan yang dikonfigurasi dan ulangi pembersihan berkas tertunda:

```sh
python -m app.scripts.retention --apply
```

Pada Kiri, jalankan perintah tersebut melalui `docker --context kiri exec preptiva-worker-1 ...`. Event `retention_completed`/`retention_failed` dan `privacy_cleanup_failed` membantu pemantauan; kegagalan tidak dicatat sebagai keberhasilan dan dicoba kembali pada jadwal berikutnya.

Tes yang menjadi bukti implementasi:

| Berkas | Hal yang dibuktikan |
| --- | --- |
| `tests/test_auth_security.py` | Login lintas proses, hanya satu pemenang, batas percobaan atomik, cookie kedaluwarsa/replay, revokasi, perubahan kredensial bersamaan, redaksi password. |
| `tests/test_privacy_security.py` | Isolasi pengguna, cascade seluruh bukti graph, retensi batas waktu, receipt tertunda dan retry, rollback, symlink, perubahan CV/password bersamaan. |
| `tests/test_security_integration.py` | Origin, cache halaman, replay HTML/WebSocket, penulisan TTS terlambat, cache antar sesi, exception tanpa data pribadi. |
| `tests/test_sqlite_identity.py` | Migrasi SQLite lama, rollback, ID yang tidak dipakai ulang dan permintaan lama setelah penghapusan akun. |
| `tests/profile_language_smoke.py` | Chrome dengan API/database sementara: profil, ganti email, CV, konfirmasi, bahasa dan layout. |
| `tests/security_privacy_browser_smoke.py` | Kontrak UI dengan API sintetis: seluruh dialog, pembatalan, error, unduhan receipt, pending berkas, dan hasil hapus akun tetap terlihat. |
| `tests/security_deployment_smoke.py` | Pemeriksaan opt-in melalui HTTP(S) dengan akun baru sintetis, tanpa wawancara/panggilan AI; akun uji dihapus setelah selesai. |

Suite autentikasi/penghapusan juga dijalankan pada PostgreSQL 16 sementara yang berbeda dari produksi, termasuk pengujian lintas proses dan row lock. Bukti ringkas dan batas cakupan ada di `artifacts/security-privacy-evidence.json`; data/password akun nyata tidak digunakan dalam pengujian regresi.

Rujukan desain: [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), dan [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html). Rujukan tersebut menjadi pertimbangan desain, bukan sertifikasi aplikasi.
