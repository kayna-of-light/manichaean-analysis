# Coptic Transcription Pipeline — Technical Documentation

## Overview

End-to-end pipeline for transcribing the original Coptic text of the Kephalaia from the Polotsky/Böhlig 1940 critical edition PDF into Unicode Coptic text.

**Script**: `scripts/transcribe_coptic_v2.py`
**Model**: Claude Opus 4.6 (Anthropic via Azure AI Foundry), vision mode, thinking disabled
**Environment**: `conda activate nhl`

---

## Source Material

**PDF**: `data/Kephalaia -- Mani...Stuttgart.pdf`
- 522 PDF pages total
- Coptic text pages at odd PDF indices: 49, 51, 53, ..., 517
- German translation pages at even PDF indices: 48, 50, 52, ..., 518
- Printed page numbers: 10 (first Coptic) through 244 (last Coptic)
- Total Coptic pages: 235

**English Translation**: `output/texts/Kephalaia_of_the_Teacher.md`
- Gardner's English translation of the Kephalaia
- Contains inline `(N)` markers for all 235 Coptic page numbers
- Auto-extracted per page by regex matching between consecutive markers

---

## Architecture

### Two-Pass Design

The pipeline uses two sequential Claude vision calls per page:

```
┌──────────────┐     ┌───────────────────┐     ┌───────────────────┐
│  PDF page     │────▶│  Pass 1: Blind    │────▶│  Pass 2: Validate │────▶ Final text
│  (JPEG)       │     │  (image only)     │     │  (image + text +  │
└──────────────┘     │                   │     │   English)         │
                     └───────────────────┘     └───────────────────┘
```

**Why two passes?**

A single pass with image + English causes **confirmation bias**: the model reads the English and then "sees" what it expects rather than what is actually printed. Proper names and Greek loanwords get especially distorted because the model recognizes the word from English context but misreads specific Coptic letterforms.

The two-pass design separates perception from validation:
- Pass 1 reads only what is there (no English context to bias it)
- Pass 2 knows what _should_ be there (from English) and can identify where Pass 1 got it wrong

### Pass 1: Expert Blind Extraction

**Input**: Page image only
**System prompt**: Full Coptic philological expertise (Lycopolitan dialect, Unicode guidance, editorial mark conventions) but zero English context
**Task**: Transcribe the printed Coptic exactly as seen

The "blind" means no English, not no expertise. The model is given detailed guidance on:
- Unicode Coptic block (U+2C80-U+2CFF)
- Combining overline (U+0305) for supralinear strokes
- Lycopolitan dialect letter distinctions
- Editorial marks (brackets, dots, lacuna notation)
- Page structure (ignore German header, ignore footnotes)

### Pass 2: English-Guided Validation

**Input**: Page image + Pass 1 transcription + English translation
**System prompt**: Explains the specific problem (the model has systematic character errors) and provides detailed error categories
**Task**: Walk through the English meaning line by line, identify where the Coptic doesn't match, correct from the image

The English serves as a **red thread** (semantic guide), not a translation target. The correction operates in one direction:

```
English meaning → identifies likely error locations → re-examine image → correct Coptic
```

The model is explicitly told to preserve Coptic features invisible in English: morphology, dialect forms, grammatical particles, prefix/suffix constructions.

### Specific Error Categories Addressed by Pass 2

| Error Type | Example | Cause |
|---|---|---|
| Proper name corruption | ⲁⲗⲁⲙ → ⲁⲇⲁⲙ | Model confuses ⲗ/ⲇ in vision |
| Greek loanword garbling | ⲧϥⲁⲣⲝ → ⲧⲥⲁⲣⲝ | Misreads letter sequences |
| ⲝ/ⲭ confusion | ⲝⲉ → ⲭⲉ | Near-identical typeface glyphs |
| Lycopolitan letter instability | ⲉ/ⲋ/ⲍ/ϩ for same letter | No stable Unicode target |
| Missing supralinear strokes | ⲛ → ⲛ̄ | Overline mark missed |
| Unicode inconsistency | Same letter → different codepoints | Model lacks consistent mapping |

---

## Auto-English Extraction

The `extract_english_for_page(page_num)` function automatically retrieves the English translation corresponding to each Coptic page:

1. Reads `output/texts/Kephalaia_of_the_Teacher.md`
2. Searches for `(page_num)` marker
3. Extracts text between `(page_num)` and `(page_num + 1)`
4. Returns the section as the English context for Pass 2

**Coverage**: All 235 Coptic pages (10-244) have markers. No manual alignment needed.

**False positive handling**: The regex `\(\d+\)` also matches footnote references and other parenthesized numbers, but since we search for specific page numbers in the expected range and extract bounded sections, false positives in higher ranges (>244) don't affect the pipeline.

---

## Usage

### Prerequisites

```bash
conda activate nhl    # Has PyMuPDF, anthropic, httpx, dotenv
```

