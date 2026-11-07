'use strict';
(() => {
  const dictionary = {
    'Bahasa perlu disesuaikan':'Please use the interview language',
    'Skor belum tersedia':'No overall score available',
    'Jawaban Anda tetap tersimpan dan dapat dibaca di bawah. Belum ada kompetensi berbobot dengan bukti yang cukup dan terverifikasi untuk menghitung skor keseluruhan. Ini bukan nilai nol. Lihat alasan penilaian pada setiap jawaban untuk mengetahui bukti yang masih diperlukan.':'Your answers are saved and shown below. No weighted competency has enough verified evidence to calculate an overall score yet. This is not a score of zero. Check the assessment reasons under each answer to see what evidence is still needed.',
    'Bagian hasil':'Result sections',
    'Siapkan cara menjawab dan pastikan Anda nyaman sebelum masuk.':'Choose how to answer and get comfortable before joining.',
    'Rekam suara':'Record audio', 'Dengan kamera dan mikrofon':'With camera and microphone',
    'Ketik jawaban':'Type your answers', 'Tanpa kamera atau mikrofon':'No camera or microphone needed',
    'Aktifkan perangkat untuk melihat pratinjau.':'Enable your devices to see your preview.', 'Pemeriksaan perangkat':'Device checks',
    'Saya siap mengikuti sesi':'I’m ready for the interview',
    'Pindah tab atau koneksi putus menjeda pertanyaan. Lanjutkan dengan Retry atau Next.':'Switching tabs or losing connection pauses the question. Continue with Retry or Next.',
    'Opsional':'Optional', 'Siap untuk mulai':'Ready to begin', 'Lengkapi pemeriksaan di atas':'Complete the checks above', 'Terdeteksi':'Detected',
    'Takarir diaktifkan':'Captions on', 'Takarir dinonaktifkan':'Captions off',
    'Kamera diaktifkan':'Camera on', 'Kamera dinonaktifkan':'Camera off',
    'Mikrofon diaktifkan':'Microphone on', 'Mikrofon dinonaktifkan':'Microphone off',
    'Cermin kamera diaktifkan':'Camera mirroring on', 'Cermin kamera dinonaktifkan':'Camera mirroring off',
    'Gerakan pewawancara diaktifkan':'Interviewer motion on', 'Gerakan pewawancara dijeda':'Interviewer motion paused',
    'Coba siapkan ulang':'Retry preparation', 'PERSIAPAN TERTUNDA':'PREPARATION PENDING',
    'Persiapan tertunda':'Preparation pending', 'Persiapan belum selesai. Coba siapkan ulang.':'Preparation is incomplete. Try again.',
    'Cara menjawab':'Answer mode', 'Rekam suara · gunakan kamera dan mikrofon':'Record audio · use camera and microphone',
    'Teks · tanpa kamera/mikrofon':'Text · without camera/microphone', 'Gunakan mikrofon':'Use microphone',
    'Mulai rekam suara':'Start recording', 'Mode jawaban: Teks':'Answer mode: Text', 'Mode jawaban: Rekam suara':'Answer mode: Audio',
    'MENGAKTIFKAN MIKROFON':'ENABLING MICROPHONE', 'GILIRAN ANDA · MODE TEKS':'YOUR TURN · TEXT MODE',
    'Aktifkan mikrofon, lalu tekan Mulai rekam suara. Draf teks tetap tersimpan selama pertanyaan ini.':'Enable your microphone, then press Start recording. Your text draft is kept during this question.',
    'Bahasa website':'Website language', 'Bahasa Indonesia':'Indonesian', 'Bahasa Inggris':'English',
    'Simulasi baru':'New simulation', 'Simulasi Baru':'New simulation', 'Riwayat':'History', 'Riwayat latihan':'Practice history',
    'Navigasi utama':'Main navigation', 'Navigasi footer':'Footer navigation', 'Lewati navigasi':'Skip navigation', 'Keluar':'Sign out',
    'Ruang latihan wawancara Anda.':'Your interview practice workspace.', 'Skor latihan, bukan prediksi hasil seleksi.':'Practice scores do not predict hiring outcomes.',
    'Persiapkan langkah berikutnya':'Prepare for your next interview', 'Hasil wawancara':'Interview results', 'Masuk':'Sign in', 'Buat akun':'Create account',
    'Persiapan yang baik dimulai dari sini.':'Good preparation starts here.',
    'Latih jawaban, kenali kekuatan, dan siapkan langkah berikutnya.':'Practice your answers, know your strengths, and prepare for what comes next.',
    'Langkah berikutnya':'Your next step', 'Pilih yang ingin Anda siapkan hari ini.':'Choose what to work on today.',
    'Lebih siap saat giliran Anda.':'Feel ready when it is your turn.',
    'Berlatih dengan pewawancara pilihan, sesuai posisi yang Anda tuju.':'Practice with your chosen interviewer for the role you want.',
    'Mulai simulasi':'Start a simulation', 'Profil & CV':'Profile & CV',
    'Pengalaman Anda, titik awalnya.':'Your experience is the starting point.',
    'Simpan CV dan detail diri agar persiapan latihan berikutnya lebih mudah.':'Save your CV and details to make your next practice session easier to set up.',
    'Lengkapi profil':'Complete your profile', 'Umpan balik':'Feedback',
    'Temukan yang bisa ditingkatkan.':'Find room to improve.',
    'Buka kembali hasil latihan dan pelajari masukan dari pewawancara.':'Revisit your practice results and learn from your interviewer’s feedback.',
    'Tinjau hasil latihan':'Review practice results', 'Ringkasan latihan':'Practice overview',
    'Setiap sesi, satu langkah lebih siap.':'A little more prepared with every session.', 'Dari latihan Anda':'From your practice',
    'Sejauh ini, latihan Anda.':'Your practice at a glance.', 'Sesi selesai':'Completed sessions', 'Seluruh latihan Anda':'All your completed interviews',
    'Rata-rata skor':'Average score', 'Dari sesi yang dinilai':'From assessed sessions', 'Skor terbaik':'Best score', 'Pencapaian tertinggi':'Your highest score',
    'Perubahan skor':'Score change', 'poin':'points', 'Skor terakhir vs pertama':'Latest score vs. first', 'Perlu 2 sesi yang dinilai':'Requires two assessed sessions',
    'Perkembangan skor':'Score progress', 'Sesi selesai terakhir':'Recent completed sessions', 'Skor total':'Overall score',
    'Bobot penilaian mengikuti pewawancara.':'Assessment weights depend on the interviewer.', 'Fokus latihan':'Practice focus', 'Dari sesi terakhir yang dinilai':'From your latest assessed session',
    'Sesi terakhir':'Recent sessions', 'Lihat semua':'View all', 'Buka hasil':'View results', 'Memuat latihan Anda…':'Loading your sessions…',
    'Latihan belum bisa dimuat.':'Unable to load your sessions.', 'Coba lagi':'Try again', 'Aktifkan JavaScript untuk melihat sesi dan hasil latihan.':'Enable JavaScript to view your sessions and results.',
    'Belum ada latihan':'No sessions yet', 'Mulai sesi pertama Anda.':'Start your first practice session.', 'Mulai latihan':'Start practicing',
    'Belum ada skor':'No scores yet', 'Selesaikan latihan untuk melihat perkembangannya.':'Complete a session to track your progress.',
    'Skor akan tampil setelah latihan dinilai.':'Scores will appear after a session is assessed.', 'Belum ada sesi dinilai':'No assessed sessions yet', '1 sesi dinilai':'1 assessed session',
    'Memuat fokus latihan…':'Loading practice focus…', 'Fokus belum tersedia.':'Practice focus is not available yet.',
    'Belum ada kompetensi terukur':'No measured competencies yet', 'Lihat hasil untuk rincian sesi ini.':'View the results for session details.',
    'Mulai dari skor terendah berikut.':'Start with these lower-scoring areas.', 'Fokus belum dapat dimuat.':'Unable to load practice focus.',
    'Data latihan belum dapat dimuat.':'Unable to load practice data.', 'Data latihan belum dapat dimuat. Coba lagi.':'Unable to load practice data. Try again.',
    'Semua sesi, jawaban, dan hasil Anda.':'All your sessions, answers, and results.', 'Daftar latihan':'Practice sessions', 'Status sesi':'Session status',
    'Semua':'All', 'Selesai':'Completed', 'Aktif':'Active', 'Ditutup':'Closed', 'Ditutup / gagal':'Closed / failed',
    'Menyiapkan':'Preparing', 'Siap dimulai':'Ready to start', 'Berlangsung':'In progress', 'Menilai':'Assessing', 'Penilaian tertunda':'Assessment pending',
    'Status tidak dikenal':'Unknown status', 'Cari sesi':'Search sessions', 'Posisi, perusahaan, atau pewawancara':'Role, company, or interviewer',
    'Pewawancara':'Interviewer', 'Semua pewawancara':'All interviewers', 'Urutkan':'Sort by', 'Terbaru':'Newest first', 'Terlama':'Oldest first', 'Skor tertinggi':'Highest score',
    'Reset filter':'Reset filters', 'Halaman riwayat':'History pages', 'Halaman sebelumnya':'Previous page', 'Halaman berikutnya':'Next page', 'Sebelumnya':'Previous', 'Berikutnya':'Next',
    'Posisi':'Role', 'Tanggal':'Date', 'Status':'Status', 'Skor':'Score', 'Tidak ada sesi yang cocok':'No matching sessions', 'Coba ubah pencarian atau filter.':'Try another search or filter.',
    'Siapkan Ruang Wawancara':'Set up your interview', 'Cek kamera dan mikrofon, lalu lengkapi':'Check your camera and microphone, then complete',
    'detail wawancara di sebelah kanan.':'your interview details on the right.', 'Kamera belum aktif':'Camera is off', 'Pratinjau lokal':'Local preview',
    'Perangkat pratinjau':'Preview devices', 'Aktifkan kamera':'Turn on camera', 'Matikan kamera':'Turn off camera', 'Aktifkan mikrofon':'Turn on microphone', 'Matikan mikrofon':'Turn off microphone',
    'Mirror kamera':'Mirror camera', 'Buka fullscreen':'Enter fullscreen', 'Keluar fullscreen':'Exit fullscreen', 'Kamera dan mikrofon nonaktif':'Camera and microphone are off',
    'Level mikrofon':'Microphone level', 'Pratinjau ini tidak direkam':'This preview is not recorded', 'Pilih pewawancara':'Choose your interviewer',
    'Wawancara belum tersedia. Hubungi pengelola untuk mengaktifkan layanan AI.':'Interviews are unavailable. Contact the administrator to enable the AI services.',
    'Format wawancara':'Interview format', 'Satu pewawancara':'One interviewer', 'Panel · 2–3 pewawancara':'Panel · 2–3 interviewers',
    'Wajib diisi':'Required', 'Unggah PDF atau gunakan CV terakhir yang tersimpan.':'Upload a PDF or use your last saved CV.',
    'Persona pewawancara':'Interviewer persona', 'Anggota panel':'Panel members', 'Pilih 2–3 pewawancara. Jumlah pertanyaan adalah total untuk seluruh panel.':'Select 2–3 interviewers. The question count covers the whole panel.',
    'Rina · HR. Menggali motivasi, kolaborasi, dan potensi belajar Anda.':'Rina · HR. Explores your motivation, collaboration, and learning potential.',
    'Andi · Calon atasan langsung. Menggali praktik teknis/fungsional, pemecahan masalah, dan cara belajar sesuai posisi.':'Andi · Your potential direct manager. Explores practical skills, problem-solving, and how you learn in the role.',
    'Pak Hendra · Manager. Menggali kepemimpinan, pengambilan keputusan, dan dampak bisnis.':'Pak Hendra · Manager. Explores leadership, decision-making, and business impact.',
    'Bahasa wawancara':'Interview language', '/ Interview language':'', 'Pewawancara mengikuti bahasa sesi. Jawaban campuran Indonesia–English tetap diterima.':'Interviewers use the session language. Mixed Indonesian–English answers are welcome.',
    'Jumlah pertanyaan':'Number of questions', 'Pemanasan':'Warm-up', 'Singkat':'Short', 'Standar':'Standard',
    'Detail kandidat & posisi':'Candidate & role details', 'Lengkapi CV dan konteks latihan Anda.':'Add your CV and practice context.', 'Nama kandidat':'Candidate name', 'Usia':'Age',
    'Laki-laki':'Male', 'Perempuan':'Female', 'Latar pengalaman':'Experience', 'Sesuaikan dari CV':'Use my CV', 'Mahasiswa / pelajar':'Student', 'Fresh graduate':'Recent graduate',
    'Sudah bekerja':'Working professional', 'Beralih karier':'Career switcher', 'CV dalam PDF':'CV as PDF', 'PDF berteks, maksimal 5 MB dan 30 halaman.':'Text-based PDF, up to 5 MB and 30 pages.',
    'Gunakan CV terakhir yang tersimpan':'Use my saved CV', 'Belum ada CV yang tersimpan di akun ini.':'No CV has been saved to this account yet.',
    'Posisi pekerjaan':'Job role', 'Contoh: Product Designer':'e.g. Product Designer', 'Level':'Level', 'Industri':'Industry', 'Contoh: Teknologi':'e.g. Technology',
    'Perusahaan':'Company', '(opsional)':'(optional)', 'Nama perusahaan':'Company name', 'Deskripsi pekerjaan':'Job description',
    'Tempel tanggung jawab dan kualifikasi posisi yang ingin Anda latih.':'Paste the responsibilities and requirements for your target role.',
    'Minimal 5 kata.':'At least 5 words.', 'Deskripsi pekerjaan minimal 5 kata.':'Your job description must contain at least 5 words.',
    'JD minimal 5 kata setelah dibersihkan.':'Your job description must contain at least 5 words after cleanup.',
    'Rubrik khusus Engineering Manager (draf)':'Engineering Manager rubric (draft)',
    'Draf untuk satu pewawancara Manager. Indikator dan bobot belum ditinjau ahli atau divalidasi.':'Draft for a single Manager interview. Indicators and weights have not been reviewed by experts or validated.',
    'Saya setuju CV dan audio jawaban diproses provider AI untuk latihan. Transkrip tetap tersimpan.':'I agree to AI providers processing my CV and answer audio for practice. Transcripts are saved.',
    'Batal':'Cancel', 'Siapkan wawancara':'Prepare interview', 'Menyiapkan sesi…':'Preparing your session…', 'Mengaktifkan kamera…':'Turning on camera…', 'Mengaktifkan mikrofon…':'Turning on microphone…',
    'Pilih minimal dua pewawancara untuk panel.':'Select at least two interviewers for a panel.', 'PDF maksimal 5 MB.':'The PDF must be no larger than 5 MB.',
    'Pilih file PDF CV terlebih dahulu.':'Choose a PDF CV file first.',
    'Preview Anda':'Your preview', 'Fullscreen tidak tersedia. Pratinjau tetap dapat digunakan.':'Fullscreen is unavailable. You can still use the preview.',
    'Izin perangkat belum diberikan. Izinkan kamera atau mikrofon melalui pengaturan browser, lalu coba lagi.':'Device permission was not granted. Allow camera or microphone access in browser settings, then try again.',
    'Perangkat tidak ditemukan. Hubungkan kamera atau mikrofon, lalu coba lagi.':'No device was found. Connect a camera or microphone, then try again.',
    'Perangkat belum bisa diaktifkan. Pastikan tidak sedang dipakai aplikasi lain, lalu coba lagi.':'Unable to activate the device. Check that another app is not using it, then try again.',
    'Selamat datang kembali.':'Welcome back.', 'Masuk untuk melanjutkan latihan Anda.':'Sign in to continue your practice.', 'Buat akun Preptiva.':'Create your Preptiva account.',
    'Persiapan wawancara dimulai di sini.':'Your interview preparation starts here.', 'Nama lengkap':'Full name', 'Nama Anda':'Your name', 'nama@email.com':'you@example.com',
    'Konfirmasi password':'Confirm password', 'Minimal 8 karakter, dengan huruf dan angka.':'At least 8 characters, including a letter and a number.', 'tahun':'years',
    'Saya menyetujui pemrosesan data untuk latihan wawancara.':'I agree to my data being processed for interview practice.',
    'Belum punya akun?':'New to Preptiva?', 'Sudah punya akun?':'Already have an account?', 'Memproses…':'Processing…',
    'Tampilkan password':'Show password', 'Sembunyikan password':'Hide password', 'Tampilkan konfirmasi password':'Show password confirmation', 'Sembunyikan konfirmasi password':'Hide password confirmation',
    'Gunakan huruf dan angka pada password.':'Include letters and numbers in your password.', 'Konfirmasi password belum sama.':'The passwords do not match.',
    'Latih jawaban.':'Practice your answers.', 'Hadapi wawancara.':'Face your interview.', 'Satu pewawancara atau panel. Sesuai kebutuhan Anda.':'One interviewer or a panel. Your choice.',
    'Latihan wawancara bersama Preptiva':'Interview practice with Preptiva', 'Email atau password salah.':'Incorrect email or password.', 'Email sudah terdaftar.':'This email is already registered.',
    'Koneksi terputus. Coba lagi.':'Connection lost. Try again.', 'Permintaan gagal.':'Request failed.', 'Hasil wawancara belum tersedia.':'Interview results are not available yet.',
    'Latihan lagi':'Practice again', 'Menyiapkan hasil latihan Anda.':'Preparing your practice results.', 'Menyiapkan hasil':'Preparing results',
    'Penilaian dan umpan balik akan tampil di sini.':'Your assessment and feedback will appear here.', 'Ringkasan hasil':'Results overview',
    'Skor keseluruhan':'Overall score', 'Skor belum terukur':'Score not yet measured', 'Penilaian untuk latihan wawancara.':'An assessment for interview practice.',
    'Ringkasan wawancara':'Interview summary', 'Ringkasan belum tersedia untuk sesi ini.':'No summary is available for this session.',
    'Belum ada pembanding':'No comparable session yet', 'Dari sesi sebanding sebelumnya':'Compared with a previous matching session',
    'Cakupan bukti':'Evidence coverage', 'Tidak tersedia pada sesi ini':'Not available for this session', 'Jawaban':'Answers', 'ditinjau':'reviewed', 'Tersimpan dalam sesi ini':'Saved in this session',
    'Hasil per interviewer':'Results by interviewer', 'Kompetensi':'Competencies', 'Skor berdasarkan bukti jawaban.':'Scores based on answer evidence.',
    'Bukti cukup':'Sufficient evidence', 'Bukti terbatas':'Limited evidence', 'Belum dinilai':'Not assessed', 'Transkrip tidak dapat digunakan':'Unusable transcript', 'Belum terukur':'Not yet measured',
    'Lihat bukti':'View evidence', 'Belum ada kompetensi yang dinilai.':'No competencies have been assessed yet.',
    'Kompetensi dengan bukti terbatas tidak dimasukkan ke skor total.':'Competencies with limited evidence are excluded from the overall score.',
    'Skor sesi ini mengikuti kebijakan penilaian versi sebelumnya.':'This session retains its original scoring policy.',
    'Yang sudah kuat':'Your strengths', 'Fokus perbaikan':'Areas to improve', 'Belum ada kekuatan yang dirangkum.':'No strengths have been summarized yet.',
    'Belum ada perbaikan yang dirangkum.':'No improvements have been summarized yet.', 'Struktur jawaban STAR':'STAR answer structure',
    'Situasi':'Situation', 'Tugas':'Task', 'Tindakan':'Action', 'Hasil':'Result', 'Terlihat':'Present', 'Belum terlihat':'Not yet present',
    'Bagian yang muncul pada jawaban sesi ini.':'Elements present in this session’s answers.', 'Latihan berikutnya':'What to practice next', 'Rekomendasi dari sesi ini.':'Recommendations from this session.',
    'Alasan rekomendasi':'Why this recommendation', 'Tinjau jawaban':'Review your answers', 'Pertanyaan, transkrip, dan umpan balik.':'Questions, transcripts, and feedback.',
    'Pertanyaan lanjutan':'Follow-up question', 'Dilewati':'Skipped', 'Jawaban teks':'Text answer', 'Jawaban suara':'Voice answer', 'Jawaban Anda':'Your answer',
    'Pertanyaan dilewati. Tidak ada jawaban yang dinilai.':'Question skipped. No answer was assessed.', 'Transkrip tidak tersedia.':'No transcript available.',
    'Yang sudah baik':'What worked well', 'Saran perbaikan':'Suggested improvements', 'Untuk jawaban berikutnya':'For your next answer', 'Rincian bukti penilaian':'Assessment evidence details',
    'Informasi penilaian':'About this assessment', 'Ringkasan latihan Anda.':'Your practice overview.', 'Belum divalidasi untuk seleksi kerja.':'Not validated for hiring decisions.',
    'Skor digunakan untuk refleksi latihan.':'Scores are intended for practice and reflection.', 'Penilaian belum selesai':'Assessment incomplete',
    'Jawaban Anda tersimpan. Coba penilaian kembali.':'Your answers are saved. Try the assessment again.', 'Nilai ulang':'Retry assessment',
    'Latihan belum selesai':'Interview incomplete', 'Selesaikan percakapan untuk melihat refleksi Anda.':'Complete the interview to view your feedback.', 'Buka ruang wawancara':'Open interview room',
    'Sesi gagal. Silakan buat latihan baru.':'The session failed. Please start a new one.', 'Komunikasi':'Communication', 'Pemecahan masalah':'Problem solving',
    'Teknis':'Technical skills', 'Berpikir analitis':'Analytical thinking', 'Analisis':'Analysis', 'Kerja sama':'Teamwork', 'Adaptasi':'Adaptability', 'Kepemimpinan':'Leadership',
    'Keputusan':'Decision making', 'Kepemimpinan tim':'Team leadership', 'Pengembangan orang':'People development', 'Komunikasi stakeholder':'Stakeholder communication', 'Penilaian teknis':'Technical judgment',
    'Indikator yang didukung bukti':'Evidence-backed indicators', 'Belum ada indikator dengan bukti yang terverifikasi.':'No indicators have verified supporting evidence yet.',
    'Alasan belum mencapai tingkat berikutnya':'Why the next level has not been reached', 'Bukti yang masih perlu dilengkapi':'Evidence still needed',
    'Asal indikator dan rujukan':'Indicator origins and references', 'Disusun internal':'Internally developed', 'Diadaptasi':'Adapted', 'Diambil dari sumber':'Taken from source',
    'Status rubrik khusus':'Custom rubric status', 'Rubrik khusus pekerjaan':'Job-specific rubric', 'Draf':'Draft',
    'Indikator dan bobot belum ditinjau ahli pekerjaan.':'Indicators and weights have not been reviewed by role experts.',
    'Rubrik ini belum divalidasi. Skor dan indikator digunakan untuk refleksi latihan.':'This rubric is not validated. Scores and indicators are for practice and reflection.',
    'Indikator dan bobot belum ditinjau ahli pekerjaan. Rubrik ini belum divalidasi. Skor dan indikator digunakan untuk refleksi latihan.':'Indicators and weights have not been reviewed by role experts. This rubric is not validated and is intended for practice and reflection.',
    'Rujukan menjelaskan landasan metodologi atau pekerjaan. Indikator berlabel internal merupakan rancangan Preptiva, bukan skala skor yang ditetapkan sumber.':'References explain the methodology or role context. Internal indicators are developed by Preptiva; they are not scoring scales prescribed by the sources.',
    'Menyiapkan sesi':'Preparing session', 'Partner latihan Anda':'Your practice partner', 'Pewawancara AI':'AI interviewer', 'Karakter pewawancara AI':'AI interviewer character',
    'Kamera Anda':'Your camera', 'Anda':'You', 'Wawancara dimulai dalam':'Your interview starts in', 'Waktu jawab':'Answer time', 'Mulai jawab':'Start answering',
    'Kirim jawaban':'Send answer', 'Rekam ulang':'Record again', 'Putar pertanyaan':'Replay question', 'Jawab dengan teks':'Answer with text', 'Jawab dengan suara':'Answer with voice',
    'Hentikan suara':'Stop audio', 'Tulis jawaban Anda…':'Type your answer…', 'Kirim jawaban teks':'Send text answer', 'Tinjau transkrip':'Review transcript',
    'Koreksi bila perlu, lalu kirim jawaban.':'Make any corrections, then send your answer.', 'Pertanyaan dijeda':'Question paused', 'Menyimpan status…':'Saving status…',
    'Retry mengulang dengan waktu penuh. Next melewati pertanyaan tanpa skor.':'Retry restarts the full timer. Next skips the question without scoring.', 'Coba kirim ulang':'Retry sending',
    'Lanjutkan percakapan':'Continue interview', 'Pertanyaan wawancara':'Interview question', 'Percakapan':'Conversation', 'Ruang latihan Anda':'Your practice room',
    'Percakapan wawancara':'Interview conversation', 'Belum ada percakapan':'No conversation yet', 'Pertanyaan dan transkrip muncul setelah sesi dimulai.':'Questions and transcripts appear when the session starts.',
    'Memproses jawaban…':'Processing your answer…', 'Memproses transkrip…':'Processing transcript…', 'Memproses ulang…':'Processing again…',
    'Tampilkan percakapan':'Show conversation', 'Sembunyikan percakapan':'Hide conversation', 'Tampilkan takarir':'Show captions', 'Sembunyikan takarir':'Hide captions',
    'Mikrofon':'Microphone', 'Kamera':'Camera', 'Tampilan':'View', 'Subtitle':'Captions', 'Animasi karakter':'Character animation', 'Cerminkan kamera':'Mirror camera', 'Nonaktifkan cermin kamera':'Turn off camera mirroring',
    'Aktifkan gerakan pewawancara':'Enable interviewer animation', 'Jeda gerakan pewawancara':'Pause interviewer animation',
    'Cek perangkat':'Check your devices', 'Mode teks · tanpa kamera/mikrofon':'Text mode · no camera or microphone', 'Aktifkan perangkat':'Enable devices', 'Periksa ulang':'Check again',
    'Kamera terlihat jelas':'My camera preview is clear', 'Perangkat':'Device', 'PC / laptop terdeteksi':'PC / laptop detected', 'Ucapkan beberapa kata':'Say a few words',
    'Speaker':'Speaker', 'Tes suara':'Test audio', 'Suara terdengar jelas':'I can hear the audio clearly', 'Koneksi':'Connection', 'Terhubung':'Connected',
    'Pengaturan suara':'Audio settings', 'Transkrip realtime':'Live transcription', 'Kirim otomatis setelah jeda':'Send automatically after a pause',
    'Pengiriman otomatis melewati tinjauan transkrip.':'Automatic sending skips transcript review.', 'Sela suara interviewer':'Interrupt the interviewer’s audio',
    'Gunakan headphone agar suara speaker tidak memulai jawaban.':'Use headphones to prevent speaker audio from starting an answer.',
    'Saya memahami: pindah tab atau koneksi putus menjeda pertanyaan. Pilih Retry atau Next untuk melanjutkan.':'I understand: switching tabs or losing connection pauses the question. Choose Retry or Next to continue.',
    'Gunakan fullscreen':'Use fullscreen', 'Video tetap lokal. Audio dikirim saat Anda mengirim jawaban.':'Video stays local. Audio is sent when you submit your answer.',
    'Lengkapi pemeriksaan untuk mulai.':'Complete the checks to start.', 'Mulai wawancara':'Start interview', 'Keluar dari wawancara?':'Leave the interview?',
    'Sesi akan ditutup dan tidak dapat dilanjutkan.':'The session will close and cannot be resumed.', 'Tetap di sini':'Stay here', 'Keluar sesi':'Leave session',
    'Tutup':'Close', 'Pratinjau kamera Anda':'Your camera preview', 'RUANG ANDA SUDAH SIAP':'YOUR INTERVIEW ROOM IS READY', 'SIAP DIMULAI':'READY TO START',
    'MENYIAPKAN RUANG':'PREPARING YOUR ROOM', 'BERSIAP':'GET READY', 'GILIRAN ANDA':'YOUR TURN', 'MENDENGARKAN':'LISTENING', 'MENDENGARKAN ANDA':'LISTENING TO YOU',
    'MEREKAM':'RECORDING', 'MEMPROSES':'PROCESSING', 'MENILAI':'ASSESSING', 'SESI DITUTUP':'SESSION CLOSED', 'PERTANYAAN DIJEDA':'QUESTION PAUSED',
    'TINJAU JAWABAN':'REVIEW YOUR ANSWER', 'TINJAU TRANSKRIP':'REVIEW TRANSCRIPT', 'PENGGALIAN LANJUTAN':'FOLLOW-UP', 'PERTANYAAN':'QUESTION',
    'PERTANYAAN BERIKUTNYA SIAP':'NEXT QUESTION READY', 'PERLU DIKIRIM ULANG':'PLEASE SEND AGAIN', 'PERLU DILANJUTKAN':'CONTINUATION NEEDED',
    'MENGHUBUNGKAN MIKROFON':'CONNECTING MICROPHONE', 'MENUNTASKAN TRANSKRIP':'FINALIZING TRANSCRIPT', 'JEDA BICARA · AKAN DIKIRIM':'SPEECH PAUSED · SENDING SOON',
    'JEDA TERDETEKSI · SILAKAN LANJUT':'PAUSE DETECTED · KEEP GOING', 'GUNAKAN REKAMAN BIASA / TEKS':'USE STANDARD RECORDING / TEXT',
    'KONEKSI TERPUTUS':'CONNECTION LOST', 'WAJIB PC / LAPTOP':'PC / LAPTOP REQUIRED', 'Wajib PC / laptop':'PC / laptop required',
    'Gunakan PC atau laptop':'Use a PC or laptop', 'HP / tablet tidak didukung':'Phones / tablets are not supported', 'HP dan tablet tidak didukung untuk wawancara.':'Phones and tablets cannot be used for interviews.',
    'Buka sesi ini melalui PC atau laptop.':'Open this session on a PC or laptop.', 'Mikrofon aktif':'Microphone on', 'Mikrofon nonaktif':'Microphone off',
    'Belum terkirim':'Not sent', 'Terkirim':'Sent', 'Terhenti':'Interrupted', 'Transkrip sementara':'Live transcript', 'Selesai bicara':'Finish speaking', 'Selesai merekam':'Recording finished',
    'Lanjutkan sesi':'Continue session', 'Tes lagi':'Test again', 'Menunggu izin…':'Waiting for permission…', 'Mengaktifkan perangkat…':'Enabling devices…',
    'Kembali ke halaman ini untuk memulai sesi.':'Return to this page to start the session.', 'Periksa kamera, mikrofon, dan suara sebelum memulai percakapan.':'Check your camera, microphone, and speaker before starting.',
    'Belum terkonfirmasi':'Not confirmed', 'Koneksi aplikasi belum tersedia.':'Unable to connect to the application.', 'Hubungkan kembali internet untuk melanjutkan.':'Reconnect to the internet to continue.',
    'Koneksi terputus. Pertanyaan dijeda.':'Connection lost. The question is paused.', 'Perangkat terputus. Pertanyaan dijeda.':'Device disconnected. The question is paused.',
    'Perangkat terputus. Hubungkan kembali lalu ulangi pemeriksaan.':'Device disconnected. Reconnect it and run the checks again.',
    'Permintaan belum berhasil. Coba lagi.':'The request failed. Try again.', 'Jawaban belum dapat dikirim. Coba kirim ulang.':'Unable to send your answer. Try sending it again.',
    'Audio belum terekam. Coba mulai jawab lagi.':'No audio was recorded. Try starting your answer again.', 'Perekaman terhenti. Tinjau audio sebelum mengirim.':'Recording stopped. Review the audio before sending.',
    'Audio realtime belum tersedia.':'Live audio is not available yet.', 'Audio realtime tidak didukung di browser ini. Rekaman biasa dan teks tetap tersedia.':'This browser does not support live audio. Standard recording and text are still available.',
    'Suara belum tersedia. Percakapan tetap dapat dibaca di chat.':'Audio is unavailable. You can still read the conversation in chat.',
    'Audio belum dapat diputar. Coba putar ulang pertanyaan.':'Unable to play audio. Try replaying the question.', 'Audio belum dapat diputar. Pilih Lanjutkan audio untuk mencoba lagi.':'Unable to play audio. Select Continue audio to try again.',
    'Browser menjeda audio. Pilih Lanjutkan audio untuk memutarnya.':'The browser paused the audio. Select Continue audio to play it.',
    'Lanjutkan audio':'Continue audio', 'Pilih Retry untuk mengulang atau Next untuk melewati.':'Choose Retry to restart or Next to skip.',
    'Pertanyaan dilewati.':'Question skipped.', 'Pemrosesan gagal. Kirim ulang jawaban yang sama.':'Processing failed. Resend the same answer.',
    'Pertanyaan berikutnya belum tersedia. Coba lanjutkan lagi.':'The next question is not available yet. Try continuing again.',
    'Menyimpan jeda. Hubungkan kembali internet bila terputus.':'Saving the pause. Reconnect to the internet if needed.',
    'Perangkat belum dapat diaktifkan. Pastikan tidak sedang dipakai aplikasi lain, lalu coba lagi.':'Unable to enable devices. Check that another app is not using them, then try again.',
    'Kamera atau mikrofon tidak ditemukan. Hubungkan perangkat, lalu coba lagi.':'No camera or microphone was found. Connect your device, then try again.',
    'Izin kamera atau mikrofon belum diberikan. Izinkan melalui pengaturan browser, lalu coba lagi.':'Camera or microphone permission was not granted. Allow access in browser settings, then try again.',
    'Pemeriksaan perangkat berubah. Periksa kembali kamera, mikrofon, suara, dan koneksi sebelum memulai.':'Your device checks changed. Check your camera, microphone, speaker, and connection again before starting.',
    'Fullscreen belum tersedia. Anda tetap dapat melanjutkan sesi.':'Fullscreen is unavailable. You can still continue the session.',
    'Status sesi belum dikenali. Coba muat ulang halaman.':'Unknown session status. Try reloading the page.',
    'Sesi telah ditutup. Buat latihan baru dari menu Simulasi baru.':'This session is closed. Start another from New simulation.',
    'Browser ini belum mendukung pemeriksaan mikrofon. Gunakan browser terbaru.':'This browser does not support microphone checks. Use an up-to-date browser.',
    'Gunakan browser terbaru melalui localhost atau HTTPS untuk kamera dan perekaman.':'Use an up-to-date browser on localhost or HTTPS for camera and recording.',
    'Sesi':'Session', 'Bukti kurang':'Insufficient evidence', 'Tidak ada jawaban yang dinilai':'No answer was assessed',
    'Alur jawaban':'Answer structure', 'Skor untuk latihan':'Practice score', 'Tinjau transkrip sebelum kirim':'Review transcript before sending'
  };
  Object.assign(dictionary, {
    'Profil saya':'My profile', 'Profil':'Profile', 'Menu akun':'Account menu', 'Bagian profil':'Profile sections', 'Informasi akun':'Account information',
    'Kelola data pribadi dan CV untuk latihan berikutnya.':'Manage your personal details and CV for your next interview.',
    'Data pribadi':'Personal information', 'CV saya':'My CV', 'Data ini menjadi isian awal saat membuat simulasi baru.':'These details are used to prefill new simulations.',
    'Informasi akun dan profil kandidat Anda.':'Your account and candidate details.', 'Digunakan untuk masuk ke akun.':'Used to sign in to your account.',
    'Simpan perubahan':'Save changes', 'Unggah CV dalam format PDF.':'Upload your CV as a PDF.',
    'CV tersimpan':'Saved CV', 'Belum ada CV tersimpan':'No saved CV yet', 'Pilih PDF':'Choose a PDF',
    'CV tersimpan bisa dipakai kembali saat membuat simulasi baru. Unggah PDF baru untuk menggantinya.':'Use your saved CV when creating a new simulation. Upload a new PDF to replace it.',
    'Hapus CV':'Remove CV', 'Simpan CV':'Save CV', 'Menyimpan…':'Saving…',
    'Perubahan disimpan.':'Changes saved.', 'CV disimpan.':'CV saved.', 'CV dihapus.':'CV removed.',
    'Hapus CV tersimpan?':'Remove your saved CV?', 'Anda dapat mengunggah PDF CV baru kapan saja.':'You can upload a new PDF CV at any time.',
    'Ganti ke Bahasa Indonesia':'Switch to Indonesian', 'Ganti ke English':'Switch to English',
    'Nama minimal 2 karakter.':'Your name must contain at least 2 characters.', 'Email maksimal 190 karakter.':'Email must not exceed 190 characters.',
    'PDF maksimal 30 halaman.':'The PDF must not exceed 30 pages.', 'File harus berupa PDF yang valid.':'Please choose a valid PDF file.',
    'PDF tidak dapat dibaca. Unggah PDF berteks yang dapat dibuka.':'Unable to read the PDF. Upload a readable, text-based PDF.',
    'Tidak ada perubahan untuk disimpan.':'There are no changes to save.', 'CV minimal 200 karakter setelah dibersihkan.':'Your CV must contain at least 200 characters after cleanup.',
    'Tidak ada latihan yang cocok':'No matching sessions', 'Ubah pencarian atau atur ulang filter.':'Change your search or reset the filters.',
    'Memeriksa…':'Checking…', 'Level sinyal mikrofon':'Microphone signal level', 'Pratinjau kamera untuk verifikasi':'Camera preview for verification',
    'Tutup pemeriksaan perangkat':'Close device checks', 'Periksa perangkat, kamera, mikrofon, dan speaker sebelum mulai.':'Check your device, camera, microphone, and speaker before starting.',
    'HP dan tablet tidak didukung.':'Phones and tablets are not supported.', 'Pertanyaan dijeda.':'Question paused.',
    'Kamera hanya untuk preview lokal.':'Your camera is only used for local preview.', 'Teks':'Text', 'Suara':'Voice',
    'Pilih sesi':'Select session', 'Data latihan':'Practice data', 'Hasil latihan':'Practice results',
    'Fokus mengikuti hasil latihan Anda':'Focus follows your practice results',
    'Belum ada fokus latihan':'No practice focus yet', 'Fokus tersedia setelah latihan dinilai.':'Your focus areas will appear after a session is assessed.',
    'Latihan wawancara':'Interview practice', 'Menyiapkan pertanyaan':'Preparing questions', 'Menyiapkan pewawancara…':'Preparing your interviewer…',
    'Menyiapkan ruang Anda…':'Preparing your room…', 'Pesan baru ↓':'New messages ↓',
    'Keluar dari sesi':'Leave session', 'Keluar dari sesi?':'Leave this session?',
    'Sesi yang ditutup tidak dapat dilanjutkan. Jawaban yang sudah dikirim tetap tersimpan.':'A closed session cannot be resumed. Answers you have already submitted remain saved.',
    'Video tetap lokal. Audio dikirim saat Anda mulai menjawab.':'Video stays local. Audio is sent when you start answering.',
    'Kamera dan mikrofon':'Camera and microphone', 'Akhiri sesi':'End session', 'Batalkan':'Cancel',
    'Siapkan perangkat sebelum mulai.':'Check your devices before starting.', 'Penjelasan indikator penilaian':'Assessment indicator details'
  });
  Object.assign(dictionary, {
    'Keamanan akun':'Account security', 'Privasi dan data':'Privacy and data',
    'Password saat ini':'Current password', 'Password baru':'New password', 'Konfirmasi password baru':'Confirm new password',
    'Masukkan password saat ini untuk mengganti email login.':'Enter your current password to change your sign-in email.',
    'Satu akun hanya dapat memiliki satu sesi login aktif.':'Each account can have only one active sign-in session.',
    'Terlalu banyak percobaan. Tunggu sebentar lalu coba kembali.':'Too many attempts. Wait a moment and try again.',
    'Kata sandi saat ini tidak sesuai.':'Your current password is incorrect.', 'Password saat ini tidak sesuai.':'Your current password is incorrect.',
    'Kredensial akun sudah berubah. Silakan masuk kembali.':'Your account credentials have changed. Please sign in again.',
    'Silakan masuk terlebih dahulu.':'Please sign in first.',
    'Login dari browser atau perangkat lain ditolak selama sesi ini aktif. Keluar terlebih dahulu jika ingin berpindah perangkat.':'Sign-in from another browser or device is blocked while this session is active. Sign out first to switch devices.',
    'Memuat informasi sesi…':'Loading session details…', 'Informasi sesi belum dapat dimuat.':'Session details could not be loaded.',
    'Setelah password berubah, sesi ini berakhir dan Anda perlu masuk kembali.':'Changing your password ends this session. You will need to sign in again.',
    'Ganti password':'Change password', 'Password minimal 8 karakter, berisi huruf dan angka, maksimal 72 byte.':'Use at least 8 characters, including letters and numbers, and no more than 72 bytes.',
    'Atur penyimpanan dan lihat bukti penghapusan data Anda.':'Manage storage and review your data deletion receipts.',
    'Memuat kebijakan retensi…':'Loading retention policy…', 'Memuat tanda terima…':'Loading receipts…',
    'Kelola dan hapus riwayat latihan':'Manage and delete practice history', 'Bukti penghapusan':'Deletion receipts',
    'Hapus akun':'Delete account', 'Hapus akun saya':'Delete my account', 'Hapus akun permanen':'Permanently delete account',
    'Hapus akun, CV, seluruh riwayat, jawaban, hasil, dan berkas audio dalam aplikasi.':'Delete your account, CV, all history, answers, results, and audio files in the app.',
    'Tindakan ini tidak dapat dibatalkan. Sesi login akan langsung berakhir.':'This cannot be undone. Your sign-in session will end immediately.',
    'Akun sudah dihapus.':'Your account has been deleted.',
    'Sesi login sudah berakhir. Simpan tanda terima sebelum meninggalkan halaman ini.':'Your sign-in session has ended. Save your receipt before leaving this page.',
    'Kembali ke halaman masuk':'Back to sign in', 'Hapus akun secara permanen?':'Permanently delete your account?',
    'Akun, CV, seluruh riwayat, transkrip, hasil, dan audio dalam aplikasi akan dihapus. Tindakan ini tidak dapat dibatalkan.':'Your account, CV, all history, transcripts, results, and audio in the app will be deleted. This cannot be undone.',
    'Ketik teks konfirmasi':'Type the confirmation text', 'Teks konfirmasi belum sesuai.':'The confirmation text does not match.',
    'Konfirmasi hapus CV':'Confirm CV deletion', 'Konfirmasi hapus akun':'Confirm account deletion', 'Konfirmasi hapus riwayat':'Confirm history deletion',
    'Menghapus CV tersimpan tidak menghapus salinan dalam sesi lama. Hapus riwayat terkait untuk menghapus salinan tersebut.':'Removing your saved CV does not remove copies in past sessions. Delete the relevant history to remove those copies.',
    'Penghapusan selesai.':'Deletion complete.', 'Penghapusan berkas masih diproses.':'File deletion is still in progress.',
    'Tanda terima ini mencatat data yang telah dihapus dari aplikasi.':'This receipt records the data deleted from the app.',
    'Data dalam database sudah dihapus. Pembersihan berkas akan dicoba kembali secara otomatis.':'Database data has been deleted. File cleanup will be retried automatically.',
    'ID tanda terima':'Receipt ID', 'Sesi':'Sessions', 'Berkas':'Files', 'Unduh tanda terima':'Download receipt', 'Unduh':'Download',
    'Audio yang disimpan':'Stored audio', 'Riwayat, transkrip, dan hasil':'History, transcripts, and results', 'Tanda terima penghapusan':'Deletion receipts',
    'Sampai Anda menghapus CV atau akun.':'Until you delete your CV or account.', 'Pembersihan otomatis berjalan secara berkala.':'Automatic cleanup runs periodically.',
    'Pembersihan otomatis belum diaktifkan oleh pengelola.':'Automatic cleanup has not been enabled by the administrator.',
    'Salinan pada provider AI dan backup dikelola terpisah; tanda terima ini tidak menyatakan penghapusan dari layanan tersebut.':'Copies held by AI providers and backups are managed separately; this receipt does not confirm deletion from those services.',
    'Kebijakan retensi belum dapat dimuat. Coba muat ulang halaman.':'The retention policy could not be loaded. Reload this page to try again.',
    'Belum ada tanda terima penghapusan.':'No deletion receipts yet.', 'Berkas menunggu pembersihan':'File cleanup pending',
    'Retensi otomatis':'Automatic retention', 'Penghapusan data':'Data deletion', 'Akun':'Account',
    'Tanda terima belum dapat dimuat. Coba muat ulang halaman.':'Receipts could not be loaded. Reload this page to try again.',
    'Anda dapat menghapus satu sesi atau seluruh riwayat secara permanen.':'You can permanently delete a single session or your entire history.',
    'Hapus semua riwayat':'Delete all history', 'Penyimpanan data latihan':'Practice data storage', 'Lihat bukti penghapusan':'View deletion receipts',
    'Hapus sesi':'Delete session', 'Hapus sesi ini?':'Delete this session?', 'Hapus seluruh riwayat?':'Delete all history?', 'Hapus permanen':'Delete permanently',
    'Pertanyaan, jawaban, transkrip, hasil, salinan CV dalam sesi, dan audio akan dihapus. Tindakan ini tidak dapat dibatalkan.':'Questions, answers, transcripts, results, CV copies in this session, and audio will be deleted. This cannot be undone.',
    'Semua sesi Anda akan dihapus, termasuk yang tidak terlihat karena filter. CV yang tersimpan di profil tetap ada. Tindakan ini tidak dapat dibatalkan.':'All your sessions will be deleted, including those hidden by filters. The CV saved in your profile will remain. This cannot be undone.'
  });
  const aliases = {'Not Ready':'Belum siap','Needs Work':'Perlu latihan','Ready':'Siap'};
  Object.assign(dictionary, {'Belum siap':'Not Ready','Perlu latihan':'Needs Work','Siap':'Ready'});
  const reverse = new Map(Object.entries(dictionary).filter(([, en]) => en).map(([id, en]) => [en, id]));
  const insensitive = new Map(Object.keys(dictionary).map(key => [key.toLowerCase(), key]));
  const texts = new WeakMap(), attributes = new WeakMap();
  const excluded = 'script,style,textarea,code,pre,[data-ui-content],.brand-name,.setup-account-name,.setup-preview-name,#setup-preview-name,#interviewer-name,.chat-message--interviewer .chat-message-author,.chat-message--interviewer .chat-message-body,.chat-message--candidate .chat-message-body,#question-text,#transcript,#stage-caption,#interviewer-response,.ws-session-main strong,.ws-session-main small,.result-summary-text,.result-feedback-list,.result-answer-heading > strong,.transcript,blockquote,.result-answer-tip p,.result-next-list h3,.result-next-list p,.evidence-detail > p,.indicator-evidence > strong';
  const patterns = [
    [/^(\d+) hari$/, (_, n) => `${n} days`],
    [/^Akun masih aktif di browser atau perangkat lain\. Keluar dari sesi tersebut, atau tunggu (\d+) menit tanpa aktivitas sebelum masuk kembali\.$/, (_, minutes) => `Your account is active in another browser or device. Sign out of that session, or wait for ${minutes} minutes of inactivity before signing in again.`],
    [/^Sesi berakhir setelah (\d+) menit tanpa aktivitas atau maksimal (\d+) jam\.$/, (_, idle, absolute) => `Your session ends after ${idle} minutes of inactivity or after ${absolute} hours at most.`],
    [/^Halo, (.+)$/, (_, name) => `Hello, ${name}`],
    [/^Latihan (.+)$/, (_, role) => `Practice for ${role}`],
    [/^Panel (\d+) pewawancara$/, (_, n) => `Panel of ${n} interviewers`],
    [/^(\d+) sesi terakhir yang dinilai$/, (_, n) => `${n} most recent assessed sessions`],
    [/^(\d+) sesi dinilai$/, (_, n) => `${n} assessed sessions`],
    [/^(\d+) sesi$/, (_, n) => `${n} sessions`],
    [/^(\d+) dari (\d+) latihan$/, (_, n, total) => `${n} of ${total} sessions`],
    [/^(\d+) jawaban$/, (_, n) => `${n} answers`],
    [/^(\d+) peserta$/, (_, n) => `${n} participants`],
    [/^(\d+) pertanyaan dilewati$/, (_, n) => `${n} questions skipped`],
    [/^(\d+) pertanyaan$/, (_, n) => `${n} questions`],
    [/^Pertanyaan (\d+)(.*)$/, (_, n, rest) => `Question ${n}${rest}`],
    [/^(\d+) dari (\d+) kompetensi$/, (_, n, total) => `${n} of ${total} competencies`],
    [/^Halaman (\d+) dari (\d+)$/, (_, n, total) => `Page ${n} of ${total}`],
    [/^Menampilkan (\d+)[–-](\d+) dari (\d+) sesi$/, (_, first, last, total) => `Showing ${first}–${last} of ${total} sessions`],
    [/^(\d+)[–-](\d+) dari (\d+) sesi$/, (_, first, last, total) => `${first}–${last} of ${total} sessions`],
    [/^Skor terakhir (\d+)\/100$/, (_, n) => `Latest score ${n}/100`],
    [/^(\d+) detik per jawaban$/, (_, n) => `${n} seconds per answer`],
    [/^(\d+) kata\/menit$/, (_, n) => `${n} words/min`],
    [/^(\d+) kata pengisi(.*)$/, (_, n, rest) => `${n} filler words${rest === '. Konteks penyampaian, bukan penalti otomatis.' ? '. Speaking context, not an automatic penalty.' : rest}`],
    [/^[Tt]erlewat di (\d+)% jawaban$/, (_, n) => `Missing in ${n}% of answers`],
    [/^Kamera (aktif|nonaktif)$/, (_, state) => `Camera ${state === 'aktif' ? 'on' : 'off'}`],
    [/^Mikrofon (aktif|nonaktif)$/, (_, state) => `Microphone ${state === 'aktif' ? 'on' : 'off'}`],
    [/^Karakter pewawancara AI (.+)$/, (_, name) => `AI interviewer character ${name}`],
    [/^(.+), pewawancara AI$/, (_, name) => `${name}, AI interviewer`],
    [/^Konteks: (.+)$/, (_, value) => `Context: ${value}`],
    [/^Rubrik (.+)$/, (_, value) => `Rubric ${translate(value)}`],
    [/^Tingkat (\d+)$/, (_, n) => `Level ${n}`],
    [/^Giliran (.+)$/, (_, n) => `Turn ${n}`],
    [/^(\d+) pesan baru$/, (_, n) => `${n} new messages`],
    [/^Menilai (.+)$/, (_, value) => `Assessing ${value}`]
  ];
  function preference() {
    const query = new URLSearchParams(location.search).get('lang');
    if (query === 'en' || query === 'id') return query;
    const cookie = document.cookie.match(/(?:^|; )preptiva_ui_language=(en|id)(?:;|$)/)?.[1];
    if (cookie) return cookie;
    try {const saved = localStorage.getItem('preptiva-ui-language'); if (saved === 'id' || saved === 'en') return saved;} catch {}
    return 'en';
  }
  let language = preference();
  function translate(value) {
    const original = String(value ?? '');
    const trimmed = original.trim();
    if (!trimmed) return original;
    const canonical = Object.hasOwn(dictionary, trimmed) ? trimmed : aliases[trimmed] || reverse.get(trimmed) || trimmed;
    let translated = canonical;
    if (language === 'en') {
      if (Object.hasOwn(dictionary, canonical)) translated = dictionary[canonical];
      else {
        const caseKey = insensitive.get(canonical.toLowerCase());
        if (caseKey) translated = canonical === canonical.toUpperCase() ? dictionary[caseKey].toUpperCase() : dictionary[caseKey];
        else {
          for (const [pattern, replace] of patterns) if (pattern.test(canonical)) {translated = canonical.replace(pattern, replace); break;}
          if (translated === canonical && canonical.includes(' · ')) translated = canonical.split(' · ').map(translate).join(' · ');
        }
      }
    }
    return original.slice(0, original.indexOf(trimmed)) + translated + original.slice(original.indexOf(trimmed) + trimmed.length);
  }
  function isContent(element) {return !element || !!element.closest(excluded);}
  function text(node) {
    if (isContent(node.parentElement)) return;
    const current = node.nodeValue;
    let saved = texts.get(node);
    if (!saved || current !== saved.rendered) saved = {source: current};
    const rendered = translate(saved.source);
    saved.rendered = rendered; texts.set(node, saved);
    if (rendered !== current) node.nodeValue = rendered;
  }
  function attrs(element) {
    if (isContent(element)) return;
    let saved = attributes.get(element);
    if (!saved) {saved = new Map(); attributes.set(element, saved);}
    for (const name of ['title','placeholder','aria-label','aria-description','alt']) {
      if (!element.hasAttribute(name)) continue;
      const current = element.getAttribute(name);
      let entry = saved.get(name);
      if (!entry || current !== entry.rendered) entry = {source: current};
      entry.rendered = translate(entry.source); saved.set(name, entry);
      if (current !== entry.rendered) element.setAttribute(name, entry.rendered);
    }
  }
  function apply(root) {
    if (root.nodeType === Node.TEXT_NODE) {text(root); return;}
    if (root.nodeType !== Node.ELEMENT_NODE || isContent(root)) return;
    attrs(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: node => node.nodeType === Node.ELEMENT_NODE && isContent(node) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
    });
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.nodeType === Node.TEXT_NODE) text(node); else attrs(node);
    }
  }
  function setLanguage(value, updateUrl = false) {
    if (value !== 'id' && value !== 'en') return;
    language = value;
    document.documentElement.lang = value;
    try {localStorage.setItem('preptiva-ui-language', value);} catch {}
    document.cookie = `preptiva_ui_language=${value}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === 'https:' ? '; Secure' : ''}`;
    if (updateUrl) {const url = new URL(location.href); url.searchParams.set('lang', value); history.replaceState(history.state, '', url);}
    for (const button of document.querySelectorAll('[data-language-toggle]')) {
      button.dataset.language = value;
      const label = value === 'en' ? 'English. Switch to Bahasa Indonesia' : 'Bahasa Indonesia. Ganti ke English';
      button.setAttribute('aria-label',label);button.title=label;
    }
    for (const link of document.querySelectorAll('[data-ui-language]')) {
      const url = new URL(location.href); url.searchParams.set('lang', link.dataset.uiLanguage);
      link.href = url.pathname + url.search + url.hash;
      if (link.dataset.uiLanguage === value) link.setAttribute('aria-current', 'true'); else link.removeAttribute('aria-current');
    }
    apply(document.body);
    const title = document.querySelector('title'); if (title) apply(title);
    window.dispatchEvent(new CustomEvent('preptiva:languagechange', {detail: {language: value}}));
  }
  window.PreptivaI18n = {get language() {return language;}, get locale() {return language === 'id' ? 'id-ID' : 'en-GB';}, t: translate, setLanguage};
  document.addEventListener('click', event => {
    const toggle = event.target.closest?.('[data-language-toggle]');
    if (toggle) {setLanguage(language === 'en' ? 'id' : 'en', true);return;}
    const link = event.target.closest?.('[data-ui-language]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); setLanguage(link.dataset.uiLanguage, true);
  });
  setLanguage(language);
  new MutationObserver(records => {
    for (const record of records) {
      if (record.type === 'characterData') text(record.target);
      else if (record.type === 'attributes') attrs(record.target);
      else for (const added of record.addedNodes) apply(added);
    }
  }).observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['title','placeholder','aria-label','aria-description','alt']});
})();
