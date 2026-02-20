# Manichaean Analysis — Script Audit for Refactoring

> Generated from full source reads of all 13 pipeline scripts.
> Use this to plan path consolidation, shared-config extraction, and CLI standardisation.

---

## Output Directory Tree (all hardcoded targets)

```
output/
├── texts/                          # stage_0_ingest.py writes raw markdown
│   └── Kephalaia_of_the_Teacher.md # (+ 11 other .md files from PDF_CATALOG)
├── cleaned/
│   ├── chapters/                   # stage_1_clean.py writes per-chapter JSON
│   │   └── ch_NNN.json
│   ├── kephalaia_teaching.md       # stage_1_clean.py assembly
│   └── kephalaia_apparatus.md      # stage_1_clean.py assembly
├── analysis/
│   ├── kephalaia_layer_analysis.json   # kephalaia_layer_analysis.py
│   ├── kephalaia_layer_analysis_report.md
│   ├── 01_..06_*.png               # kephalaia_layer_analysis.py (6 PNGs)
│   ├── registers/
│   │   └── register_analysis.json  # register_analysis.py
│   ├── v2/                         # kephalaia_core_recovery.py
│   │   ├── v2_report.md
│   │   ├── v2_data.json
│   │   └── v2_01..06_*.png         # 6 PNGs
│   ├── v3/                         # kephalaia_paragraph_recovery.py
│   │   ├── v3_report.md
│   │   ├── v3_reconstruction.md
│   │   ├── v3_paragraphs.json
│   │   └── v3_01..08_*.png         # 8 PNGs
│   └── v4/                         # kephalaia_layer_analysis_v4.py
│       ├── v4_report.md
│       ├── v4_data.json
│       ├── v4_paragraphs.json
│       └── v4_01..07_*.png         # 7 PNGs
├── core/                           # stage_4_extract.py
│   ├── chapters/
│   │   └── ch_NNN.json             # (also read by clean_page_breaks.py in-place)
│   ├── restored_core.md
│   └── core_data.json
├── restored/               # stage_5_restore.py
│   ├── chapters/
│   │   └── ch_NNN.json
│   └── restored_kephalaia.md
├── substrate/                      # reconstruct_substrate.py
│   ├── segments/
│   │   └── ch_NNN.json
│   ├── restored_substrate.md
│   └── substrate_data.json
├── pdfs/
│   ├── Kephalaia_Layer_1_Extract.pdf   # generate_layer1_pdf.py
│   └── Kephalaia_Reading_Edition.pdf   # generate_reading_pdf.py
└── Kephalaia_Layer_1_Extract.md    # generate_layer1_pdf.py reads from here
```

---

## Per-Script Detail

### 1. `stage_0_ingest.py` — 300 lines

| Item | Detail |
|------|--------|
| **Path constants** | `PROJECT_ROOT = Path(__file__).parent.parent` (L17) |
| | `DATA_DIR = PROJECT_ROOT / "data"` (L18) |
| | `OUTPUT_DIR = PROJECT_ROOT / "output" / "texts"` (L19) |
| **CLI** | `--dry-run` (sys.argv), positional PDF name filter |
| **Reads** | `data/*.pdf.json` (Azure Document Intelligence OCR JSON) |
| **Writes** | `output/texts/<name>.md` (12 files defined in `PDF_CATALOG` dict) |
| **LLM** | None |
| **⚠ Notes** | Uses `sys.argv` instead of `argparse`. `PDF_CATALOG` maps 12 PDF filenames → markdown output names. |

---

### 2. `stage_1_clean.py` — 664 lines

