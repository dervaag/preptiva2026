# Menyiapkan pembandingan AI–asesor

Status 7 November 2026: alat analisis siap, **penilaian manusia belum dilakukan**. Alat ini tidak memberikan sertifikasi atau mengubah flag `validated`. Rencana pengambilan sampel, indikator, dan peninjauan ahli tetap mengikuti [rubric-validation-plan.md](rubric-validation-plan.md).

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
4. Jalankan evaluator pada kasus uji minimal lima kali dengan konfigurasi yang dicatat. Isi skor `ai_runs` dan semua kutipan yang ingin diaudit di `ai_quotes`; belum tersedia runner AI otomatis untuk dataset ini.
5. Jalankan `python3 validation/compare.py /path/private-dataset.json --output /path/report.json`.

Laporan memuat quadratic weighted kappa pasangan asesor, kappa AI run pertama terhadap konsensus, persentase selisih maksimal satu poin, persentase rentang lima run maksimal satu poin, keberadaan kutipan literal, serta galat per bahasa. Kappa menjadi `null` jika distribusi konstan sehingga tidak terdefinisi. Keberadaan kutipan tidak membuktikan relevansinya; relevansi terhadap indikator tetap diperiksa manusia. Statistik kelompok kecil bukan bukti fairness.

Input dengan skor kosong, kurang dari tiga asesor, kasus kalibrasi, ID ganda, atau kurang dari lima run ditolak. Dua kasus adalah minimum komputasi, **bukan ukuran sampel yang cukup untuk validasi**. Target 30–50 jawaban per kompetensi dalam rencana tetap merupakan usulan awal yang perlu ditinjau ahli. Laporan selalu `validated: false`; keputusan kelayakan konteks memerlukan tinjauan hasil, cakupan sampel, konsistensi, fairness dan sensitivitas STT.
