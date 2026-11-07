# Cleansing CV/JD dan chunking dokumen

Diperbarui: 5 November 2026.

## Cleansing konservatif

`app/services/text.py` menangani teks PDF, teks CV yang ditempel, CV tersimpan yang dipakai ulang, dan job description sebelum disimpan ke sesi baru. Pipeline ekstraksi juga membersihkan input sesi lama saat dipersiapkan.

- Normalisasi Unicode NFC, newline CRLF/CR, tab/spasi berlebih, non-breaking space, BOM, zero-width space, word joiner, soft hyphen, serta karakter kontrol.
- Paragraf, baris, bullet, angka pencapaian, tanggal, nama, email, nomor telepon, C++, C#, dan istilah teknis tetap dipertahankan. Tidak melakukan stemming, lowercasing keseluruhan, terjemahan, penghapusan stopword, atau koreksi fakta.
- PDF mempertahankan pemisahan halaman/paragraf. Nomor halaman berlabel Page/Halaman di margin dibuang. Baris margin pendek yang sama pada minimal tiga halaman dipertahankan di halaman pertama dan dihapus pada halaman berikutnya.
- Pembersihan margin bersifat heuristik: periksa hasil pada CV dengan layout rumit. PDF hasil scan tanpa teks tetap memerlukan OCR di luar aplikasi atau input teks manual. Tidak ada OCR otomatis.
- File PDF asli tidak ditulis ulang; sesi dan CV terakhir menyimpan teks bersih. Dokumen lama tidak dimigrasi massal.

## Batas input

PDF maksimal 5 MB dan 30 halaman. Jumlah halaman berlebih ditolak, bukan diam-diam membaca hanya sepuluh halaman pertama. Teks CV minimal 200 dan maksimal 60.000 karakter setelah cleansing. JD minimal 30 dan maksimal 40.000 karakter. Input berlebih ditolak dengan pesan ralat; tidak dipotong diam-diam.

## Kapan memakai chunking

Dokumen pendek (CV <=12.000 dan JD <=8.000 karakter) tetap diekstrak dalam satu panggilan GPT-4o-mini agar cepat dan hemat.

Jika salah satu melebihi ambang itu, teks CV dibagi maksimal 6.000 karakter dan JD 4.000 karakter. Pemotongan mengutamakan paragraf, lalu baris, lalu spasi, dengan fallback panjang tetap untuk token teks yang sangat panjang. Tidak ada overlap karena semua chunk dibaca untuk ekstraksi, bukan pencarian semantik.

Bagian CV dan JD dipasangkan berdasarkan indeks. Jika salah satu habis, bagiannya dikirim kosong; semua bagian dokumen lain tetap diproses. Maksimal dua panggilan ekstraksi berjalan bersamaan. Pada input maksimum diperlukan sekitar 10 batch untuk potongan penuh; pemilihan batas alami dapat menghasilkan hingga sekitar 20 batch yang lebih pendek. Setiap hasil diekstrak dengan output maksimal 1.200 token. Jika salah satu gagal, persiapan gagal; tidak mengganti dengan data dummy atau mengabaikan chunk tersebut.

Ringkasan digabung dengan deduplikasi daftar secara persis. Field skalar memakai nilai non-null pertama; `years_exp` memakai angka terbesar, bukan penjumlahan, karena rentang kerja bisa tumpang tindih. Angka ini tetap estimasi model, bukan rekonstruksi masa kerja berdasarkan tanggal. Ringkasan bukan salinan semua fakta; model masih dapat melewatkan detail. Namun input di akhir dokumen tidak lagi dibuang sebelum dibaca model.

Ekstraksi chunk menambah panggilan/token dan waktu persiapan pada dokumen panjang. Generasi pertanyaan menerima ringkasan gabungan, bukan seluruh teks mentah. Tidak ada embedding, vector database, atau RAG: satu CV dan satu JD belum memerlukannya. Tambahkan pencarian semantik hanya jika kelak harus mengambil bukti relevan dari kumpulan dokumen besar.

## Verifikasi dan log

Tes mencakup preservasi angka/istilah/identitas, idempotensi cleansing, margin PDF, batas input, preservasi bagian akhir dokumen, deduplikasi, dan konkurensi. Event `documents_chunked` mencatat jumlah karakter/chunk tanpa isi CV/JD; `llm_usage` dengan step `parse_chunk` mencatat token masing-masing panggilan.
