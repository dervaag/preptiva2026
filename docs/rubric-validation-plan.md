# Rencana rubrik berbasis referensi dan pengujiannya

Status 7 November 2026: **draf rubrik khusus dan implementasi teknis tersedia; tinjauan ahli serta penilaian manusia belum dilakukan**. Rubrik umum tetap `2026-11-05.2`; draf Engineering Manager/persona Manager menggunakan `2026-11-07.em.1` melalui pilihan eksplisit pada form. Keduanya `validated: false`.

Pembaruan 7 November 2026: pemisahan persona, guidebook pertanyaan, adaptasi berdasarkan CV/percakapan, dan panel telah diimplementasikan secara terpisah; lihat [guidebook](question-guidebook.md). Hal itu tidak menyelesaikan validasi rubrik oleh asesor yang direncanakan di dokumen ini.

Alat pembandingan dan format masukan asesor kini tersedia di [assessor-validation.md](assessor-validation.md). Implementasi bukti/cakupan/retry sesi ada di [panel-implementation.md](panel-implementation.md). Keduanya tidak menggantikan penilaian manusia. [Rubrik EM](engineering-manager-rubric.md) sudah memiliki lima kompetensi, 25 jangkar perilaku, pemetaan tugas/sumber dan bobot usulan. Ahli masih perlu meninjau semuanya; gold set bernilai manusia belum ada.

## Tujuan

Rubrik baru boleh disebut **berbasis referensi** jika setiap indikator skor dapat ditelusuri ke bagian sumber yang mendukungnya. Rubrik baru boleh disebut **telah diuji untuk suatu konteks** jika penerapannya oleh AI sudah dibandingkan dengan penilaian asesor manusia pada konteks tersebut. Mencantumkan tautan sumber di dokumen belum memenuhi keduanya.

Ruang lingkup tahap pertama: **satu pekerjaan dan satu persona — Engineering Manager, persona Manager.** Rubrik umum tujuh kompetensi tetap berjalan untuk pekerjaan lain sampai ada hasil pengujian.

## Kondisi saat ini

| Aspek | Sekarang | Target |
| --- | --- | --- |
| Sumber | Tiap indikator EM memiliki ID sumber, lokasi, kutipan pendek, penerapan, dan asal internal | Ahli meninjau ketepatan dan relevansinya untuk JD target |
| Kompetensi | Rubrik umum tetap tujuh; profil EM draf memiliki lima kompetensi khusus dari analisis pekerjaan publik | Kompetensi/bobot ditinjau ahli terhadap konteks pekerjaan target |
| Deskripsi skor | 25 jangkar perilaku konkret tersedia pada profil EM; tingkat rendah memerlukan bukti perilaku rendah eksplisit | Periksa kejelasan, keterpisahan tingkat dan konsistensi penggunaan oleh asesor |
| Keluaran evaluasi | Rantai skor → kutipan → indikator → gap → sumber tersedia untuk profil EM; kode memeriksa ID/level/quote | Tinjau relevansi semantik kutipan dan alasan bersama asesor |
| Pengujian | Tes perangkat lunak dan paket 20 kasus sintetis tanpa skor tersedia; lima kalibrasi, 15 uji | Sampel memadai yang dinilai minimal tiga asesor, konsensus, lima run AI dan audit fairness/STT |

## Langkah 1 — Tentukan kompetensi dari pekerjaan

1. Kumpulkan beberapa JD Engineering Manager yang relevan dengan target pengguna (bukan data pribadi kandidat).
2. Uraikan tanggung jawab utama, misalnya: menetapkan prioritas tim, memutuskan pendekatan teknis bersama tim, mengembangkan anggota tim, mengelola stakeholder, dan menjaga kualitas pengiriman.
3. Turunkan kompetensi dari tanggung jawab tersebut. Kandidat awal: **pengambilan keputusan**, **kepemimpinan tim**, **pengembangan orang**, **komunikasi stakeholder**, **penilaian teknis**.
4. Minta minimal satu orang yang memahami pekerjaan (EM/Head of Engineering aktif) meninjau daftar, menghapus yang tidak relevan, dan menetapkan bobot.
5. Catat matriks tanggung jawab → kompetensi beserta nama peran peninjau dan tanggal tinjauan (tanpa data pribadi lain).

Keluaran: daftar kompetensi EM dan bobotnya, dengan keterangan bahwa bobot adalah keputusan internal hasil tinjauan, bukan angka dari sumber.

## Langkah 2 — Petakan setiap indikator ke sumber

Setiap indikator dicatat dengan format berikut:

| Field | Isi |
| --- | --- |
| `indicator_id` | Contoh: `em.decision.l3.alternatives` |
| `source_title` | Judul dokumen |
| `source_edition` | Edisi/tahun |
| `source_locator` | Halaman atau bagian |
| `source_excerpt` | Kutipan singkat dari sumber |
| `application` | Bagaimana kutipan tersebut diterapkan pada indikator |
| `origin` | `taken` (diambil langsung), `adapted` (diadaptasi), atau `internal` (dibuat sendiri) |

Aturan:

- Bagian/halaman wajib dicek langsung di dokumen sumber, bukan dari ingatan atau ringkasan AI.
- Sumber metodologi (OPM, SIOP) umumnya menjelaskan *cara* menyusun indikator perilaku dan skala, bukan isi kompetensi EM. Indikator spesifik EM kemungkinan besar berstatus `adapted` atau `internal`; catat apa adanya.
- Jangan menganggap sumber menetapkan bobot, ambang label (Strong Match, Good, dst.), atau batas skor jika sumber tidak menyatakannya. Hal tersebut berstatus `internal`.
- ISO 10667-1 berbayar; jangan mengutip isinya tanpa akses ke dokumen resmi.

## Langkah 3 — Tulis indikator skor 1–5 yang konkret

Setiap tingkat berisi bukti yang dapat diperiksa dalam transkrip, bukan kata sifat umum.

Contoh internal (belum ditinjau ahli, belum tervalidasi) — **pengambilan keputusan**:

| Skor | Bukti yang dicari |
| --- | --- |
| 1 | Keputusan disebut tanpa alasan |
| 2 | Ada alasan, tetapi tidak ada alternatif yang dipertimbangkan |
| 3 | Ada alasan dan alternatif, tetapi pertimbangan risiko terbatas |
| 4 | Membandingkan alternatif dan risiko, trade-off disebut, hasil belum dievaluasi |
| 5 | Membandingkan alternatif, risiko, trade-off, dan mengevaluasi hasil keputusan |

Pedoman penulisan:

- Satu tingkat sebaiknya menambah satu atau dua unsur bukti dari tingkat sebelumnya agar alasan "belum mencapai tingkat berikutnya" dapat disebut secara spesifik.
- Pertahankan aturan yang berlaku: tidak adanya bukti bukan bukti ketidakmampuan, tanpa kutipan valid skor maksimal 2, dan code-switching Indonesia/English tidak menurunkan skor.
- Indikator harus ditinjau ahli pekerjaan sebelum dipakai untuk pengujian.

## Langkah 4 — Kumpulan jawaban acuan bernilai manusia

1. Siapkan 30–50 jawaban per kompetensi yang mencakup skor rendah, sedang, dan tinggi, termasuk jawaban Indonesia, English, dan campuran.
2. Gunakan jawaban sintetis atau jawaban dengan persetujuan tertulis yang sudah dianonimkan. Jangan menyimpan CV, transkrip asli, atau audio kandidat di repositori.
3. Minimal tiga asesor menilai setiap jawaban **secara terpisah** dengan rubrik dari langkah 3, mencatat skor, kutipan, dan indikator yang terpenuhi.
4. Hitung kesepakatan antarasesor. Bahas jawaban yang skornya berbeda lebih dari satu poin; jika perbedaannya karena indikator ambigu, perbaiki indikator lalu nilai ulang.
5. Skor konsensus menjadi acuan pembanding (gold set). Bagi set menjadi bagian kalibrasi (boleh dipakai sebagai contoh di prompt) dan bagian uji (tidak boleh masuk prompt).

## Langkah 5 — Uji AI terhadap penilaian manusia

Jalankan evaluator pada bagian uji gold set dan ukur:

| Uji | Cara ukur | Ambang awal (internal, dapat direvisi) |
| --- | --- | --- |
| Kesepakatan skor | Quadratic weighted kappa AI vs konsensus; persentase selisih ≤1 | Tidak lebih rendah dari kesepakatan antarasesor |
| Konsistensi | Jalankan setiap jawaban 5 kali; sebaran skor | ≥90% jawaban memiliki rentang skor ≤1 |
| Ketepatan kutipan | Kutipan ada di transkrip dan benar mendukung indikator yang diklaim | 100% kutipan ada di transkrip; dukungan dicek manual |
| Jawaban campuran | Bandingkan selisih AI–manusia pada jawaban Indonesia, English, dan campuran | Tidak ada pola penurunan skor pada jawaban campuran |
| Kesalahan STT | Jawaban sama dengan dan tanpa kesalahan transkripsi sintetis | Skor tidak turun hanya karena kesalahan STT |

Jika hasil di bawah ambang, perbaiki indikator atau prompt, naikkan versi rubrik, lalu uji ulang. Simpan ringkasan hasil (metrik, versi rubrik, model, tanggal) di changelog; data jawaban tetap di luar repositori.