| Item | Detail |
|------|--------|
| **Path constants** | `PROJECT_ROOT = Path(__file__).resolve().parent.parent` (L39) |
| | `SECRETS_PATH = PROJECT_ROOT / "secrets" / "azure_openai.env"` (L40) |
| | `SOURCE_FILE = PROJECT_ROOT / "output" / "texts" / "Kephalaia_of_the_Teacher.md"` (L41) |
| | `OUTPUT_DIR = PROJECT_ROOT / "output" / "cleaned"` (L42) |
| | `CHAPTERS_DIR = OUTPUT_DIR / "chapters"` (L43) |
| | `TEACHING_FILE = OUTPUT_DIR / "kephalaia_teaching.md"` (L44) |
| | `APPARATUS_FILE = OUTPUT_DIR / "kephalaia_apparatus.md"` (L45) |
| **CLI (argparse)** | `--chapter` (int), `--range` (str "N-M"), `--dry-run`, `--list`, `--overwrite`, `--assemble-only` |
| **Reads** | `output/texts/Kephalaia_of_the_Teacher.md`, `output/cleaned/chapters/ch_NNN.json` |
| **Writes** | `output/cleaned/chapters/ch_NNN.json`, `output/cleaned/kephalaia_teaching.md`, `output/cleaned/kephalaia_apparatus.md` |
| **LLM** | GPT-5.2 via OpenAI (structured output with Pydantic `CleanedChapter`) |

---

### 3. `register_analysis.py` — 563 lines

| Item | Detail |
|------|--------|
| **Path constants** | `PROJECT_ROOT = Path(__file__).resolve().parent.parent` (L51) |
| | `CHAPTERS_DIR = PROJECT_ROOT / "output" / "cleaned" / "chapters"` (L52) |
| | `OUTPUT_DIR = PROJECT_ROOT / "output" / "analysis" / "registers"` (L53?) |
| **CLI (argparse)** | `--chapter` / `-c` (int), `--report` / `-r`, `--save` / `-s` |
| **Reads** | `output/cleaned/chapters/ch_*.json` |
| **Writes** | `output/analysis/registers/register_analysis.json` (when `--save`) |
| **LLM** | None |
| **⚠ Notes** | Defines 5 marker vocabulary dicts (CORRESPONDENTIAL, COSMOLOGICAL, CHRISTIAN, FRAME, PASTORAL). These are **duplicated** in `stage_4_extract.py`. |

---

### 4. `stage_4_extract.py` — 1606 lines

| Item | Detail |
|------|--------|
| **Path constants** | `PROJECT_ROOT = Path(__file__).resolve().parent.parent` (L63) |
| | `SECRETS_PATH = PROJECT_ROOT / "secrets" / "azure_openai.env"` (L64) |
| | `CHAPTERS_DIR = PROJECT_ROOT / "output" / "cleaned" / "chapters"` (L65) |
| | `REGISTER_JSON = PROJECT_ROOT / "output" / "analysis" / "registers" / "register_analysis.json"` (L66) |
| | `V4_DATA_JSON = PROJECT_ROOT / "output" / "analysis" / "v4" / "v4_data.json"` (L67) |
| | `V4_PARA_JSON = PROJECT_ROOT / "output" / "analysis" / "v4" / "v4_paragraphs.json"` (L68) |
| | `OUTPUT_DIR = PROJECT_ROOT / "output" / "core"` (L69) |
| | `SEGMENTS_DIR = OUTPUT_DIR / "chapters"` (L70) |
| | `ASSEMBLED_FILE = OUTPUT_DIR / "restored_core.md"` (L71) |
| | `DATA_FILE = OUTPUT_DIR / "core_data.json"` (L72) |
| **CLI (argparse)** | `--chapter` / `-c`, `--range` / `-r`, `--limit` / `-l`, `--dry-run` / `-n`, `--overwrite`, `--reasoning` (low/medium/high), `--max-concurrency` / `-j`, `--assemble` / `-a` |
| **Reads** | `output/cleaned/chapters/ch_*.json`, `output/analysis/registers/register_analysis.json`, `output/analysis/v4/v4_data.json`, `output/analysis/v4/v4_paragraphs.json` |
| **Writes** | `output/core/chapters/ch_NNN.json`, `output/core/restored_core.md`, `output/core/core_data.json` |
| **LLM** | GPT-5.2 via OpenAI (structured output with Pydantic `ChapterExtraction` → `ParagraphExtraction`) |
| **⚠ Notes** | Duplicates marker dicts from `register_analysis.py` inline. Supports `ThreadPoolExecutor` parallel mode. |

