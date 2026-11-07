# Menjalankan Preptiva di Kiri

Target: Kiri lokal di Mac. Docker context yang dipakai selalu `kiri`, tanpa mengganti context default Docker Desktop. Project Compose bernama `preptiva`.

## Persiapan sekali

1. Buka Kiri. Pada **Settings → Domains**, pilih `kiri.local` dan aktifkan **HTTPS** seperti pada screenshot pengaturan Anda. Jika Kiri meminta izin memasang resolver atau mempercayai CA lokal, selesaikan dialog sistemnya.
2. Isi `.env` dengan kredensial OpenAI/ElevenLabs dan voice ID yang sudah digunakan pada aplikasi lokal.
3. Dari direktori proyek, jalankan:

```sh
sh deploy/kiri.sh config
sh deploy/kiri.sh up
```

Perintah `config` membuat `.env.kiri` sekali dengan secret sesi dan password PostgreSQL acak, permission `600`, lalu memvalidasi Compose tanpa mencetak nilainya. Pemanggilan berikutnya mempertahankan secret/password yang sama. Jangan menghapus atau membuat ulang `.env.kiri` jika volume PostgreSQL sudah berisi data.

`up` membangun image aplikasi dan menjalankan empat service. Compose menunggu database dan Redis sehat, kemudian web membuat tabel, lalu worker mulai setelah web sehat. Ini menghindari dua proses membuat skema baru secara bersamaan.

## Alamat dan akses

- Alamat utama: **https://preptiva.kiri.local**
- Alias Compose: **https://web.preptiva.kiri.local**
- Health: **https://preptiva.kiri.local/health**

Label `dev.kiri.domain: preptiva` memberi nama utama; project/service Compose memberi alias kedua. Kiri menangani DNS lokal dan TLS, lalu meneruskan HTTP ke port container 8000. Web juga dipublish hanya ke loopback `127.0.0.1:18080` untuk Kiri Share. PostgreSQL dan Redis tetap tidak dipublish ke host. Server Uvicorn development pada localhost:8000 bisa tetap berjalan terpisah.

Alamat `.kiri.local` tersebut adalah domain lokal Kiri di Mac Anda. Untuk publikasi internet, gunakan URL Kiri Share di bagian berikut. Domain lokal tidak memerlukan domain berbayar atau perubahan DNS publik. HTTPS harus dipercaya browser agar kamera/mikrofon bisa dipakai. Jangan menonaktifkan verifikasi sertifikat sebagai solusi permanen.

## Akses publik melalui Kiri Share

URL setelah aktivasi dan uji restart autostart pada 7 November 2026: **https://buoy-s5yqbu.runkiri.cloud**. URL ini milik sesi Share saat ini, bukan nama permanen yang direservasi. Gunakan perintah status di bawah untuk URL terbaru. Pengunjung pertama kali dapat melihat halaman konfirmasi Kiri; klik **Continue to site**, kemudian daftar/login seperti biasa.

Target tunnel adalah `127.0.0.1:18080`, yang diteruskan Compose ke web port 8000. Kiri Share versi terpasang mensyaratkan published port jika memakai nama container; `expose: 8000` saja tidak mencukupi. Tunnel menargetkan port tetap sehingga tidak bergantung pada ID container saat deployment mengganti web.

Autostart sudah diaktifkan atas permintaan pengguna melalui LaunchAgent akun Mac `com.preptiva.kiri-share`. Daemon Kiri sendiri juga sudah terdaftar sebagai `dev.kiri.daemon`. Layanan Share dimulai setelah login macOS dan dijalankan ulang oleh launchd jika proses berakhir. Setelah reboot, login dan buka kunci akun Mac terlebih dahulu; layanan ini bukan daemon sistem sebelum login.

Pengelolaan dari folder proyek:

```sh
# Status autostart dan URL publik terbaru
python3 deploy/kiri_share_service.py status

# Restart Share (URL bisa berubah)
python3 deploy/kiri_share_service.py restart

# Hentikan Share untuk sesi login macOS saat ini
python3 deploy/kiri_share_service.py stop

# Aktifkan kembali setelah stop / pasang pada akun Mac yang sudah disiapkan
python3 deploy/kiri_share_service.py install
```

