# Orkestrasi LangGraph Preptiva

Implementasi `langgraph-v1` menambahkan tiga graph di atas fungsi AI, database, FastAPI, dan Redis/arq yang sudah ada. Default konfigurasi tetap `ORCHESTRATION_ENGINE=legacy`; sesi baru dapat memakai `langgraph`. Tidak ada perubahan status validasi rubrik: panel AI dan persetujuan antar-model bukan penilaian tiga asesor manusia.

## Versi sesi dan aktivasi

Gunakan Python **3.12**, sama dengan Docker dan CI, lalu instal `requirements.txt`. Paket LangGraph dipin agar implementasi checkpoint diuji terhadap versi yang jelas.

```dotenv
ORCHESTRATION_ENGINE=langgraph
```

Pilihan engine, versi graph, kebijakan agregasi dan pemulihan disimpan ke `session.script.runtime` saat sesi dibuat. Mengubah environment hanya memengaruhi sesi baru. Sesi yang sudah berjalan tetap memakai engine dan snapshot sebelumnya; sesi historis tanpa metadata graph menggunakan alur legacy. Tren hasil membedakan versi agregasi agar perubahan perhitungan tidak dianggap sebagai perubahan kemampuan kandidat.

Pada Kiri, konfigurasi deployment berada di `~/Library/Application Support/PreptivaDeploy/shared/.env`, terpisah dari `.env` IDE. Setelah kode graph tersedia pada release yang telah diuji, ubah konfigurasi shared dan lakukan deployment ulang agar **web dan worker** memakai environment yang sama. Push branch enhancement sendiri tidak memicu deployment `main`. Untuk menghentikan penggunaan graph pada sesi baru, kembalikan flag ke `legacy`; jangan menghapus metadata sesi atau tabel graph untuk memaksa migrasi sesi aktif.

## Tiga graph

| Graph | Node utama | Sumber kebenaran aplikasi |
| --- | --- | --- |
| Persiapan | Validasi → ekstraksi CV/JD → konteks kandidat → rencana cakupan → pertanyaan → audio → commit siap | Snapshot sesi dan tabel pertanyaan |
| Satu giliran | Terima transkrip → konteks bersama → usulan respons → koordinator tervalidasi → pertanyaan/audio → commit jawaban | Transkrip diterima, jawaban dan pertanyaan aktif |
| Finalisasi | Ambil sumber → penilaian awal tiap persona → tinjau perbedaan → agregasi → feedback → commit hasil | Jawaban asli, snapshot rubrik dan hasil tersimpan |

Fungsi `orchestrator.parse_documents`, `build_questions`, `respond`, `adapt_question`, `evaluate`, `summarize`, serta provider suara tetap digunakan. API browser tetap mengirim hasil melalui format yang sudah ada. Persiapan menggunakan CV/JD asli dari sesi; checkpoint graph tidak menyalin dokumen penuh atau byte audio pada setiap node.

Koordinator mempertahankan ID dan urutan nomor pertanyaan. Ia dapat menukar **konten dua slot utama yang belum dijawab** untuk mendahulukan kompetensi yang belum ditanyakan, tanpa mengubah jumlah alokasi persona. Slot terakhir tetap memiliki persona penutup yang direncanakan. Follow-up hanya diberikan kepada persona pertanyaan utama dan mengikuti batas snapshot. Usulan action, sumber kutipan dan pertanyaan HR diperiksa kode; model tidak dapat menambah persona atau mengakhiri sesi sebelum waktunya.

Handoff memuat alasan perpindahan, kompetensi sasaran, dan kutipan dengan ID giliran asli. Pernyataan kandidat tetap diberi label belum diverifikasi. Status cakupan seperti `asked_not_yet_scored` hanya berarti topik sudah ditanyakan, bukan bahwa kompetensi sudah terukur. Generator berikutnya menerima jawaban yang telah tersedia agar dapat menggali aspek yang belum dijelaskan tanpa meminta kandidat mengulangnya.

## Penilaian panel dan agregasi

Kebijakan baru: `panel-evidence-equal-persona-v1`.