Credentials in `secrets/azure_openai.env`:
```env
ANTHROPIC_ENDPOINT=https://your-foundry-endpoint
ANTHROPIC_API_KEY=your-key
ANTHROPIC_DEPLOYMENT=claude-opus-4-6
```

### Commands

```bash
# Single page:
python scripts/transcribe_coptic_v2.py --pages 12

# Page range:
python scripts/transcribe_coptic_v2.py --pages 10-20

# Multiple pages:
python scripts/transcribe_coptic_v2.py --pages 10,11,12

# All Coptic pages:
python scripts/transcribe_coptic_v2.py --pages all

# Resume interrupted batch:
python scripts/transcribe_coptic_v2.py --pages all --skip-existing

# Reuse pass1 (after prompt refinement):
python scripts/transcribe_coptic_v2.py --pages 12 --reuse-pass1

# Custom DPI for extraction:
python scripts/transcribe_coptic_v2.py --pages 12 --dpi 300

# From pre-extracted image:
python scripts/transcribe_coptic_v2.py --image output/kephalaia_pages/keph_p012.jpg
```

### Flags

| Flag | Description |
|---|---|
| `--pages` | Page spec: single, range, comma-separated, or `all` (mutually exclusive with `--image`) |
| `--image` | Pre-extracted page image path (backward compat, mutually exclusive with `--pages`) |
| `--english` | Manual English translation file (overrides auto-extraction) |
| `--no-auto-english` | Disable auto-extraction from Gardner (Pass 2 skipped) |
| `--reuse-pass1` | Reuse existing `_pass1.txt` if available |
| `--skip-existing` | Skip pages that already have `_pass2.txt` output |
| `--dpi` | PDF rendering resolution (default: 200) |
| `--output-dir` | Output directory (default: `output/kephalaia_coptic/`) |

---

## Output

### Per-Page Files

| File | Content |
|---|---|
| `output/kephalaia_pages/keph_pNNN.jpg` | Extracted page image (cached, ~200 KB at 200 DPI) |
| `output/kephalaia_coptic/keph_pNNN_pass1.txt` | Pass 1 blind extraction |
| `output/kephalaia_coptic/keph_pNNN_pass2.txt` | Pass 2 corrected transcription (final result) |
| `output/kephalaia_coptic/keph_pNNN_twopass.json` | Combined metadata JSON |

### JSON Structure

```json
{
  "source_image": "path/to/keph_p012.jpg",
  "page_name": "keph_p012",
  "pass1": {
    "transcription": "...",
    "lines": ["..."],
    "input_tokens": 2074,
    "output_tokens": 4088,
    "elapsed_seconds": 75.4
  },
  "pass2": {
    "transcription": "...",
    "lines": ["..."],
    "english_chars": 1832,
    "input_tokens": 8044,
    "output_tokens": 4090,
    "elapsed_seconds": 46.1
  },
  "english_text": "..."
}
```

---

## Performance & Cost

### Per Page
- Pass 1: ~2K input tokens (image) + ~4K output tokens, ~75s
- Pass 2: ~8K input tokens (image + text + English) + ~4K output tokens, ~45s
- Total: ~14K tokens, ~2 minutes

### Full Corpus (235 pages)
- Estimated: ~3.3M tokens, ~8 hours
- Use `--skip-existing` to resume interrupted runs

### Accuracy
- Pass 2 typically corrects 30-40% of lines
- Proper names, Greek loanwords, and ⲝ/ⲭ distinctions show the largest improvements
- No published digital Coptic ground truth exists for validation

---

## Pipeline Integration

The Coptic transcription pipeline is independent of the main analysis pipeline (Stages 0-8) but the outputs serve complementary purposes:

- **Main pipeline** (Stages 0-8): Processes Gardner's English translation through layer separation, core extraction, and correspondential restoration
- **Coptic pipeline**: Provides the original-language evidence that the English translation is derived from

Future integration: Coptic transcriptions can be used to verify correspondential readings at the vocabulary level (e.g., confirming that Gardner's "flesh" corresponds to ⲥⲁⲣⲝ, not ⲥⲱⲙⲁ, at specific passages).

---

## Legacy Scripts

| Script | Status | Notes |
|---|---|---|
| `extract_kephalaia_pages.py` | Standalone, still works | Bulk PDF extraction without transcription |
| `transcribe_coptic.py` | v1 single-pass, still works | Simpler but less accurate than v2 |
| `transcribe_coptic_v2.py` | **Current** | Full pipeline: PDF extraction + two-pass OCR |

---

## Critical Implementation Notes

- **Thinking MUST be disabled**: Adaptive thinking on Opus 4.6 burns all tokens on Coptic vision tasks without producing output. The script sets `thinking={"type": "disabled"}` explicitly.
- **Streaming with retries**: The API connection can drop during the ~75s streaming window. The script retries up to 3 times with 5s backoff.
- **Image caching**: PDF extraction is expensive. Images are cached in `output/kephalaia_pages/` and reused on subsequent runs.
- **UTF-8 throughout**: All file I/O uses `encoding="utf-8"` to preserve Coptic Unicode characters.