---

### 5. `clean_page_breaks.py` — ~130 lines

| Item | Detail |
|------|--------|
| **Path constants** | `CORE_DIR = Path("output/core/chapters")` (L14) |
| **CLI** | None |
| **Reads** | `output/core/chapters/ch_*.json` |
| **Writes** | Same files **in-place** (modifies `core_text` field) |
| **LLM** | None |
| **⚠ RELATIVE PATH** | Uses `Path("output/core/chapters")` — does NOT use `PROJECT_ROOT`. Must be run from repo root. |

---

### 6. `stage_5_restore.py` — 1837 lines

| Item | Detail |
|------|--------|
| **Path constants** | `PROJECT_ROOT = Path(__file__).resolve().parent.parent` (L37) |
| | `SECRETS_PATH = PROJECT_ROOT / "secrets" / "azure_openai.env"` (L38) |
| | `CORE_CHAPTERS_DIR = PROJECT_ROOT / "output" / "core" / "chapters"` (L39) |
| | `OUTPUT_DIR = PROJECT_ROOT / "output" / "correspondential"` (L40) |
| | `CHAPTERS_OUT_DIR = OUTPUT_DIR / "chapters"` (L41) |
| | `ASSEMBLED_FILE = OUTPUT_DIR / "restored_kephalaia.md"` (L42) |
| **CLI (argparse)** | `--chapter` / `-c`, `--range` / `-r`, `--limit` / `-l`, `--dry-run` / `-n`, `--overwrite`, `--assemble` / `-a`, `--concurrency` / `-j`, `--debug` |
| **Reads** | `output/core/chapters/ch_*.json` |
| **Writes** | `output/correspondential/chapters/ch_NNN.json`, `output/correspondential/restored_kephalaia.md` |
| **LLM** | Claude Opus 4.6 via AnthropicFoundry (Azure AI Foundry). Two phases: (1) Spiritual Reading with streaming + adaptive thinking, (2) Tool-Call Restoration with `restore_lacuna` tool, multi-turn validation loop (up to 10 turns). |
| **⚠ Notes** | Uses `anthropic.Anthropic` with custom `AnthropicFoundry` subclass for Azure AI Foundry. Supports `ThreadPoolExecutor` parallel mode. |

---

### 7. `reconstruct_substrate.py` — 1096 lines

| Item | Detail |
|------|--------|
| **Path constants** | `PROJECT_ROOT = Path(__file__).resolve().parent.parent` (L48) |
| | `SECRETS_PATH = PROJECT_ROOT / "secrets" / "azure_openai.env"` (L49) |
| | `CHAPTERS_DIR = PROJECT_ROOT / "output" / "cleaned" / "chapters"` (L50) |
| | `OUTPUT_DIR = PROJECT_ROOT / "output" / "substrate"` (L51) |
| | `SEGMENTS_DIR = OUTPUT_DIR / "segments"` (L52) |
| | `ASSEMBLED_FILE = OUTPUT_DIR / "restored_substrate.md"` (L53) |
| | `DATA_FILE = OUTPUT_DIR / "substrate_data.json"` (L54) |
| **CLI (argparse)** | `--chapter` / `-c`, `--range` / `-r`, `--limit` / `-l`, `--dry-run` / `-n`, `--overwrite`, `--assemble` / `-a` |
| **Reads** | `output/cleaned/chapters/ch_*.json` |
| **Writes** | `output/substrate/segments/ch_NNN.json`, `output/substrate/restored_substrate.md`, `output/substrate/substrate_data.json` |
| **LLM** | GPT-5.2 via OpenAI (structured output with Pydantic `ChapterExtraction` → `SubstrateSegment`) |
| **⚠ Notes** | Defines extensive `NarrativeEpisode` enum (55 values), `EPISODE_ORDER`, `SECTION_STRUCTURE`, `EPISODE_NAMES` constants. Sequential processing only (no concurrency). |