1. Setiap persona menilai unit jawaban utama beserta follow-up yang masuk lingkup bobot personanya. Unit yang sama menggunakan sumber jawaban yang sama. Penilaian awal tidak menerima skor persona lain.
2. Kutipan, indikator dan kecukupan bukti diperiksa menggunakan pemeriksa yang sudah ada. Unit dilewati tetap tanpa penilaian; bukti kurang tidak menjadi skor terukur.
3. Setelah seluruh penilaian awal tersimpan, selisih skor minimal dua poin atau perbedaan kecukupan bukti dapat memicu tinjauan. Tinjauan bersifat saran dan harus merujuk sumber asli. Skor awal tidak ditimpa atau dipaksa menjadi konsensus.
4. Agregasi menghitung rata-rata unit terukur per kompetensi di dalam masing-masing persona, kemudian rata-rata dengan bobot setara antar-persona yang memiliki bukti terukur. Skor total menggunakan bobot kompetensi dari snapshot sesi, dinormalisasi ke kompetensi terukur.
5. Hasil penilaian awal, tinjauan, sumber dan versi kebijakan tersedia dalam `review.panel_assessment`. Halaman hasil tetap menampilkan skor serta feedback otomatis; panel rinci juga tersedia di respons API hasil.

Perhitungan ini sengaja berbeda dari legacy yang menilai unit terutama melalui persona penanya. Jumlah evaluasi dapat meningkat pada panel. Bukti bahwa suatu kutipan berasal dari transkrip tidak membuktikan ketepatan interpretasi psikometriknya. Rubrik umum dan EM tetap `validated: false`; Mohler tetap benchmark akademik terpisah.

## Checkpoint, idempotensi dan pemulihan

LangGraph menyimpan kemajuan eksekusi per thread melalui checkpointer persisten. Preptiva memakai saver SQLAlchemy dengan JSON saja pada database aplikasi, bukan `MemorySaver` yang hilang saat proses berhenti. Pemisahan state thread dan data aplikasi mengikuti konsep [persistence LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence).

Tabel baru bersifat aditif: `graph_executions`, `graph_operations`, `graph_checkpoints`, `graph_checkpoint_writes`, dan `graph_turn_inputs`. `init_db()` membuat tabel yang belum ada. PostgreSQL tetap database deployment; pengujian dasar dapat memakai SQLite sementara. Tabel jawaban/sesi tetap otoritas status domain. Ledger operasi menyimpan hasil yang sudah selesai; checkpoint hanya menyimpan referensi thread/sesi/node. Tidak ada pickle atau pemuatan objek Python dari model.

Thread dipetakan secara deterministik:

```text
prepare:<session_id>:v1
turn:<session_id>:<question_id>:<attempt>:<input_hash_prefix>:v1
finalize:<session_id>:v1
```

Percobaan pertanyaan berubah melalui Retry/Next yang sah. Kunci operasi memisahkan node dan payload; input berbeda tidak boleh menggantikan operasi yang sudah memiliki hasil. Lease database mencegah dua worker memproses thread yang sama bersamaan. Commit aplikasi memeriksa ulang status dan jawaban yang sudah ada, sehingga crash sesudah commit tetapi sebelum checkpoint tidak membuat pertanyaan/jawaban ganda.

