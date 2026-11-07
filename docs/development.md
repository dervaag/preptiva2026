# Panduan development

> Tinjauan dokumentasi: 7 November 2026, baseline `a4369f5`. [Status terkini dan batas verifikasi](current-state.md).

Gunakan Python 3.12, sesuai Docker/CI. [Status terkini](current-state.md) merangkum perilaku yang sudah diterapkan.

## Menjalankan lokal

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Hanya jika .env belum ada: cp .env.example .env
.venv/bin/python -m app.scripts.seed
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Jangan menimpa `.env` yang sudah berisi konfigurasi. Halaman akun/dashboard tidak memerlukan provider AI; wawancara nyata memerlukan OpenAI, ElevenLabs dan voice ID yang sesuai. `AI_MOCK=true` ditolak. `/dev-login` hanya untuk development setelah akun demo dibuat. Lihat [setup](setup.md).

## Titik perubahan

| Area | Berkas |
| --- | --- |
| Prompt dan validasi keluaran | `app/ai/orchestrator.py` |
| Cakupan dan persona | `app/ai/blueprint.py`, `guidebook.py`, `memory.py` |
| Bahasa jawaban/hasil dan penutup | `app/ai/answer_language.py`, `feedback.py`, `closing.py` |
| Bukti dan skor | `app/ai/scoring.py`, `job_rubric.py`, `assessment.py` |
| Graph dan recovery | `app/graphs/`, `app/worker/tasks.py`, `app/jobs.py` |
| Form, lifecycle, hasil | `app/static/js/app.js`, `session-setup.js`, `interview-room.js`, `result.js` |
| Bahasa UI | `app/static/js/ui-language.js` |
| Konfigurasi | `app/config.py`, `.env.example` |

Modul `prompts.py`, `types.py`, `delivery.py` atau task `evaluate_answer` bukan kontrak aktif saat ini. Evaluasi unit jawaban berjalan saat finalisasi.

## Pengujian tanpa kredit provider

```sh
.venv/bin/python -m unittest discover -s tests -v
node tests/room_controller_test.cjs app/static/js/interview-room.js
node tests/rubric_ui_test.js
node --check app/static/js/app.js
node --check app/static/js/interview-room.js
node --check app/static/js/result.js
```

Test Python memakai database sementara dan provider tiruan. Tes browser memerlukan paket `playwright` serta Chrome terpasang; `tests/result_visibility_smoke.py` menguji hasil bilingual/PDF tanpa akun atau provider produksi. Lihat [hasil](results.md) untuk cakupannya. Jangan menjalankan tes live dengan `--run-paid` tanpa memahami pemakaian kredit.

## Orkestrasi dan bahasa

`ORCHESTRATION_ENGINE=legacy|langgraph`, default `legacy`. Restart web/worker setelah konfigurasi berubah; hanya sesi baru yang memilih engine baru. Lihat [operasi graph](langgraph-orchestration.md).

Bahasa UI dan wawancara berbeda. Bahasa UI saat pembuatan sesi dipakai sebagai `feedback_language`. Jawaban dominan dalam bahasa berlawanan yang terdeteksi pasti menghasilkan `language_retry`; UI meminta ulang pada pertanyaan sama. Pertahankan jumlah pertanyaan, kuota follow-up, ownership dan status `running` pada cabang ini.

## Benchmark dan dokumentasi

[Benchmark Mohler](mohler-benchmark.md) memerlukan dependensi opsional `validation/requirements.txt` hanya untuk impor Parquet. Dataset/pilot lokal tidak ikut Git/image. Prompt benchmark terpisah dari evaluator produksi. Tidak ada metrik AI–manusia sampai run model dan report benar-benar dijalankan.

Perbarui dokumen terkait dan [changelog](CHANGELOG.md) pada perubahan perilaku. Jangan mengubah blok rubrik runtime hanya untuk merapikan prose; perubahan indikator/bobot memerlukan versi/snapshot dan peninjauan. Jangan commit `.env`, data kandidat, dataset lokal, byte audio atau kredensial.
