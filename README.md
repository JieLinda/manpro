# LLM → XLSX Extractor

Aplikasi Python untuk mengekstrak data terstruktur dari dokumen (PDF, DOCX, TXT, CSV, XLSX, gambar) menggunakan layanan LLM yang kompatibel dengan OpenAI API, lalu menyimpannya ke file Excel (.xlsx).

## Instalasi

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # lalu isi LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
```

## Pemakaian

```bash
# satu file
python -m app.main -s schemas/contoh_invoice.yaml -i input/faktur.pdf -o output/faktur.xlsx

# satu folder (semua file yang didukung, rekursif)
python -m app.main -s schemas/contoh_invoice.yaml -i input/
```

Tanpa `-o`, hasil disimpan ke `output/hasil_<timestamp>.xlsx`.

## Skema

Kolom yang diekstrak ditentukan di file YAML/JSON (lihat `schemas/contoh_invoice.yaml`). Tipe yang didukung: `string`, `number`, `integer`, `date`, `boolean`. Isi `instructions` dengan konteks domain agar hasil LLM lebih akurat.

## Alur

```
file → readers.py (teks / gambar) → chunk → llm_client.py (JSON mode)
     → extractor.py (normalisasi tipe, dedupe) → xlsx_writer.py
```

## Catatan

- **Format angka** Indonesia & internasional ditangani (`Rp 1.250.000,50` → 1250000.5).
- **Gambar** dikirim ke LLM sebagai input vision, jadi `LLM_MODEL` harus model yang mendukung gambar.
- **PDF hasil scan** (tanpa teks) ditolak dengan pesan jelas; ubah ke gambar atau OCR dahulu.
- **JSON mode**: bila endpoint tidak mendukung `response_format`, klien otomatis beralih ke mode biasa dan mem-parsing JSON dari teks.
- **Error per file** tidak menghentikan batch; dicatat di sheet `Log Error` pada file hasil.
- Kolom `Sumber` mencatat nama file asal setiap baris.

## Struktur

```
app/
  config.py       # baca .env
  schema.py       # model skema kolom
  readers.py      # pembaca dokumen + chunking
  llm_client.py   # klien OpenAI-compatible + retry
  extractor.py    # prompt, normalisasi, dedupe
  xlsx_writer.py  # tulis Excel bergaya
  main.py         # CLI
schemas/          # definisi skema ekstraksi
input/  output/
```