Runtime service, status, dan log privat berada di `~/Library/Application Support/PreptivaDeploy/share/`. Plist ada di `~/Library/LaunchAgents/com.preptiva.kiri-share.plist`. Service memakai salinan konfigurasi bootstrap di luar folder IDE sampai deployment otomatis pertama sukses; setelah itu ia memakai release yang ditunjuk `PreptivaDeploy/current`. Ia menjalankan Compose tanpa build, mempertahankan project/volume, dan menunggu kesehatan aplikasi. Kredensial login Kiri tetap dikelola Kiri; jika sesi akun tidak lagi valid, login ulang dengan `~/.kiri/bin/kiri share login`.

Mac harus tetap menyala dan terhubung internet. Autostart tidak menyediakan akses saat Mac tidur/mati dan tidak membuat URL acak menjadi permanen. `stop` melepas service untuk sesi login saat ini; untuk menonaktifkan autostart permanen, jalankan `stop`, lalu hapus plist tersebut. Aplikasi lokal dan volume database tetap ada.

Kiri Share mengubah host upstream, sehingga aplikasi perlu menerima origin HTTPS publik secara eksplisit. Saat URL berubah, service memperbarui `PUBLIC_ORIGIN` pada environment shared, bootstrap, dan release aktif lalu menerapkan ulang aplikasi. Password/secret/image tag dipertahankan; lock yang sama dengan CI mencegah perubahan bersamaan. Nilainya harus origin HTTPS Kiri lengkap tanpa path, bukan wildcard `*.runkiri.cloud`. Origin lain dan request browser bertanda `cross-site` tetap ditolak. Untuk deployment manual dari folder IDE, samakan `PUBLIC_ORIGIN` di `.env.kiri` dengan hasil perintah status terlebih dahulu; salinan environment IDE tidak ditulis oleh service. Pergantian URL dapat menimbulkan jeda singkat ketika web/worker diperbarui.

Smoke check publik menggunakan akun sementara, tidak memanggil API AI, dan menghapus akun uji setelah selesai:

```sh
.venv/bin/python tests/kiri_smoke.py --url https://buoy-s5yqbu.runkiri.cloud
```

Hasil disimpan terpisah di `artifacts/kiri-public-smoke.json` dan screenshot `artifacts/kiri-public-login.png`. Ganti URL jika sesi Share sudah berubah.

Profil ini memakai `APP_ENV=production` dan `COOKIE_SECURE=true`; `/dev-login` tidak tersedia. Buka halaman **Daftar** untuk membuat akun. Database PostgreSQL Kiri terpisah dari `data/dev.db` SQLite, sehingga akun/riwayat development tidak otomatis muncul di sini. Tidak ada akun demo bawaan yang dibuat dalam profil ini.

## Konfigurasi dan data

| Service | Fungsi | Penyimpanan |
| --- | --- | --- |
| `web` | FastAPI dan antarmuka, port internal 8000 | `interview_data` |
| `worker` | Job persiapan dan penilaian arq | `interview_data` yang sama |
| `db` | PostgreSQL 16 | `postgres_data` |
| `redis` | Antrean arq, persistence AOF | `redis_data` |

Nama volume otomatis diberi awalan project `preptiva_`. `.env` menyuplai pengaturan API/perilaku wawancara; `.env.kiri` menyuplai secret khusus stack ini. Compose menetapkan koneksi internal database/Redis dan mode cookie HTTPS secara eksplisit. Kedua file rahasia dikecualikan dari Git dan konteks build Docker; key SSH juga dikecualikan.

Setelah mengubah kode atau `.env`, jalankan `up` lagi agar image/container diperbarui. Perubahan pada durasi/follow-up/retry berlaku untuk sesi baru sesuai snapshot aplikasi. Profile VM lama tetap terpisah di `compose.yaml`; konfigurasi Kiri ada di `compose.kiri.yaml`.

## Operasional

```sh
# Status dan health seluruh service
sh deploy/kiri.sh ps

# Log web dan worker (Ctrl+C menghentikan tampilan log saja)
sh deploy/kiri.sh logs web worker

# Berhenti tanpa menghapus container/volume
sh deploy/kiri.sh stop

# Hapus container/network project, volume data tetap disimpan
sh deploy/kiri.sh down

# Menyalakan kembali / menerapkan perubahan
sh deploy/kiri.sh up

# Pemeriksaan worker
sh deploy/kiri.sh exec -T worker arq app.worker.settings.WorkerSettings --check
```