---

### 8. `generate_layer1_pdf.py` — 385 lines

| Item | Detail |
|------|--------|
| **Path constants** | `SCRIPT_DIR = Path(__file__).parent` (L33) |
| | `PROJECT_ROOT = SCRIPT_DIR.parent` (L34) |
| | `SOURCE = PROJECT_ROOT / "output" / "Kephalaia_Layer_1_Extract.md"` (L35) |
| | `OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "Kephalaia_Layer_1_Extract.pdf"` (L36) |
| **CLI** | None |
| **Reads** | `output/Kephalaia_Layer_1_Extract.md` |
| **Writes** | `output/pdfs/Kephalaia_Layer_1_Extract.pdf` |
| **LLM** | None |
| **Deps** | `reportlab` |

---

### 9. `generate_reading_pdf.py` — 476 lines

| Item | Detail |
|------|--------|
| **Path constants** | `SCRIPT_DIR = Path(__file__).parent` (L31) |
| | `PROJECT_ROOT = SCRIPT_DIR.parent` (L32) |
| | `SOURCE = PROJECT_ROOT / "output" / "texts" / "Kephalaia_of_the_Teacher.md"` (L33) |
| | `OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "Kephalaia_Reading_Edition.pdf"` (L34) |
| **CLI** | None |
| **Reads** | `output/texts/Kephalaia_of_the_Teacher.md` |
| **Writes** | `output/pdfs/Kephalaia_Reading_Edition.pdf` |
| **LLM** | None |
| **Deps** | `reportlab` |

---

### 10. `kephalaia_layer_analysis.py` — 1017 lines

| Item | Detail |
|------|--------|
| **Path constants** | (in `main()`, L949-952) |
| | `project_root = Path(__file__).parent.parent` |
| | `text_path = project_root / "output" / "texts" / "Kephalaia_of_the_Teacher.md"` |
| | `output_dir = project_root / "output" / "analysis"` |
| **CLI** | None |
| **Reads** | `output/texts/Kephalaia_of_the_Teacher.md` |
| **Writes** | `output/analysis/kephalaia_layer_analysis.json`, `output/analysis/kephalaia_layer_analysis_report.md`, `output/analysis/01_..06_*.png` (6 PNGs) |
| **LLM** | None |
| **Deps** | `sklearn`, `scipy`, `matplotlib`, `numpy` |
| **⚠ Notes** | Paths defined as locals in `main()`, not module-level constants. `LAYER1_VOCAB`, `LAYER2_VOCAB`, `LAYER2_SINGLE`, `LAYER3_VOCAB` are the v1 vocabulary system. `MANUAL_LAYER1` chapter set hardcoded. |

---

### 11. `kephalaia_core_recovery.py` — 1459 lines

| Item | Detail |
|------|--------|
| **Path constants** | `KEPHALAIA_PATH = Path("output/texts/Kephalaia_of_the_Teacher.md")` (L48) |
| | `OUTPUT_DIR = Path("output/analysis")` (L53) |
| **CLI** | None |
| **Reads** | `output/texts/Kephalaia_of_the_Teacher.md` |
| **Writes** | `output/analysis/v2_report.md`, `output/analysis/v2_data.json`, `output/analysis/v2_01..06_*.png` (6 PNGs) |
| **LLM** | None |
| **Deps** | `sklearn`, `scipy`, `matplotlib`, `numpy` |
| **⚠ RELATIVE PATHS** | Uses `Path("output/...")` — does NOT use `PROJECT_ROOT`. Must be run from repo root. `MANUAL_LAYER1` chapter set duplicated. `MIN_WORDS_FOR_CLUSTERING` constant. |

---

### 12. `kephalaia_paragraph_recovery.py` — 1318 lines

