# Menyiapkan pembandingan AI–asesor

Status 7 November 2026: alat analisis dan paket penilaian tanpa skor AI siap, **asesor belum tersedia dan penilaian manusia belum dilakukan**. Alat ini tidak memberikan sertifikasi atau mengubah flag `validated`. Rencana pengambilan sampel, indikator, dan peninjauan ahli tetap mengikuti [rubric-validation-plan.md](rubric-validation-plan.md).

`validation/compare.py` membaca dataset lokal dan menghasilkan statistik deskriptif tanpa memanggil provider AI. Simpan jawaban nyata/hasil penilaian di luar repository. Gunakan pseudonim asesor. Contoh berikut sengaja tidak diisi skor agar tidak disalahartikan sebagai penilaian manusia yang sudah dilakukan:

```json
{
  "rubric_version": "2026-11-05.2",
  "rubric_sha256": "isi hash snapshot yang diuji",
  "model": "isi model dan versi prompt yang diuji",
  "cases": [
    {
      "id": "em-001",
      "split": "test",
      "competency": "leadership",
      "language": "id",
      "transcript": "Isi jawaban asli/sintetis yang akan dinilai.",
      "human_ratings": {"assessor-a": null, "assessor-b": null, "assessor-c": null},
      "consensus_score": null,
      "ai_runs": [],
      "ai_quotes": []
    }
  ]
}
```

1. Tentukan konteks pekerjaan/persona, indikator dan sampel bersama ahli. Pisahkan data kalibrasi dan uji sebelum menyesuaikan prompt.
2. Minta sekurangnya tiga asesor yang sama menilai setiap kasus secara independen pada skala 1–5. Jangan memperlihatkan skor AI sebelum penilaian independen selesai.
3. Catat konsensus setelah pembahasan perbedaan. Simpan skor independen asli.
4. Jalankan evaluator pada kasus uji minimal lima kali dengan konfigurasi yang dicatat. Isi skor `ai_runs` dan semua kutipan yang ingin diaudit di `ai_quotes`; runner opt-in tersedia melalui `validation/kit.py run-ai` (lihat di bawah).
5. Jalankan `python3 validation/compare.py /path/private-dataset.json --output /path/report.json`.

Laporan memuat quadratic weighted kappa pasangan asesor, kappa AI run pertama terhadap konsensus, persentase selisih maksimal satu poin, persentase rentang lima run maksimal satu poin, keberadaan kutipan literal, serta galat per bahasa. Kappa menjadi `null` jika distribusi konstan sehingga tidak terdefinisi. Keberadaan kutipan tidak membuktikan relevansinya; relevansi terhadap indikator tetap diperiksa manusia. Statistik kelompok kecil bukan bukti fairness.

Input dengan skor kosong, kurang dari tiga asesor, kasus kalibrasi, ID ganda, atau kurang dari lima run ditolak. Dua kasus adalah minimum komputasi, **bukan ukuran sampel yang cukup untuk validasi**. Target 30–50 jawaban per kompetensi dalam rencana tetap merupakan usulan awal yang perlu ditinjau ahli. Laporan selalu `validated: false`; keputusan kelayakan konteks memerlukan tinjauan hasil, cakupan sampel, konsistensi, fairness dan sensitivitas STT.

## Paket penilaian tanpa skor AI

`validation/kit.py` membuat HTML mandiri untuk dibuka offline. Tiap asesor mendapat pseudonim berbeda, konteks pekerjaan/level, snapshot rubrik, pertanyaan, transkrip dan kompetensi yang dinilai. Skor AI, konsensus, dan skor asesor lain tidak dimasukkan ke HTML. Form tidak mengirim data ke server atau menyimpan jawaban otomatis; asesor mengunduh JSON sebelum menutup halaman.

Paket awal lokal `data/assessor-kit-2026-11-07/` berisi `assessor-a.html`, `assessor-b.html`, `assessor-c.html`, dan dataset koordinator. Arsip `packets.zip` hanya memuat tiga formulir kosong dan petunjuk. Isinya tujuh contoh sintetis Engineering Manager, satu per kompetensi, dalam bahasa Indonesia/Inggris/campuran. Ini latihan alur kerja dan bahan tinjauan awal, **bukan gold set, penilaian manusia, atau sampel validasi yang memadai**. Belum ada asesor yang diundang atau hasil penilaian yang diisi. Pseudonim perlu ditetapkan koordinator kepada tiga orang berbeda.

Untuk membuat paket baru (perintah menolak menimpa file yang sudah ada):

```sh
python3 validation/kit.py init --output data/assessor-new/dataset.json
python3 validation/kit.py pack data/assessor-new/dataset.json --assessor assessor-a --output data/assessor-new/assessor-a.html
python3 validation/kit.py pack data/assessor-new/dataset.json --assessor assessor-b --output data/assessor-new/assessor-b.html
python3 validation/kit.py pack data/assessor-new/dataset.json --assessor assessor-c --output data/assessor-new/assessor-c.html
```

Asesor memilih skor 1–5 dengan kutipan asli dan alasan yang mengacu indikator, atau **bukti belum cukup** tanpa skor. Kutipan harus ditemukan verbatim di jawaban. Asesor mengonfirmasi bahwa ia menilai sendiri secara independen. Pernyataan form bukan verifikasi identitas; koordinator tetap memeriksa independensi dan kualifikasi.

Setelah semua JSON diterima:

```sh
python3 validation/kit.py merge data/assessor-new/dataset.json /path/ratings-assessor-a.json /path/ratings-assessor-b.json /path/ratings-assessor-c.json --output data/assessor-new/human-rated.json
```

Penggabungan memeriksa hash rubrik/konteks/kasus, kasus lengkap, asesor unik, skor/status, kutipan dan alasan; skor asesor yang sudah masuk tidak boleh ditimpa. Konsensus tetap kosong dan harus ditetapkan setelah pembahasan. Status bukti kurang disimpan sebagai `null`; alat statistik menolaknya. Jangan mengganti dengan skor buatan: tinjau kecukupan sampel dan catat alasan eksklusi sebelum membentuk himpunan uji yang dapat dibandingkan.

Runner AI memakai evaluator yang sama tanpa memasukkan skor manusia ke prompt, lima panggilan per kasus, dan menyimpan skor terverifikasi, status serta kutipan:

```sh
.venv/bin/python validation/kit.py run-ai data/assessor-new/human-rated.json --run-paid --output data/assessor-new/ai-rated.json
python3 validation/compare.py data/assessor-new/ai-rated.json --output data/assessor-new/comparison.json
```

`run-ai` mengonsumsi kredit API; contoh tujuh kasus berarti 35 panggilan evaluator. Belum dijalankan pada paket awal. Bila model tidak memberikan bukti yang cukup, hasil AI tetap `null` dan laporan komparasi tidak boleh dipaksakan. Semua perintah mempertahankan `validated: false`. Direktori `data/` diabaikan Git dan tidak masuk image deployment; hasil nyata tetap lokal, bukan artefak publik CI.
