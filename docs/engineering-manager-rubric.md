# Rubrik Engineering Manager — persona Manager

Versi `2026-11-07.em.1`, disusun 7 November 2026. **Draf internal untuk latihan dan tinjauan ahli; belum ditinjau ahli pekerjaan dan belum divalidasi.** Penggunaan draf harus dipilih secara eksplisit. Rubrik umum dan snapshot sesi lama tetap berlaku untuk konteks lain.

Lima kompetensi di bawah memakai key penyimpanan yang sudah ada, tetapi definisi dan jangkar penilaiannya khusus lingkup kerja Engineering Manager. Key `teamwork` berarti kepemimpinan tim dalam profil ini, dan `leadership` berarti pengembangan orang. Ini bukan perubahan arti untuk sesi dengan rubrik umum. Bobot 25/20/20/20/15 adalah usulan internal; sumber tidak menetapkan bobot tersebut.

## Asal dan batas sumber

[OPM Structured Interviews](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews.pdf) dipakai untuk metode menyusun jangkar perilaku dan tinjauan ahli. [SIOP/APA Principles 2018](https://www.apa.org/ed/accreditation/about/policies/personnel-selection-procedures.pdf) dipakai untuk hubungan penilaian dengan analisis pekerjaan. [SIOP AI 2023](https://www.siop.org/wp-content/uploads/legacy/SIOP%20Considerations%20and%20Recommendations%20for%20the%20Validation%20and%20Use%20of%20AI-Based%20Assessments%20for%20Employee%20Selection%20010323.pdf) mendukung pencatatan sumber, proses dan studi pengujian. [ISO 10667-1:2020](https://www.iso.org/standard/74716.html) hanya dibaca melalui abstrak publik untuk tujuan dan pengelolaan asesmen; isi standar berbayar tidak dikutip.

Analisis tugas awal membandingkan dua organisasi: [GitLab Engineering Manager](https://handbook.gitlab.com/job-description-library/engineering/development/management/engineering-manager/) dan [Monzo Engineering Manager Framework v2.0](https://monzo.com/documents/engineering-manager-framework-v2-0.pdf). Penilaian teknis juga mempertimbangkan [penjelasan Monzo tentang peran teknis EM](https://monzo.com/blog/what-are-monzos-technical-expectations-for-engineering-leaders). Dokumen ini membantu mengidentifikasi tugas untuk ditinjau; bukan representasi semua perusahaan, bukan JD yang telah disetujui untuk target pengguna, dan bukan dasar menyetarakan jenjang karier perusahaan dengan skor 1–5.

Setiap sumber memiliki bagian/halaman, cuplikan pendek dan batas penggunaan di blok terstruktur. Semua 25 jangkar diberi `origin: internal`: kalimat, batas antarskor dan contoh perilaku disusun untuk Preptiva, bukan diambil sebagai skala resmi dari organisasi sumber. `source_ids` menghubungkan metode dan relevansi tugas, bukan menyatakan bahwa sumber memvalidasi indikator. Asesor perlu memeriksa apakah tugas dan standar bukti cocok dengan JD target.

## Cara membaca hasil

Rantai hasil yang dituju adalah **skor → kutipan asli → indikator yang didukung → bukti yang belum tersedia untuk tingkat berikutnya → sumber dan asal indikator**. Kecocokan kutipan secara tekstual tidak membuktikan relevansi semantiknya. Penilaian kualitas tetap perlu dibandingkan dengan asesor independen.

Tingkat 1/2 hanya dipakai sebagai skor terukur jika jawaban menunjukkan tindakan rendah yang eksplisit. Ketiadaan bukti dipisahkan sebagai bukti belum cukup. Tingkat 5 menerima hasil kualitatif yang jelas; angka bukan syarat mutlak. Pertanyaan hipotetis dapat memperlihatkan keputusan dan rencana, tetapi rencana tidak boleh disebut hasil nyata. Untuk menghindari batas skor akibat rancangan pertanyaan, penguji perlu menawarkan penggalian pengalaman atau bukti hasil yang sesuai sebelum menafsirkan cakupan skor.

## Sumber runtime terstruktur

Blok ini menjadi sumber profil draf dan harus disalin ke snapshot sesi/paket penilaian. Perubahan isi memerlukan versi dan hash baru. Tidak ada flag `validated: true` atau nama asesor yang diisi otomatis.

<!-- em-rubric:start -->
{
  "version": "2026-11-07.em.1",
  "id": "engineering_manager_manager",
  "title": "Engineering Manager — persona Manager (draf latihan)",
  "scope": {
    "job_roles": [
      "Engineering Manager"
    ],
    "interviewer": "manager",
    "panel": [
      "manager"
    ]
  },
  "status": "draft_pending_expert_review",
  "validated": false,
  "job_reviewed_by_human": false,
  "source_checked_at": "2026-11-07",
  "weights": {
    "problem_solving": 25,
    "teamwork": 20,
    "leadership": 20,
    "communication": 20,
    "technical": 15
  },
  "weight_origin": "internal_proposal_pending_expert_review",
  "scoring_rules": [
    "Gunakan hanya pada konteks Engineering Manager dan satu persona Manager yang secara eksplisit memilih draf ini. Ini latihan pengembangan, bukan prediksi seleksi kerja.",
    "Nilai bukti perilaku per kompetensi dari satu pertanyaan utama beserta follow-up; jangan menghukum ketiadaan pengalaman kerja berbayar, jabatan formal, bawahan, angka hasil atau kesempatan mempraktikkan skenario.",
    "Jangkar 1–5 adalah alternatif kualitas bukti dalam lingkup EM yang sama, bukan level jabatan. Tingkat 4/5 tidak harus membuktikan perilaku negatif tingkat 1/2. Jika disebut memenuhi tingkat sebelumnya, yang dimaksud hanya syarat positif pada tingkat yang dirujuk.",
    "Pilih jangkar tertinggi yang seluruh unsur pokoknya ditunjang kutipan literal dan penjelasan. Bila unsur tingkat berikutnya belum terlihat, nyatakan belum ada bukti di jawaban; jangan menyimpulkan kandidat tidak mampu.",
    "Skor 1 atau 2 yang terukur memerlukan kutipan perilaku rendah yang eksplisit. Jawaban terlalu singkat, tidak menjawab, atau bukti tidak cukup berstatus insufficient/not_assessed tanpa skor terukur.",
    "Kutipan harus berasal dari satu giliran asli; indikator hanya boleh memakai ID pada snapshot ini dan sesuai kompetensi serta tingkat skor. Jangan mengarang sumber, fakta atau hasil.",
    "Hasil kualitatif yang dapat diterangkan dapat memenuhi tingkat 5. Angka, nama perusahaan, ukuran tim, aksen, usia, gender, kepribadian, perpindahan tab dan campuran bahasa tidak otomatis menaikkan atau menurunkan skor.",
    "Untuk skenario hipotetis, bedakan rencana verifikasi dari hasil yang sudah terjadi. Jangan mengklaim rencana sebagai hasil nyata. Pertanyaan yang tidak memberi kesempatan menunjukkan unsur tingkat tinggi perlu diperbaiki, bukan dipakai membatasi kemampuan kandidat.",
    "Metode dan sumber pekerjaan mendukung desain awal; relevansi, tingkat kesulitan, keterpisahan kompetensi serta bobot masih menunggu tinjauan ahli dan penilaian independen."
  ],
  "sources": [
    {
      "id": "opm-rating",
      "title": "U.S. OPM — Structured Interviews",
      "url": "https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews.pdf",
      "edition": "Materi presentasi, tanggal edisi tidak tercantum",
      "locator": "Slide 9 (analisis pekerjaan), 23–25 (skala perilaku), 26–27 (pilot dan dokumentasi); nomor slide sama dengan halaman PDF",
      "excerpt": "Determine behavioral examples for each proficiency level",
      "scope": "Metode menyusun jangkar perilaku dan meninjau contoh bersama ahli; tidak menyediakan indikator atau bobot Engineering Manager."
    },
    {
      "id": "siop-principles-2018",
      "title": "SIOP/APA — Principles for the Validation and Use of Personnel Selection Procedures",
      "url": "https://www.apa.org/ed/accreditation/about/policies/personnel-selection-procedures.pdf",
      "edition": "Fifth Edition, August 2018",
      "locator": "Analysis of Work, halaman cetak 7–8 (PDF 15–16); Content-Based Evidence, halaman cetak 16 (PDF 24)",
      "excerpt": "understand the work performed",
      "scope": "Analisis pekerjaan dan hubungan isi penilaian dengan tuntutan pekerjaan; dokumen pekerjaan publik tetap perlu diperiksa relevansinya oleh ahli konteks lokal."
    },
    {
      "id": "siop-ai-2023",
      "title": "SIOP — Considerations and Recommendations for the Validation and Use of AI-Based Assessments for Employee Selection",
      "url": "https://www.siop.org/wp-content/uploads/legacy/SIOP%20Considerations%20and%20Recommendations%20for%20the%20Validation%20and%20Use%20of%20AI-Based%20Assessments%20for%20Employee%20Selection%20010323.pdf",
      "edition": "January 2023",
      "locator": "Bagian 4.5.1, halaman 25; Bagian 5 dan 5.1.1–5.1.3, halaman 29–30; nomor halaman cetak sama dengan halaman PDF",
      "excerpt": "document all steps in the process",
      "scope": "Keterlacakan data, versi, proses penilaian dan studi validasi; bukan jaminan bahwa keluaran AI atau kutipan yang cocok sudah valid."
    },
    {
      "id": "iso10667-abstract",
      "title": "ISO 10667-1:2020 — Assessment service delivery, Part 1: Requirements for the client",
      "url": "https://www.iso.org/standard/74716.html",
      "edition": "Edition 2, November 2020",
      "locator": "Abstrak publik, butir a–e; isi standar dan Annex B/C tidak diakses",
      "excerpt": "the needs and rationale for using assessments",
      "scope": "Tujuan, konteks penggunaan, kompetensi pelaksana dan pengelolaan hasil. Abstrak saja; tidak menjadi sumber indikator, bobot, klaim kepatuhan atau sertifikasi."
    },
    {
      "id": "gitlab-em",
      "title": "GitLab Handbook — Engineering Manager",
      "url": "https://handbook.gitlab.com/job-description-library/engineering/development/management/engineering-manager/",
      "edition": "Halaman handbook berjalan, diperiksa 7 November 2026",
      "locator": "Pembuka, Responsibilities dan Requirements",
      "excerpt": "Help your engineers grow their skills and experience",
      "scope": "Contoh konteks pekerjaan: pengelolaan tim, coaching, umpan balik, koordinasi, keputusan teknis dan perbaikan kualitas. Persyaratan khusus GitLab tidak dijadikan syarat universal."
    },
    {
      "id": "monzo-em-v2",
      "title": "Monzo — Engineering Manager Progression Framework v2.0",
      "url": "https://monzo.com/documents/engineering-manager-framework-v2-0.pdf",
      "edition": "Version 2.0, tanggal edisi tidak dicantumkan",
      "locator": "Foreword (PDF 1–2) dan Engineering Manager Level 50 (PDF 3–4), kolom Team and execution, People, Leadership",
      "excerpt": "Sets meaningful development goals and milestones for their reports.",
      "scope": "Contoh lingkup manajer tim: tujuan kerja, pengembangan anggota, penyelesaian hambatan dan komunikasi lintas fungsi. Level karier Monzo tidak dipetakan menjadi skor Preptiva."
    },
    {
      "id": "monzo-technical-2024",
      "title": "Monzo — What are Monzo's technical expectations for Engineering Leaders?",
      "url": "https://monzo.com/blog/what-are-monzos-technical-expectations-for-engineering-leaders",
      "edition": "19 February 2024",
      "locator": "Bagian In practice → Technical outcomes dan Communication",
      "excerpt": "reason through trade-offs, and assess major technical decisions",
      "scope": "Konteks pertimbangan teknis dan penerjemahan masalah teknis bagi mitra lintas fungsi; bukan tuntutan menulis kode pada semua jawaban."
    }
  ],
  "job_analysis": [
    {
      "responsibility": "Memilih prioritas kerja dan keputusan dalam batas sumber daya tim.",
      "competencies": [
        "problem_solving"
      ],
      "source_ids": [
        "gitlab-em",
        "monzo-em-v2"
      ]
    },
    {
      "responsibility": "Mengatur koordinasi, tanggung jawab, delegasi dan penyelesaian hambatan tim.",
      "competencies": [
        "teamwork"
      ],
      "source_ids": [
        "gitlab-em",
        "monzo-em-v2"
      ]
    },
    {
      "responsibility": "Mendukung perkembangan anggota melalui coaching dan umpan balik.",
      "competencies": [
        "leadership"
      ],
      "source_ids": [
        "gitlab-em",
        "monzo-em-v2"
      ]
    },
    {
      "responsibility": "Menyelaraskan informasi dan tindak lanjut bersama pihak lintas fungsi.",
      "competencies": [
        "communication"
      ],
      "source_ids": [
        "gitlab-em",
        "monzo-em-v2",
        "monzo-technical-2024"
      ]
    },
    {
      "responsibility": "Menilai pilihan teknis dan risikonya bersama engineer.",
      "competencies": [
        "technical"
      ],
      "source_ids": [
        "gitlab-em",
        "monzo-technical-2024"
      ]
    }
  ],
  "competencies": {
    "problem_solving": {
      "name": "Pengambilan keputusan",
      "definition": "Menentukan prioritas dan pilihan tindakan untuk tim engineering dengan alasan, batasan, risiko dan pemeriksaan hasil.",
      "levels": {
        "1": {
          "id": "em.problem_solving.l1",
          "behavior": "Secara eksplisit memilih tindakan hanya karena jabatan, kebiasaan atau desakan, sambil mengabaikan risiko atau fakta relevan yang sudah diketahui dalam contoh tersebut.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal untuk menilai keputusan dalam lingkup kerja tim; sumber dipakai untuk relevansi tugas dan metode, bukan menetapkan skor ini."
        },
        "2": {
          "id": "em.problem_solving.l2",
          "behavior": "Memakai satu alasan yang relevan untuk memilih tindakan, tetapi secara eksplisit menutup alternatif yang layak atau mengesampingkan batasan penting tanpa memeriksanya.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal untuk menilai keputusan dalam lingkup kerja tim; sumber dipakai untuk relevansi tugas dan metode, bukan menetapkan skor ini."
        },
        "3": {
          "id": "em.problem_solving.l3",
          "behavior": "Menjelaskan tujuan dan batasan utama, menyebut pilihan yang layak, lalu memberi alasan konkret mengapa satu pilihan digunakan dalam lingkup tanggung jawabnya.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal untuk menilai keputusan dalam lingkup kerja tim; sumber dipakai untuk relevansi tugas dan metode, bukan menetapkan skor ini."
        },
        "4": {
          "id": "em.problem_solving.l4",
          "behavior": "Membandingkan pilihan beserta risiko dan konsekuensi untuk tim atau pengguna, menyebut asumsi yang perlu diperiksa, serta menetapkan cara meninjau keputusan setelah dijalankan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal untuk menilai keputusan dalam lingkup kerja tim; sumber dipakai untuk relevansi tugas dan metode, bukan menetapkan skor ini."
        },
        "5": {
          "id": "em.problem_solving.l5",
          "behavior": "Memenuhi jangkar tingkat 4 dan menjelaskan hasil peninjauan yang benar-benar dilakukan, termasuk bukti hasil serta keputusan mempertahankan atau menyesuaikan pendekatan dengan alasan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal untuk menilai keputusan dalam lingkup kerja tim; sumber dipakai untuk relevansi tugas dan metode, bukan menetapkan skor ini."
        }
      }
    },
    "teamwork": {
      "name": "Kepemimpinan tim",
      "definition": "Membentuk koordinasi, pembagian tanggung jawab dan cara menyelesaikan hambatan agar tim dapat bekerja dengan jelas dan saling menghargai.",
      "levels": {
        "1": {
          "id": "em.teamwork.l1",
          "behavior": "Secara eksplisit menyalahkan atau membungkam anggota saat muncul hambatan, atau memaksakan tanggung jawab yang bertentangan setelah konflik peran diketahui, tanpa tindakan perbaikan dalam contoh itu.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal koordinasi dan kepemimpinan tim; tidak menilai kesamaan gaya pribadi atau banyaknya bawahan."
        },
        "2": {
          "id": "em.teamwork.l2",
          "behavior": "Membagi tugas atau menyelesaikan hambatan secara langsung, tetapi secara eksplisit membiarkan ketergantungan atau batas tanggung jawab yang diketahui tetap tidak jelas.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal koordinasi dan kepemimpinan tim; tidak menilai kesamaan gaya pribadi atau banyaknya bawahan."
        },
        "3": {
          "id": "em.teamwork.l3",
          "behavior": "Menjelaskan tujuan bersama, peran atau pemilik pekerjaan, dan tindakan koordinasi untuk menyelesaikan setidaknya satu hambatan atau perbedaan pendapat yang konkret.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal koordinasi dan kepemimpinan tim; tidak menilai kesamaan gaya pribadi atau banyaknya bawahan."
        },
        "4": {
          "id": "em.teamwork.l4",
          "behavior": "Menyepakati batas keputusan dan cara eskalasi, mengelola ketergantungan atau konflik dengan mendengar pihak terkait, serta memeriksa apakah pembagian kerja dapat dijalankan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal koordinasi dan kepemimpinan tim; tidak menilai kesamaan gaya pribadi atau banyaknya bawahan."
        },
        "5": {
          "id": "em.teamwork.l5",
          "behavior": "Memenuhi jangkar tingkat 4 dan menunjukkan bukti bahwa tim memakai mekanisme tersebut untuk menyelesaikan pekerjaan atau hambatan dengan lebih mandiri; merefleksikan perbaikan yang masih diperlukan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal koordinasi dan kepemimpinan tim; tidak menilai kesamaan gaya pribadi atau banyaknya bawahan."
        }
      }
    },
    "leadership": {
      "name": "Pengembangan orang",
      "definition": "Membantu anggota atau rekan berkembang melalui diagnosis kebutuhan, kesempatan belajar, umpan balik dan tindak lanjut yang dapat diperiksa.",
      "levels": {
        "1": {
          "id": "em.leadership.l1",
          "behavior": "Secara eksplisit merespons kebutuhan pengembangan dengan label pribadi atau ancaman, menolak dukungan yang relevan, atau meniadakan kesempatan belajar tanpa alasan pekerjaan yang dapat diterangkan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal pengembangan orang; pengalaman mentoring rekan, proyek atau organisasi dapat menjadi bukti sesuai lingkup pertanyaan."
        },
        "2": {
          "id": "em.leadership.l2",
          "behavior": "Memberikan saran atau pelatihan umum, tetapi secara eksplisit menerapkan cara yang sama meskipun kebutuhan individu berbeda sudah diketahui, atau menolak menindaklanjuti hambatan belajar yang telah disampaikan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal pengembangan orang; pengalaman mentoring rekan, proyek atau organisasi dapat menjadi bukti sesuai lingkup pertanyaan."
        },
        "3": {
          "id": "em.leadership.l3",
          "behavior": "Mengidentifikasi kebutuhan belajar yang spesifik, menyepakati sasaran yang dapat diamati, dan memberi kegiatan atau umpan balik yang sesuai dengan kebutuhan tersebut.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal pengembangan orang; pengalaman mentoring rekan, proyek atau organisasi dapat menjadi bukti sesuai lingkup pertanyaan."
        },
        "4": {
          "id": "em.leadership.l4",
          "behavior": "Memenuhi jangkar tingkat 3 serta menyepakati dukungan, batas tanggung jawab dan jadwal pemeriksaan; menggunakan umpan balik selama proses untuk menyesuaikan langkah belajar.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal pengembangan orang; pengalaman mentoring rekan, proyek atau organisasi dapat menjadi bukti sesuai lingkup pertanyaan."
        },
        "5": {
          "id": "em.leadership.l5",
          "behavior": "Memenuhi jangkar tingkat 4 dan menyajikan bukti perubahan kemampuan atau kemandirian dari tindak lanjut yang dilakukan; menjelaskan batas kesimpulan serta langkah pengembangan berikutnya.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2"
          ],
          "application": "Jangkar internal pengembangan orang; pengalaman mentoring rekan, proyek atau organisasi dapat menjadi bukti sesuai lingkup pertanyaan."
        }
      }
    },
    "communication": {
      "name": "Komunikasi stakeholder",
      "definition": "Menyampaikan keadaan, pilihan dan keputusan pekerjaan engineering kepada pihak terkait dengan konteks dan tingkat detail yang membantu koordinasi.",
      "levels": {
        "1": {
          "id": "em.communication.l1",
          "behavior": "Secara eksplisit menyembunyikan risiko yang diketahui atau menyampaikan informasi menyesatkan sehingga pihak terkait mengambil keputusan berdasarkan gambaran yang salah dalam contoh tersebut.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal komunikasi pekerjaan; isi dan tindakan komunikasi dinilai dari transkrip, bukan aksen, kelancaran suara atau karakter pribadi."
        },
        "2": {
          "id": "em.communication.l2",
          "behavior": "Menyampaikan status atau kebutuhan, tetapi secara eksplisit mengabaikan kebingungan penerima atau dampak perubahan yang sudah diketahui, tanpa memperjelas pesan dalam contoh tersebut.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal komunikasi pekerjaan; isi dan tindakan komunikasi dinilai dari transkrip, bukan aksen, kelancaran suara atau karakter pribadi."
        },
        "3": {
          "id": "em.communication.l3",
          "behavior": "Menyampaikan konteks, status atau masalah serta tindakan yang dibutuhkan kepada pihak yang tepat, dengan penjelasan yang dapat diikuti dan sesuai keputusan yang sedang dibahas.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal komunikasi pekerjaan; isi dan tindakan komunikasi dinilai dari transkrip, bukan aksen, kelancaran suara atau karakter pribadi."
        },
        "4": {
          "id": "em.communication.l4",
          "behavior": "Menyesuaikan detail bagi penerima, menjelaskan pilihan dan konsekuensi, menyepakati tindak lanjut, serta memeriksa bahwa pihak terkait memahami keputusan yang sama.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal komunikasi pekerjaan; isi dan tindakan komunikasi dinilai dari transkrip, bukan aksen, kelancaran suara atau karakter pribadi."
        },
        "5": {
          "id": "em.communication.l5",
          "behavior": "Memenuhi jangkar tingkat 4 dan menunjukkan bagaimana umpan balik penerima atau perubahan situasi dipakai untuk memperbaiki komunikasi; memberi bukti dampaknya terhadap penyelarasan tindakan atau keputusan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-em-v2",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal komunikasi pekerjaan; isi dan tindakan komunikasi dinilai dari transkrip, bukan aksen, kelancaran suara atau karakter pribadi."
        }
      }
    },
    "technical": {
      "name": "Penilaian teknis",
      "definition": "Meninjau pilihan teknis bersama engineer dengan mempertimbangkan kebutuhan, batasan, risiko dan bukti pengujian dalam tanggung jawab manajer.",
      "levels": {
        "1": {
          "id": "em.technical.l1",
          "behavior": "Secara eksplisit mengabaikan batasan atau kegagalan teknis yang sudah terbukti, atau memerintahkan perubahan berisiko tanpa perlindungan yang diketahui diperlukan dalam contoh tersebut.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal peninjauan teknis manajerial; sintaks atau hafalan teknologi bukan indikator wajib dan kebutuhan organisasi tetap harus diperiksa."
        },
        "2": {
          "id": "em.technical.l2",
          "behavior": "Menggunakan alasan teknis yang relevan, tetapi secara eksplisit menganggap satu solusi cocok untuk semua kondisi atau menolak memeriksa asumsi kritis yang telah dipersoalkan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal peninjauan teknis manajerial; sintaks atau hafalan teknologi bukan indikator wajib dan kebutuhan organisasi tetap harus diperiksa."
        },
        "3": {
          "id": "em.technical.l3",
          "behavior": "Menjelaskan kebutuhan dan batasan sistem, meninjau pilihan bersama pihak teknis, serta memberi alasan teknis yang konsisten untuk memilih pendekatan atau meminta pemeriksaan tambahan.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal peninjauan teknis manajerial; sintaks atau hafalan teknologi bukan indikator wajib dan kebutuhan organisasi tetap harus diperiksa."
        },
        "4": {
          "id": "em.technical.l4",
          "behavior": "Membandingkan konsekuensi pilihan terhadap kualitas, operasional atau pengguna, mengakui batas pengetahuan, dan menetapkan pengujian atau mitigasi yang sesuai dengan risiko.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal peninjauan teknis manajerial; sintaks atau hafalan teknologi bukan indikator wajib dan kebutuhan organisasi tetap harus diperiksa."
        },
        "5": {
          "id": "em.technical.l5",
          "behavior": "Memenuhi jangkar tingkat 4 dan meninjau bukti pengujian atau operasi yang benar-benar tersedia; menjelaskan bagaimana bukti itu mengubah atau menguatkan keputusan serta batas penerapannya.",
          "origin": "internal",
          "source_ids": [
            "opm-rating",
            "siop-principles-2018",
            "gitlab-em",
            "monzo-technical-2024"
          ],
          "application": "Jangkar internal peninjauan teknis manajerial; sintaks atau hafalan teknologi bukan indikator wajib dan kebutuhan organisasi tetap harus diperiksa."
        }
      }
    }
  }
}
<!-- em-rubric:end -->

## Pekerjaan manusia yang masih diperlukan

1. Ahli Engineering Manager/Head of Engineering meninjau analisis tugas terhadap JD target, cakupan kompetensi, bobot, dan 25 jangkar; catat peran peninjau, tanggal, alasan keputusan serta perubahan.
2. Perbaiki pertanyaan yang tidak memberi kesempatan menampilkan indikator; pisahkan kecukupan bukti dari kemampuan.
3. Tiga asesor yang memenuhi syarat menilai secara independen tanpa skor AI, dengan kutipan dan indikator. Paket kosong atau jawaban sintetis tanpa skor bukan gold set.
4. Tetapkan konsensus setelah skor independen disimpan, lalu gunakan himpunan uji terpisah untuk pembandingan AI, stabilitas, bahasa campuran dan sensitivitas kesalahan transkripsi.
5. Catat hasil dan batas penggunaan. Tinjauan dokumen atau kelulusan tes perangkat lunak tidak mengubah `validated` menjadi true.

## Batas benchmark Mohler

[Benchmark Mohler](mohler-benchmark.md) terpisah dari profil ini. Rating jawaban akademik tidak menjadi bukti penilaian kepemimpinan atau keputusan manajerial, dan prompt benchmark berbeda dari evaluator EM. Unduhan dataset serta pilot tidak mengubah blok rubrik runtime, hash, versi `2026-11-07.em.1`, bobot maupun status `validated: false`. Penilaian manusia atas kasus EM tetap belum tersedia.
