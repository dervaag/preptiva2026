# Arsip rencana deployment VM

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

**Status 7 November 2026: rencana deployment VM dibatalkan oleh pengguna. Target deployment aktif adalah satu mesin Kiri di Mac pengguna**, dengan PostgreSQL, Redis, Kiri Share dan auto-deploy GitHub. Ikuti [deployment-kiri.md](deployment-kiri.md) untuk menjalankan dan memelihara target aktif.

Dokumen ini menyimpan catatan rencana VM dan hanya dipakai bila deployment VM diputuskan kembali. Target lama yang diberikan adalah `ubuntu@43.218.46.146`, SSH port 22, tanpa domain. Pada pemeriksaan 7 November 2026, koneksi SSH timeout sebelum autentikasi; tidak ada file yang diunggah atau layanan VM yang diubah dalam upaya tersebut. Status/IP VM saat ini belum diperiksa ulang.

## Jika rencana VM dilanjutkan: periksa akses SSH

1. Pastikan instance berstatus running dan IP publik masih `43.218.46.146`.
2. Pada Security Group instance, izinkan inbound TCP 22 dari IP publik koneksi administrator (`/32`). Jangan gunakan IP privat laptop atau alamat `localhost`.
3. Pastikan firewall OS, network ACL dan routing jaringan juga mengizinkan koneksi dan balasannya. Bila memakai SSH port selain 22, sesuaikan opsi `-p`.
4. Uji dari direktori proyek:

```sh
chmod 400 rnd-tekna.pem
ssh -i rnd-tekna.pem -o IdentitiesOnly=yes ubuntu@43.218.46.146
```

Timeout terjadi sebelum key diverifikasi, sehingga tidak membuktikan key benar atau salah. Bila koneksi sudah mencapai autentikasi tetapi ditolak, periksa user `ubuntu` dan key yang dipasang pada instance.

## Private key dan Git

`rnd-tekna.pem` pernah masuk commit `4bb8275`. Penghapusannya sudah dikomit dalam `f98470c` dan tercakup dalam `origin/main`; file tidak lagi dilacak pada versi saat ini. Pola private key dikecualikan dari Git dan konteks Docker. Penghapusan file dari versi terbaru tidak menghapus key dari riwayat lama.

Penggantian key dan pencabutan akses key lama belum terverifikasi. Sebelum memakai VM kembali, pasang public key pengganti melalui jalur administrasi yang tersedia, uji login baru pada koneksi kedua, lalu cabut public key lama dari `authorized_keys`. Jangan mencabut akses lama sebelum akses pengganti terverifikasi. Pembersihan riwayat Git memerlukan koordinasi karena mengubah commit; belum dilakukan otomatis.

## Paket aplikasi

```sh
python3 deploy/package.py
```

Perintah ini membuat paket di `data/deploy/preptiva-source.tar.gz` tanpa mengunggahnya atau mengubah target deployment aktif. Paket memakai daftar file/direktori yang diizinkan dan hanya memuat source aplikasi, dokumentasi, dependensi, Docker/Compose dan contoh konfigurasi. Private key, `.env`, Git, data lokal, dan hasil pengujian tidak dimasukkan. Jangan mengunggah seluruh direktori proyek secara rekursif.

Setelah SSH tersedia, langkah deployment adalah memeriksa layanan dan kapasitas VM, menentukan direktori aplikasi yang belum dipakai, mengunggah paket source, memasang konfigurasi produksi dengan permission ketat, kemudian menjalankan PostgreSQL, Redis, web, dan worker. Konfigurasi produksi membutuhkan secret acak, kredensial database sendiri, dan cookie secure. Kredensial API ditransfer terpisah melalui SSH, bukan dimasukkan ke image atau repository.

Compose saat ini hanya mengekspos web pada loopback VM `127.0.0.1:8000`; database dan Redis tidak mempunyai port host publik. Sambil menunggu domain/HTTPS, tunnel administrasi dapat meneruskan port lokal:

```sh
ssh -i rnd-tekna.pem -o IdentitiesOnly=yes -N -L 8001:127.0.0.1:8000 ubuntu@43.218.46.146
```

Port tunnel baru berguna setelah aplikasi berjalan di VM. Publikasi browser di luar localhost membutuhkan HTTPS untuk kamera/mikrofon dan cookie produksi. Nginx yang tersedia masih contoh proxy HTTP; sertifikat, domain, dan routing publik belum disiapkan.