Jangan menjalankan `docker compose down -v` kecuali memang ingin menghapus data. Jangan mencetak hasil penuh `docker compose config` untuk dibagikan karena interpolasi environment dapat memuat rahasia; helper `config` menggunakan `--quiet`.

Rujukan: [fitur domain, HTTPS, Compose, dan Docker context Kiri](https://github.com/libracoder/kiri/blob/main/docs/features.md).

## Hasil verifikasi 7 November 2026

Deployment telah dijalankan pada Kiri 0.1.18. Keempat service berstatus healthy, dan helper `up` berhasil dijalankan ulang dengan volume/secret yang sama. HTTPS dipercaya oleh Chrome dan curl tanpa melewati pemeriksaan sertifikat.

`tests/kiri_smoke.py` memverifikasi health PostgreSQL/Redis, secure context browser dan ketersediaan API perangkat, pendaftaran/login/logout dengan cookie Secure/HttpOnly, penolakan `/dev-login` pada mode produksi, eksekusi job arq tanpa panggilan AI, serta akses baca/tulis volume bersama dari web dan worker. Akun serta file uji dihapus setelah selesai. Ringkasan ada di `artifacts/kiri-smoke.json`; screenshot halaman login ada di `artifacts/kiri-login.png`.

Pengujian ini tidak menggunakan kuota AI. Wawancara lengkap dengan API nyata sebelumnya diuji pada runtime lokal; kualitas mikrofon/speaker fisik dan sesi AI penuh melalui worker Kiri tetap perlu dicoba dari browser pengguna.

Untuk mengulang pemeriksaan dengan Chrome dan paket Playwright yang sudah terpasang:

```sh
.venv/bin/python tests/kiri_smoke.py
```

## Deployment otomatis: hanya Mac Bima

Workflow [kiri.yml](../.github/workflows/kiri.yml) menjalankan tes pada GitHub-hosted Ubuntu untuk PR dan push ke `main`. Setelah tes pada commit `main` lulus, job deployment berjalan hanya pada runner Mac ARM64 berlabel **`preptiva-kiri-bima`**. Daftarkan label ini pada satu mesin saja. Teman cukup push branch, membuka PR, lalu merge ke `main`; teman tidak perlu memasang Kiri atau menyimpan `.env` deployment. Push branch lain belum menerapkan perubahan.

```text
Push branch → PR → merge main → tes GitHub Actions
                                      ↓ lulus
                        runner preptiva-kiri-bima di Mac Bima
                                      ↓
                        build image → healthcheck Kiri
                                      ↓
                        https://preptiva.kiri.local
```

Kiri menjalankan container; GitHub Actions dan runner yang memicu deployment. Mac harus menyala, terhubung internet, runner online, dan VM Kiri berjalan. Ketika runner offline, job deployment menunggu runner; ketika runner online tetapi Kiri mati, deployment gagal dan perlu dijalankan ulang setelah Kiri dinyalakan. Alamat `.kiri.local` tetap lokal di Mac tersebut; mekanisme ini belum memberikan URL publik kepada teman.

### Persiapan environment deployment sekali

Dari folder proyek yang `.env` dan `.env.kiri`-nya sudah benar:

```sh
python3 deploy/auto_kiri.py init
```

Helper menyalin environment ke `~/Library/Application Support/PreptivaDeploy/shared/` dengan permission `600`. Pemanggilan ulang tidak menimpa file yang sudah ada. Password PostgreSQL harus tetap sama dengan yang digunakan volume saat ini. Ini memisahkan environment deployment dari perubahan `.env` untuk development. Untuk mengganti konfigurasi API produksi setelahnya, edit file `shared/.env` secara lokal, lalu jalankan ulang workflow pada `main`. Jangan mengganti password database melalui penghapusan `.env.kiri`.

### Registrasi runner sekali

1. Buka [Settings → Actions → Runners](https://github.com/dervaag/preptiva2026/settings/actions/runners) sebagai pemilik/admin repository. Pilih **New self-hosted runner → macOS → ARM64**.
2. Ikuti perintah download, checksum, dan ekstraksi yang GitHub tampilkan. Gunakan folder khusus di luar checkout proyek, misalnya `~/actions-runner-preptiva`.
3. Pada perintah `./config.sh` dari GitHub, tambahkan `--name preptiva-kiri-bima --labels preptiva-kiri-bima`. Jalankan sebagai akun Mac yang memiliki context Docker `kiri`. Token registrasi hanya dimasukkan di Terminal lokal dan tidak disimpan ke repository/chat. Gunakan label bawaan `self-hosted`, `macOS`, `ARM64` juga.
4. Dari folder runner yang sudah terdaftar, jalankan:

```sh
./svc.sh install
./svc.sh start
./svc.sh status
```

5. Pastikan GitHub menunjukkan runner **Idle/online** dan label `preptiva-kiri-bima`. Commit dan push file konfigurasi aplikasi/deployment serta workflow ke `main` (termasuk penghapusan key SSH dari index yang sudah disiapkan). Atau merge melalui PR. Pada tab **Actions**, pastikan job `test` dan `deploy` selesai hijau. `workflow_dispatch` memungkinkan **Run workflow** ulang pada `main`.

Registrasi membutuhkan akses pemilik/admin dan token sementara yang disediakan GitHub. Lihat [panduan registrasi resmi](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners) dan [service runner macOS](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application?platform=mac). Runner menjalankan kode repository dengan akses akun Mac; batasi penulis repository/workflow kepada kolaborator tepercaya dan gunakan review PR untuk `main`. Konfigurasi ini tidak menjalankan job deployment pada event PR.

### Perilaku pembaruan dan pemulihan

- Skrip [auto_kiri.py](../deploy/auto_kiri.py) memeriksa checkout sesuai SHA yang dites dan membuat release terpisah di `PreptivaDeploy/releases/`. Folder kerja IDE tidak di-pull/reset.
- Setiap percobaan punya tag image unik. Build selesai sebelum container diperbarui; build gagal tidak mengganti container berjalan.
- Project tetap `preptiva` dan Docker context tetap `kiri`. Volume `preptiva_postgres_data`, `preptiva_redis_data`, dan `preptiva_interview_data` dipakai ulang; tidak ada `down -v`.
- Deployment diserialkan dengan concurrency GitHub dan lock lokal. Commit lama yang sudah digantikan oleh `main` dilewati sebelum build atau sebelum aktivasi. Kegagalan membaca GitHub menghentikan deployment.
- Compose menunggu health web, worker, PostgreSQL, Redis. Setelah berhasil, pointer `current` diganti. Jika aktivasi gagal dan sudah ada release otomatis sukses sebelumnya, skrip mencoba menjalankan kembali image/config release tersebut. Workflow tetap gagal agar kegagalan terlihat. Pada deployment otomatis pertama, release otomatis sebelumnya belum tersedia; periksa `ps` dan perbaiki/pulihkan secara manual.
- Rollback container tidak memulihkan database. Perubahan skema tetap memerlukan migrasi dan backup tersendiri; aplikasi saat ini hanya membuat tabel yang belum ada. Pembaruan bisa menginterupsi request/wawancara yang sedang berlangsung; ini bukan rolling deployment tanpa jeda.
- Release/image lama disimpan agar bisa diperiksa. Pantau ruang disk Kiri/Mac dan bersihkan release/image yang tidak dipakai setelah memastikan kebutuhan pemulihan; jangan menghapus volume data.

Status deployment otomatis:

```sh
python3 deploy/auto_kiri.py status
```

Sesudah deployment otomatis pertama sukses, operasikan konfigurasi release aktif agar tidak tanpa sengaja menjalankan ulang source lama dari folder IDE:

```sh
sh "$HOME/Library/Application Support/PreptivaDeploy/current/deploy/kiri.sh" ps
sh "$HOME/Library/Application Support/PreptivaDeploy/current/deploy/kiri.sh" logs web worker
```

Status penyiapan 7 November 2026: runner ARM64 resmi v2.338.2 sudah diverifikasi SHA-256, didaftarkan sebagai `preptiva-kiri-bima`, dan dijalankan sebagai service akun Mac dari `~/actions-runner-preptiva`. Runner terhubung ke GitHub dan menampilkan `Listening for Jobs`. Seluruh 35 tes lokal lulus. Run workflow pertama setelah push menjadi pemeriksaan aktivasi menyeluruh.