| Item | Detail |
|------|--------|
| **Path constants** | `SCRIPT_DIR = Path(__file__).parent` (L39) |
| | `PROJECT_ROOT = SCRIPT_DIR.parent` (L40) |
| | `SOURCE_PATH = PROJECT_ROOT / "output" / "texts" / "Kephalaia_of_the_Teacher.md"` (L41) |
| | `OUTPUT_DIR = PROJECT_ROOT / "output" / "analysis" / "v3"` (L42) |
| **CLI** | None |
| **Reads** | `output/texts/Kephalaia_of_the_Teacher.md` |
| **Writes** | `output/analysis/v3/v3_report.md`, `output/analysis/v3/v3_reconstruction.md`, `output/analysis/v3/v3_paragraphs.json`, `output/analysis/v3/v3_01..08_*.png` (8 PNGs) |
| **LLM** | None |
| **Deps** | `sklearn`, `scipy`, `matplotlib`, `numpy` |
| **⚠ Notes** | Own VOCAB dict and WEIGHTS, different from v4. Own line classifier state machine, paragraph extractor, tier system (5 tiers). |

---

### 13. `kephalaia_layer_analysis_v4.py` — 1528 lines

| Item | Detail |
|------|--------|
| **Path constants** | `SCRIPT_DIR = Path(__file__).parent` (L81) |
| | `PROJECT_ROOT = SCRIPT_DIR.parent` (L82) |
| | `CHAPTERS_DIR = PROJECT_ROOT / "output" / "cleaned" / "chapters"` (L83) |
| | `OUTPUT_DIR = PROJECT_ROOT / "output" / "analysis" / "v4"` (L84) |
| **CLI** | None |
| **Reads** | `output/cleaned/chapters/ch_*.json` |
| **Writes** | `output/analysis/v4/v4_data.json`, `output/analysis/v4/v4_paragraphs.json`, `output/analysis/v4/v4_report.md`, `output/analysis/v4/v4_01..07_*.png` (7 PNGs) |
| **LLM** | None |
| **Deps** | `sklearn`, `scipy`, `matplotlib`, `numpy` |
| **⚠ Notes** | `MANUAL_LAYER1` chapter set duplicated. Most complete vocabulary system (7 categories in `VOCAB` dict with temporal `WEIGHTS`). `VOCAB` and `WEIGHTS` are the canonical versions — used by `stage_4_extract.py` at runtime via `V4_DATA_JSON`. |

---

## Cross-Cutting Issues for Refactoring

### 1. Path Convention Inconsistencies

| Script | Pattern | Problem |
|--------|---------|---------|
| `clean_page_breaks.py` | `Path("output/core/chapters")` | **Relative path** — breaks if not run from repo root |
| `kephalaia_core_recovery.py` | `Path("output/texts/...")`, `Path("output/analysis")` | **Relative paths** — same issue |
| `kephalaia_layer_analysis.py` | Paths in `main()` locals, not module-level | Inconsistent with all other scripts |
| All others | `PROJECT_ROOT = Path(__file__).resolve().parent.parent` | ✅ Correct pattern |

**Recommendation**: Standardise all scripts to the `PROJECT_ROOT` pattern.

### 2. Duplicated Vocabulary Dictionaries

| Canonical Location | Duplicated In | Notes |
|-------------------|---------------|-------|
| `register_analysis.py` | `stage_4_extract.py` (inline copy) | 5 marker dicts: FRAME, PASTORAL, CHRISTIAN, APPLICATION, TEACHING |
| `kephalaia_layer_analysis_v4.py` | `kephalaia_paragraph_recovery.py` (older version) | `VOCAB` dict and `WEIGHTS` — v3 has fewer categories |
| — | `kephalaia_layer_analysis.py` | Oldest vocabulary system (`LAYER1_VOCAB`, `LAYER2_VOCAB`, etc.) — superseded by v4 |
| — | `kephalaia_core_recovery.py` | Another vocabulary variant (`VOCAB_CATEGORIES`, `SINGLE_WORD_MARKERS`) |

