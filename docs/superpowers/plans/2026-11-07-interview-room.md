# Rencana ruang wawancara Preptiva

> Arsip rencana implementasi. Checklist dan perintah di bawah adalah catatan saat rancangan dibuat, bukan status live. Tinjauan 7 November 2026: [status implementasi terkini](../../current-state.md).

## Lingkup yang disetujui

Menerapkan referensi pemilik proyek menjadi ruang meeting compact dengan chat, modal verifikasi perangkat, countdown 3-2-1, dan tiga pewawancara 3D beranimasi. Melanjutkan DM Sans, logo, dan oranye dari form. Mempertahankan format rekaman dan aturan penutupan sesi; tambahan instruksi pengguna mewajibkan PC/laptop melalui gate UI dan API start.

## Implementasi

- [x] Periksa template, controller, API, dan sesi target secara read-only.
- [x] Pisahkan shell ruang, stage, candidate PiP, chat, toolbar, dan modal yang dapat digunakan dengan keyboard.
- [x] Generate tiga sprite transparan serta background melalui image_gen bawaan sesuai permintaan pengguna; simpan aset di proyek dan prompt di dokumentasi.
- [x] Implementasikan verifikasi media nyata, start tunggal, countdown, animasi audio, chat, dan recovery tanpa perubahan backend.
- [x] Uji alur terisolasi, layout desktop/mobile, cleanup, dan regresi sebelum/ sesudah perbaikan temuan review.
- [x] Review independen, perbaiki dua P2, dokumentasikan perilaku dan batas verifikasi.
- [x] Terapkan instruksi tambahan wajib PC/laptop; verifikasi blokir HP, tablet Android, iPad mode desktop dan dukungan laptop Windows layar sentuh.

## Alasan desain

Stage dominan meniru konteks percakapan; PiP kecil memberi konfirmasi kamera tanpa mengganggu interviewer. Chat terpisah memudahkan membaca ulang pertanyaan. Kontrol rekaman berada di stage agar chat dapat ditutup. Modal mengumpulkan kesiapan perangkat sebelum waktu sesi berjalan. Gerak karakter mengikuti audio; toggle dan reduced motion menjaga kendali pengguna.

## Verifikasi

22 tes backend lulus. Dua belas skenario controller lulus. Smoke Chrome terisolasi lulus sampai hasil empat turn, termasuk follow-up, serta memblokir tiga jenis perangkat mobile tanpa mengubah status sesi. Dua temuan review direproduksi sebagai tes gagal terlebih dahulu: toolbar layar pendek dan restore back-cache ketika state awal belum selesai; keduanya lolos setelah perbaikan. Pengujian tidak mengirim start/close ke sesi asli. Rincian teknis dan batas perangkat fisik tersedia di `docs/interview-room.md`.