Panggilan berbayar yang telah selesai dan tersimpan dipakai ulang. Jika proses berhenti ketika panggilan provider masih berlangsung, hasilnya dianggap **belum diketahui**, bukan gagal tanpa biaya. Retry otomatis tidak dapat menjamin efek eksternal tepat satu kali; tanggung jawab idempotensi dan kasus acknowledgment yang hilang juga dijelaskan dalam [fault tolerance LangGraph](https://docs.langchain.com/oss/python/langgraph/fault-tolerance). Preptiva menghentikan operasi ambigu sampai operator mengakui kemungkinan panggilan berulang.

| Kejadian | Perilaku |
| --- | --- |
| Tab tersembunyi, offline, reload atau perangkat putus | Pertanyaan aktif berhenti; browser menawarkan Retry/Next |
| Kandidat memilih Retry | Pertanyaan yang sama dengan waktu penuh; percobaan sebelumnya tidak dapat menghidupkan rekaman |
| Kandidat memilih Next | Pertanyaan dilewati tanpa skor |
| Tahap backend gagal sesudah transkrip tersimpan | Data tetap ada; lanjutkan tahap yang belum berhasil dengan thread yang sama |
| Worker berhenti | Pemulihan saat startup/pemeriksaan berkala menunggu lease berakhir, kemudian memakai hasil operasi yang sudah selesai |
| Operasi provider ambigu | Perlu tindakan operator; tidak diulang diam-diam |

Resume graph **tidak** menyalakan mikrofon, memutar ulang audio, atau meneruskan sisa waktu browser. Pemulihan worker juga tidak melewati checkpoint domain `interrupted`. Pengguna tetap mengendalikan Retry/Next.

## Pemeriksaan dan retry operator

Gunakan environment database deployment yang benar. CLI berikut hanya mencetak metadata operasi, bukan isi CV, transkrip, prompt, atau kunci API:

```bash
python -m app.graphs.manage inspect --session SESSION_UUID
python -m app.graphs.manage retry --session SESSION_UUID --thread THREAD_ID
```

Untuk container Kiri yang sudah memuat release graph:

```bash
docker --context kiri exec preptiva-web-1 python -m app.graphs.manage inspect --session SESSION_UUID
```

Jika hasil inspeksi menunjukkan operasi ambigu, periksa log/provider dan batas biaya terlebih dahulu. Opsi berikut secara eksplisit mengizinkan pengulangan panggilan yang hasil sebelumnya belum diketahui:

```bash
python -m app.graphs.manage retry --session SESSION_UUID --thread THREAD_ID --acknowledge-possible-charge
```

Thread harus berasal dari hasil `inspect` dan milik sesi yang sama. CLI menolak melanjutkan giliran yang sudah diinterupsi atau sesi yang sudah ditutup. Jika STT ambigu terjadi sebelum transkrip tersimpan, opsi acknowledgment memberi izin satu kali yang tercatat pada thread. Kandidat kemudian mengirim ulang audio yang sama dari browser; izin dikonsumsi saat eksekusi memperoleh lease. Mikrofon tidak dinyalakan otomatis dan audio mentah tidak dimasukkan ke checkpoint. Rekaman berbeda yang belum pernah diterima memakai thread berbeda; setelah transkrip diterima, payload berbeda pada pertanyaan/percobaan yang sama ditolak.

Metadata menyertakan node/operasi, durasi, jumlah percobaan, error type, model dan token yang dikembalikan provider. Nilai token yang tidak dikembalikan provider tidak diisi dengan perkiraan. Metadata dapat digunakan untuk audit dan perbandingan, tetapi belum ada dashboard monitoring atau retensi checkpoint otomatis. Akses database/ledger harus diperlakukan seperti akses data wawancara karena hasil operasi dapat berisi ringkasan dan kutipan kandidat.

## Benchmark sebelum rollout luas

Benchmark sintetis dapat diulang tanpa API berbayar:

```bash
python validation/orchestration_benchmark.py --repeats 3 --output /tmp/preptiva-orchestration-benchmark.json
```

Setiap sampel memakai proses baru dan SQLite sementara, CV/JD/jawaban serta seed rencana yang sama, tiga pertanyaan, interviewer tunggal atau panel tiga persona, dan input audio → teks → audio. Seluruh provider diganti dengan fungsi sintetis; akses jaringan provider diblokir. Laporan menyimpan hash fixture/source, durasi per tahap, median/mean, jumlah langkah provider logis dan metadata node graph. Startup proses dan import sebelum tahap tidak dimasukkan; inisialisasi graph pertama dan import malas di dalam tahap tetap terukur. Ini belum mengukur worker yang sudah menjalankan graph sebelumnya. Benchmark menolak laporan jika source berubah di tengah pengujian.

Angka ini hanya mengukur tambahan kerja aplikasi/graph/database pada fixture dengan provider yang segera menjawab. `logical_provider_steps` menghitung pemanggilan fungsi orkestrasi, **bukan jumlah request model nyata**; satu fungsi dapat menjalankan beberapa request dalam produksi. Token, biaya uang, latensi jaringan/STT/TTS, transport audio dan kualitas skor tidak diukur, sehingga bidang biaya/token tetap `null`. Jangan menyimpulkan LangGraph lebih cepat atau pertanyaan lebih baik dari laporan ini.

Baseline lokal 7 November 2026 (3 ulangan per skenario, 12 sampel): median tiga pertanyaan tunggal 29,188 ms legacy vs 485,154 ms graph; panel tiga persona 26,250 ms vs 489,559 ms. Tambahan sekitar 456–463 ms mencakup inisialisasi graph pertama dan SQLite pada mesin pengujian ini. Pada fixture panel tersebut, evaluasi logis bertambah dari 3 menjadi 8 karena penilaian silang sesuai lingkup persona. Rincian fase, hash source/fixture dan batas pengukuran tersimpan di [baseline sintetis](../artifacts/langgraph-synthetic-baseline.json).

Pembandingan nyata masih memerlukan sampel yang diizinkan, model dan prompt yang dipin, batas biaya, tarif provider pada tanggal pengujian, serta pencatatan usage aktual. Bandingkan fase yang sama dan laporkan pekerjaan tambahan penilaian panel, bukan hanya total waktu. Penilaian kualitas pertanyaan dan kesesuaian skor memerlukan uji terpisah dengan tinjauan manusia. Benchmark Mohler tidak menggantikan pengujian evaluator interview produksi.