**Recommendation**: Extract canonical vocabulary into a shared module (e.g., `scripts/vocab.py` or `shared/vocab.py`).

### 3. `MANUAL_LAYER1` Chapter Set

Hardcoded in three scripts with identical values:
- `kephalaia_layer_analysis.py` (L in `main()`)
- `kephalaia_core_recovery.py` (module-level)
- `kephalaia_layer_analysis_v4.py` (L86)

**Recommendation**: Extract to shared config.

### 4. CLI Standardisation

| Pattern | Scripts |
|---------|---------|
| **Full argparse** with `--chapter`, `--range`, `--dry-run`, `--overwrite`, `--assemble`, `--limit` | `stage_4_extract.py`, `stage_5_restore.py`, `reconstruct_substrate.py` |
| **Partial argparse** | `stage_1_clean.py` (similar but with `--list`, `--assemble-only`), `register_analysis.py` (`--chapter`, `--report`, `--save`) |
| **sys.argv** | `stage_0_ingest.py` |
| **No CLI** | `clean_page_breaks.py`, `generate_layer1_pdf.py`, `generate_reading_pdf.py`, all analysis scripts (v1, v2, v3, v4) |

**Recommendation**: Standardise around the `--chapter / --range / --dry-run / --overwrite / --assemble / --limit` pattern.

### 5. Secrets / LLM Client Setup

| LLM | Scripts | Client Pattern |
|-----|---------|----------------|
| GPT-5.2 (Azure) | `stage_1_clean.py`, `stage_4_extract.py`, `reconstruct_substrate.py` | `dotenv_values(SECRETS_PATH)` → `OpenAI(base_url=..., api_key=...)` |
| Claude Opus 4.6 (Azure AI Foundry) | `stage_5_restore.py` | Custom `AnthropicFoundry` subclass of `anthropic.Anthropic` + `httpx` |

**Recommendation**: Extract LLM client creation into a shared utility.

### 6. Pipeline Dependency Chain

```
stage_0_ingest.py
  └→ output/texts/*.md
       ├→ stage_1_clean.py → output/cleaned/chapters/ch_*.json
       │    ├→ register_analysis.py → output/analysis/registers/*.json
       │    ├→ kephalaia_layer_analysis_v4.py → output/analysis/v4/*.json
       │    │    └→ stage_4_extract.py → output/core/chapters/ch_*.json
       │    │         ├→ clean_page_breaks.py (in-place)
       │    │         ├→ stage_5_restore.py → output/correspondential/
       │    │         └→ (stage_4_extract.py also reads v4 data)
       │    └→ reconstruct_substrate.py → output/substrate/
       ├→ kephalaia_layer_analysis.py → output/analysis/ (v1, superseded)
       ├→ kephalaia_core_recovery.py → output/analysis/v2/ (superseded)
       ├→ kephalaia_paragraph_recovery.py → output/analysis/v3/ (superseded)
       ├→ generate_reading_pdf.py → output/pdfs/
       └→ generate_layer1_pdf.py (reads output/Kephalaia_Layer_1_Extract.md)
```

### 7. Likely Obsolete Scripts

| Script | Version | Superseded By | Evidence |
|--------|---------|---------------|----------|
| `kephalaia_layer_analysis.py` | v1 | `kephalaia_layer_analysis_v4.py` | Older vocabulary system, fewer categories |
| `kephalaia_core_recovery.py` | v2 | `kephalaia_layer_analysis_v4.py` + `stage_4_extract.py` | Uses raw text instead of cleaned JSON |
| `kephalaia_paragraph_recovery.py` | v3 | `kephalaia_layer_analysis_v4.py` | Fewer vocab categories, reads raw text |

All three read from `output/texts/Kephalaia_of_the_Teacher.md` (raw OCR markdown) rather than from `output/cleaned/chapters/ch_*.json` (LLM-cleaned structured JSON). The v4 script and `stage_4_extract.py` use the cleaned data.