## Perubahan aplikasi yang dibutuhkan

Keluaran per kompetensi menjadi:

```json
{
  "score": 3,
  "evidence": "kutipan persis dari transkrip",
  "indicators_met": ["em.decision.l3.alternatives"],
  "next_level_gap": "Risiko pilihan lain belum dibandingkan.",
  "sources": [{"indicator_id": "em.decision.l3.alternatives", "origin": "adapted", "source_title": "...", "source_locator": "..."}]
}
```

Rencana teknis:

- Simpan peta indikator → sumber di Markdown (blok terstruktur) agar tetap menjadi sumber rubrik yang dibaca runtime dan ikut disnapshot ke `interview_sessions.script.assessment`.
- Tambahkan field baru secara opsional di hasil skor (`app/ai/scoring.py`; `app/ai/types.py` tidak ada pada implementasi saat ini); sesi lama tanpa field tersebut tetap tampil seperti sekarang.
- Validasi di kode: `indicators_met` harus ID yang ada di snapshot sesi dan sesuai tingkat skor; `sources` diisi dari snapshot oleh kode, bukan dari teks LLM.
- Halaman hasil menampilkan rantai skor → kutipan → indikator → alasan belum naik tingkat → sumber.
- Rubrik EM hanya dipakai untuk sesi Engineering Manager + persona Manager; pekerjaan lain tetap memakai rubrik umum.
- Perubahan ini menaikkan versi rubrik di dokumen dan `app/ai/assessment.py`; snapshot sesi lama dipertahankan.

## Kriteria selesai

Rubrik EM boleh disebut "rubrik berbasis referensi yang telah diuji untuk konteks Engineering Manager (persona Manager)" jika:

- [ ] Daftar kompetensi dan bobot sudah ditinjau ahli pekerjaan.
- [ ] Setiap indikator memiliki sumber, bagian/halaman, kutipan, penerapan, dan status asal.
- [ ] Gold set dinilai minimal tiga asesor secara terpisah, dengan kesepakatan antarasesor tercatat.
- [ ] Hasil uji AI memenuhi ambang di langkah 5 atau batasannya dicatat dengan jelas.
- [ ] Aplikasi menampilkan rantai keluaran lengkap dan menandai `validated` hanya untuk konteks yang diuji.

Klaim tersebut tidak berlaku untuk pekerjaan atau persona lain, dan tetap bukan validasi sebagai alat seleksi kerja nyata tanpa studi validitas terhadap kinerja kerja.

## Implementasi teknis yang tersedia

- Form hanya menawarkan **Rubrik khusus Engineering Manager (draf)** untuk judul Engineering Manager dan interviewer tunggal Manager. Pilihan dimatikan secara default; konteks lain/panel tetap memakai rubrik umum. Server juga menolak scope yang tidak cocok.
- Lima fokus: pengambilan keputusan, kepemimpinan tim, pengembangan orang, komunikasi stakeholder, penilaian teknis. Nama khusus terikat pada snapshot; key penyimpanan lama tidak mengubah arti hasil historis.
- Snapshot mencakup indikator, sumber, ruang lingkup, aturan, bobot dan status draf. Hash mencakup keseluruhan snapshot, sehingga perubahan indikator/bobot/sumber tidak tercampur pada perbandingan hasil. Blueprint 5/7 pertanyaan mencakup lima kompetensi; sesi tiga pertanyaan hanya mencakup sebagian.
- Evaluator meminta indikator pada tingkat skor yang sama, kutipan per giliran, kecukupan bukti dan alasan belum naik tingkat. Keluaran struktural tidak lengkap diberi satu kesempatan perbaikan; kegagalan berikutnya mempertahankan jawaban dan menyediakan penilaian ulang.
- Sumber di halaman hasil diambil oleh kode dari snapshot, bukan URL yang dikarang model. Pemeriksaan literal/ID/level bukan pemeriksaan relevansi semantik oleh ahli. Tidak adanya contoh bukan bukti perilaku rendah.
- Perangkat asesor menyediakan paket offline tanpa skor AI, penggabungan rating, template konsensus kosong setelah tiga asesor, impor keputusan koordinator, runner AI lima kali, dan laporan dengan pengecualian/denominator untuk bukti kurang. Tidak ada konsensus atau rating manusia yang diisi otomatis.

Seluruh kriteria tinjauan manusia di atas tetap terbuka. Dua puluh contoh sintetis hanya menyiapkan proses, tidak menggantikan usulan sampel lebih besar yang harus disetujui ahli. Mengaktifkan opsi draf tidak mengaktifkan status validated.
