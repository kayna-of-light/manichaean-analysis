# Manichaean Analysis — Correspondential Reading Project

Reading the Manichaean texts through the correspondential lens — the same methodology applied to the [Nag Hammadi Library](https://github.com/kayna-of-light/NagHammadiLibrary).

## Companion Repositories

This project is part of a multi-repository research framework:

| Repository | Purpose |
|---|---|
| **[literary-compilation](https://github.com/kayna-of-light/literary-compilation)** | The Divine Bricolage — research collection and synthesis across multiple channels, documenting what the data shows and how it connects |
| **[structured-data-analysis](https://github.com/kayna-of-light/structured-data-analysis)** | Empirical data analysis — NDE phenomenology, past-life memory, MallWorld dream data |
| **[nag-hammadi-analysis](https://github.com/kayna-of-light/NagHammadiLibrary)** | Correspondential reading of the complete Nag Hammadi Library |
| **[proto-luke-reconstruction](https://github.com/kayna-of-light/ProtoLuke)** | Proto-Luke reconstruction — the Jamesian Protograph |

## Why Manichaeism?

Mani (216–274 CE) explicitly synthesized Zoroaster, Buddha, and Jesus — claiming to complete their "partial truths" in a universal religion. The Manichaean tradition is the **only historical religion to have been officially adopted by the Uyghur Khaganate** (762/763 CE), placing its scriptures physically in the cave libraries of "Great Tartary" — the Turfan/Turpan region that Swedenborg described as preserving the Ancient Word.

The Manichaean Psalm Book — a liturgical collection including the Psalms of Thomas — converges with Swedenborg's *Spiritual Diary* Entry 6077, where spirits from "Lesser Tartary" possess a "Divine Book" identified as "the Psalms of David." The German Turfan expeditions (1902–1914) recovered thousands of Manichaean manuscript fragments from exactly these caves.

This is not coincidence. This is the natural degree expressing the spiritual degree. The correspondential lens is applied because it organizes the data better than alternatives.

---

## The Problem: What the Kephalaia Actually Is

The *Kephalaia of the Teacher* (Coptic, 4th century) is not a unitary composition. It is a **composite text** — an editorial compilation assembled by Mani's community from multiple temporal layers:

1. **The Substrate**: The oldest layer — systematic cosmological-correspondential teaching that predates Mani's compilation. This is Persian correspondential knowledge: five-fold degree maps, body-cosmos systems, metal-realm mappings, zoomorphic forms. Both sides of every mapping stay within the cosmic system. This is the teaching of the Ancient Word in its natural-plane vocabulary.

2. **The Frame**: Hagiographic editorial apparatus added by the compiling community — "Once again the disciples questioned the enlightener", closing praise formulas, biographical claims about Mani. This material gives the text its literary shape but is not part of the teaching itself.

3. **The Pastoral Layer**: Church institutional material — fasting rules, alms, catechumen instruction, moral exhortation without cosmological grounding. This layer reflects the needs of a functioning religious community, not the original teaching.

4. **The Christian Overlay**: Explicit NT citations, Pauline vocabulary in devotional contexts, Christian titles grafted onto cosmic beings. Added as the community expanded into Christian cultural contexts.

The text is further damaged by **physical lacunae** — gaps in the papyrus where words, phrases, or entire passages are lost. Gardner's translation marks these with `[ ... ]` brackets of varying length.

The pipeline exists to **reverse the editorial process**: identify and separate the temporal layers, recover the oldest teaching substrate, fill the physical lacunae using correspondential logic, and then verify the result at corpus scale.

---

## The Pipeline

The pipeline has nine stages (0–8). Each stage is a separate script. The output of each stage feeds the next. All scripts operate on JSON chapter files within a project directory structure managed by `project_config.py`.

```
                                  ┌──────────────────────────────┐
                                  │  data/*.pdf.json             │
                                  │  (Azure OCR output)          │
                                  └───────────┬──────────────────┘
                                              │
                                   stage_0_ingest.py
                                              │
                                  ┌───────────▼──────────────────┐
                                  │  output/texts/*.md           │
                                  │  (raw markdown)              │
                                  └───────────┬──────────────────┘
                                              │
                                  projects/<name>/stage_1_clean.py
                                              │
                    ┌─────────────────────────▼────────────────────────────┐
                    │  output/projects/<name>/cleaned/chapters/ch_NNN.json │
                    │  (clean teaching text + apparatus, per chapter)       │
                    └───────────┬──────────────────────────────────────────┘
                                │
                     stage_2_discover.py ──────────────────────────┐
                                │                                  │
                    ┌───────────▼──────────────────┐   ┌───────────▼───────────┐
                    │  corpus_metadata.json         │   │  (same cleaned input) │
                    │  (vocabulary, patterns)        │   │                       │
                    └───────────┬───────────────────┘   └───────┬───────────────┘
                                │ drives scoring                │
                                └──────────┬────────────────────┘
                                           │
                                stage_3_score.py
                                           │
                    ┌──────────────────────▼────────────────────────────────┐
                    │  output/projects/<name>/analysis/chapters/ch_NNN.json │
                    │  (paragraph-level scores + editorial seam flags)      │
                    └───────────┬───────────────────────────────────────────┘
                                │
                          stage_4_extract.py
                                           │
                    ┌──────────────────────▼────────────────────────────────┐
                    │  output/projects/<name>/core/chapters/ch_NNN.json     │
                    │  (classified paragraphs: CORE/FRAME/PASTORAL/OVERLAY) │
                    └───────────┬───────────────────────────────────────────┘
                                │
                     stage_5_restore.py
                                │
                    ┌───────────▼──────────────────────────────────────────────┐
                    │  output/projects/<name>/restored/chapters/       │
                    │  ch_NNN.json (spiritual reading + gap fills +             │
                    │               reconstructed text per paragraph)           │
                    └───────────┬──────────────────────────────────────────────┘
                                │
                        stage_6_review.py
                                │
                    ┌───────────▼──────────────────┐
                    │  corpus_review.json           │
                    │  (mistranslations,             │
                    │   inconsistencies,             │
                    │   missed layers, etc.)         │
                    └───────────┬───────────────────┘
                                │
                         stage_7_correct.py
                                │
                    ┌───────────▼──────────────────────────────────────────────┐
                    │  output/projects/<name>/corrected/chapters/ch_NNN.json   │
                    │  (final corrected reconstructions + spiritual readings)   │
                    └──────────────────────────────────────────────────────────┘
```

### Directory Layout

```
output/
├── texts/                              # Stage 0: OCR → markdown (shared)
└── projects/
    └── kephalaia/
        ├── cleaned/chapters/           # Stage 1: LLM clean (per chapter JSON)
        ├── corpus_metadata.json        # Stage 2: corpus-wide metadata
        ├── core/chapters/              # Stage 4: core extraction (per chapter JSON)
        ├── restored/chapters/          # Stage 5: restoration + spiritual reading
        ├── corpus_review.json          # Stage 6: corpus-wide review findings
        ├── corrected/chapters/         # Stage 7: corrected final output
        └── analysis/                   # Stage 3: text-critical analysis outputs
```

---

### Stage 0: OCR Ingest (`stage_0_ingest.py`)

**Input**: Azure AI Document Intelligence JSON output (`data/*.pdf.json`)
**Output**: Raw markdown text (`output/texts/*.md`)

Converts OCR output into readable markdown. This is mechanical — no LLM involved, just structural cleanup of the machine-read text.

```bash
python scripts/stage_0_ingest.py
```

### Stage 1: Cleaning (`projects/<name>/stage_1_clean.py`)

**Input**: Raw markdown text
**Output**: `cleaned/chapters/ch_NNN.json` — one JSON per chapter

Each book has its own clean script because every text has different editorial conventions. For the Kephalaia, this sends each chapter to GPT-5.2 to separate the teaching text from Gardner's scholarly apparatus (footnotes, commentary, cross-references). The LLM handles what regex cannot: understanding which text is Mani's teaching and which is Gardner's editorial contribution.

Each cleaned chapter JSON contains:

| Field | Content |
|---|---|
| `chapter_number` | Manuscript chapter number |
| `title` | Chapter title from the manuscript |
| `teaching_text` | The full translated text, cleaned of apparatus |
| `gardner_synopsis` | Gardner's editorial synopsis (preserved separately) |
| `footnotes` | Extracted footnotes |
| `editorial_notes` | What was removed and why |
| `manuscript_pages` | Page range in the manuscript |

**Critical**: The `teaching_text` is the *complete* translated text — all temporal layers (substrate, frame, pastoral, overlay) are present. Nothing has been classified or removed at this stage. Physical lacunae remain as they appear in Gardner's translation (`[ ... ]`).

```bash
cd scripts && python projects/kephalaia/stage_1_clean.py
```

### Stage 2: Metadata Discovery (`stage_2_discover.py`)

**Input**: All 123 cleaned chapter JSONs (the raw `teaching_text` from Stage 1)
**Output**: `corpus_metadata.json`

**Model**: Claude Opus 4.6 (single-turn, full corpus in context)

This is the critical bridge between the raw text and automated extraction. The entire cleaned corpus (~136K tokens, 1522 paragraphs) is fed to Claude in a single prompt. The model reads the complete text holistically as a text-critical expert and produces structured metadata that drives the extraction pipeline:

| Output Category | Purpose |
|---|---|
| **Vocabulary taxonomies** | Diagnostic terms per temporal layer (substrate, frame, pastoral, overlay) with strength weights (1–5) and exclusivity flags |
| **Diagnostic patterns** | Multi-word formulas that signal layer transitions — frame openers, closing praise, citation formulas, editorial bridges, application pivots |
| **Structural templates** | The recurring teaching architectures — five-fold maps, three-fold structures, body-cosmos correspondences, metal-realm mappings |
| **Correspondential registers** | Categories of natural objects used as correspondence-vehicles (metals, body parts, zoomorphic forms, sensory qualities) |
| **Chapter profiles** | Per-chapter layer assessment — dominant layer, estimated substrate percentage, templates present |
| **Cross-chapter teachings** | Teachings that span or repeat across chapters (what extends, repeats, contradicts) |
| **Editorial patterns** | Seam types, fatigue patterns, citation formulas — where and how the editor intervened |

**Why this stage exists**: The previous extraction pipeline used hardcoded word lists (manually curated marker dictionaries). These lists were incomplete, biased by the author's prior readings, and blind to patterns that only a text-critical expert reading the full corpus can see. By having Claude derive the vocabulary and patterns from the raw text, the extraction in Stage 4 is guided by observation rather than assumption.

**Why it must read the cleaned data**: This script was initially written to read from the *core extraction output* (Stage 4 output). That was a circular dependency — the metadata meant to drive extraction was derived from already-extracted data. The script now correctly reads from Stage 1 output, ensuring the metadata reflects the raw text before any classification.

```bash
cd scripts && python stage_2_discover.py --project kephalaia [--dry-run] [--debug]
```

### Stage 3: Text-Critical Scoring (`stage_3_score.py`)

**Input**: Cleaned chapter JSONs + `corpus_metadata.json`
**Output**: `analysis/chapters/ch_NNN.json` — per-paragraph scoring and seam detection

**Model**: None (pure computational NLP, no LLM calls)

This stage runs the text-critical machinery locally — no API calls needed:

1. **Register scoring**: Using the diagnostic vocabularies from `corpus_metadata.json`, each paragraph is scored for affinity with each temporal layer (core, frame, pastoral, overlay, etc.).

2. **Editorial seam detection**: Bridge connectives, institutional vocabulary, and register shifts between adjacent paragraphs are flagged as potential editorial joins.

The output is consumed by `stage_4_extract.py`, which formats the analysis into the Claude prompt.

```bash
cd scripts && python stage_3_score.py --project kephalaia [--chapter 42] [--dry-run]
```

### Stage 4: Core Extraction (`stage_4_extract.py`)

**Input**: Cleaned chapter JSONs + `analysis/chapters/ch_NNN.json` + `corpus_metadata.json`
**Output**: `core/chapters/ch_NNN.json` — classified and extracted per chapter

**Model**: Claude Opus 4.6 (per-chapter, with pre-computed register scoring as context)

This is the textual-critical heart of the pipeline. For each chapter:

1. **Load analysis**: Pre-computed vocabulary scores and seam flags from `stage_3_score.py` are loaded and formatted into the prompt, giving Claude quantitative guidance — not dictation.

2. **LLM classification**: The chapter is sent to Claude with the register scores. The model classifies each paragraph:
   - **CORE**: Teaching content that predates the editorial compilation. Correspondential maps, cosmological narrative, body-universe systems, five-fold structures, named cosmic beings *and their correspondential descriptions*. The criterion is temporal (old teaching), not thematic.
   - **FRAME**: Hagiographic editorial apparatus — Q&A formulas, closing praise, biographical claims about Mani.
   - **PASTORAL**: Church institutional material — fasting, alms, catechumen instruction, behavioral ethics without cosmological mechanism.
   - **OVERLAY**: Explicit NT/Christian additions — Gospel citations, Pauline vocabulary in devotional contexts.
   - **MIXED**: Paragraphs where core and later material are interwoven. For these, the LLM extracts the core teaching and records what was removed.

3. **Output**: Each chapter JSON preserves the full classification with core_text, layer assignment, removal notes, and the scoring context.

**What "core" means**: The distinction is temporal, not thematic. A passage about cosmic beings *and its Q&A framing* can be split: the cosmological content is CORE (old teaching), the Q&A formula is FRAME (editorial apparatus). A passage about charity with no cosmological mechanism is PASTORAL regardless of how "spiritual" it sounds. The criterion is: does this belong to the teaching substrate that existed before the editorial compilation?

**What introductory questions are**: The core Persian text often started with cosmological questions — these are substantive framing that sets up the teaching, not mere editorial apparatus. Questions like "Tell us about the five realms" are CORE because they reflect the pedagogical structure of the original teaching. Questions like "We beseech you, our master, enlightener" are FRAME because they reflect the compiling community's hagiographic conventions.

```bash
cd scripts && python stage_4_extract.py --project kephalaia [--chapter 42] [--dry-run]
cd scripts && python stage_4_extract.py --project kephalaia --assemble  # assembly only
```

### Stage 5: Restoration (`stage_5_restore.py`)

**Input**: `core/chapters/ch_NNN.json` (extracted core text with lacunae)
**Output**: `restored/chapters/ch_NNN.json`

**Model**: Claude Opus 4.6 (per-chapter, two-pass)

The name "correspondential reading" is somewhat misleading — the *primary* goal of this stage is **lacuna restoration**. The spiritual reading is a means, not the end.

The Kephalaia manuscripts are physically damaged. Gardner's translation preserves these gaps as `[ ... ]` markers of varying length.  Standard papyrological practice fills gaps based on paleographic spacing and parallel texts. This pipeline fills gaps based on **correspondential logic** — what the spiritual sense *requires* at each position.

The process has two passes per chapter:

**Pass A — Spiritual Reading**: Claude translates the entire chapter from its natural sense into its spiritual sense through Swedenborg's doctrine of correspondences. Every natural image (light, darkness, fire, water, garments, metals, body parts, animals, mountains, seeds, vessels) is replaced by the spiritual reality it expresses. Gap positions are preserved as anchor markers (`[GAP-N]`) in the spiritual prose, showing what spiritual reality belongs at each lacuna.

**Pass B — Tool-Call Restoration**: A multi-turn conversation where Claude uses a `restore_lacuna` tool for each gap. For every lacuna:
1. The model finds the `GAP-N` anchor in the spiritual reading to determine what spiritual reality belongs there
2. It translates that spiritual reality *back* into the text's own natural-plane vocabulary — the language of the Kephalaia
3. It submits the fill via tool call, with explanation and confidence rating
4. Each fill is individually validated (correct gap ID, non-empty, matches size constraints)

The output for each chapter includes:
- **`spiritual_reading`**: The complete correspondential translation (interpretive layer)
- **`fills`**: Individual gap-fill decisions with explanations
- **`reconstructions`**: The reconstructed core text — lacunae filled, readable prose

**Why correspondences work for restoration**: A standard papyrological fill is constrained by spacing and parallel passages. A correspondential fill is constrained by the *teaching system itself* — if the text maps five realms to five metals, and the fourth metal is in a lacuna, the correspondential system dictates what it must be. The fill is not a guess; it is the only value consistent with the systematic structure.

**Lacuna types**:

| Marker | Size | Constraint |
|---|---|---|
| `{GAP-N}` | Exactly one word | Must be a single word |
| `[GAP-N: ...]` | Small (words to phrase) | Short fill |
| `[GAP-N: ... ...]` | Medium (clause/sentence) | Moderate fill |
| `[GAP-N: ... ... ...]` | Large (multiple sentences) | Extended fill |
| `[GAP-N: REVIEW word]` | Editorial review | Editor's guess — confirm or improve through correspondential lens |

```bash
cd scripts && python stage_5_restore.py --project kephalaia [--chapter 42]
cd scripts && python stage_5_restore.py --project kephalaia --assemble  # assembly only
```

### Stage 6: Corpus Review (`stage_6_review.py`)

**Input**: All core + correspondential chapter JSONs (interleaved as continuous flow)
**Output**: `corpus_review.json`

**Model**: Claude Opus 4.6 (single-turn, full corpus in context)

Per-chapter processing is blind to cross-chapter patterns. A correspondence read one way in chapter 38 might be read differently in chapter 65 without justification. A teaching sequence split across two chapters might have been interrupted by an editorial boundary. A pre-Manichaean layer visible only from the full narrative might have been missed at chapter level.

This stage feeds the *entire* corpus — core text interleaved with spiritual readings — to Claude in a single prompt (~200K tokens). The model reads the complete reconstructed text holistically and identifies:

| Finding Type | What It Catches |
|---|---|
| **Mistranslation** | A spiritual reading got the correspondence wrong — wrong spiritual reality mapped |
| **Inconsistency** | The same natural image read differently in different chapters without justification |
| **Missed pre-Manichaean layer** | Manichaean editorial vocabulary treated as original when it glosses over older teaching |
| **Untranslated natural** | Natural-plane vocabulary left in the spiritual reading without correspondential translation |
| **Opposite sense error** | Correspondence read in the wrong polarity (fire as divine love vs. self-love) |
| **Narrative break** | Teaching sequence interrupted by chapter boundary or editorial insertion |
| **Cross-passage pattern** | Theme or system visible only at corpus scale |
| **Deeper substrate** | Evidence of layers older than Persian (proto-Indo-Iranian, Mesopotamian) |

Each finding includes severity (critical/significant/minor), specific `§` references, the current reading, the proposed correction, and reasoning.

```bash
cd scripts && python stage_6_review.py --project kephalaia [--dry-run] [--debug]
```

### Stage 7: Apply Corrections (`stage_7_correct.py`)

**Input**: `corpus_review.json` + `restored/chapters/ch_NNN.json`
**Output**: `corrected/chapters/ch_NNN.json`

**Model**: Claude Opus 4.6 (per-chapter, for affected chapters only)

The final stage applies corpus-wide corrections to individual chapters. For each chapter that has applicable findings from the review:

1. The chapter's three data layers (reconstructions, fills, spiritual reading) are sent to Claude along with the applicable corrections
2. Claude rewrites all three layers to incorporate the fixes:
   - **Reconstructions** (primary): Corrected gap fills, harmonized terminology
   - **Fills**: Updated individual fill decisions where a fill introduced wrong terminology
   - **Spiritual reading** (secondary): Updated correspondential translation for consistency
3. No editorial notes, annotations, or bracketed explanations are added — the corrections are applied silently

Only "actionable" finding categories are applied: mistranslation, inconsistency, opposite_sense_error, untranslated_natural, missed_pre_manichaean. Cross-passage observations and narrative breaks inform understanding but don't modify text.

The corrected files are written to a separate `corrected/chapters/` directory, preserving the Stage 5 output untouched.

```bash
cd scripts && python stage_7_correct.py --project kephalaia [--chapter 42] [--dry-run]
```

---

## Stage 8: Composition and Assembly

After the seven-stage extraction/correction pipeline (Stages 0–7), composition operates on the final output:

### Structure Composition (`stage_8_compose.py`)

Reads the complete corrected corpus and determines the book’s *true* structure — the natural divisions, teaching sequences, and chapter groupings that the editorial compilation obscured. Outputs `book_structure.json`.

```bash
cd scripts && python stage_8_compose.py --project kephalaia [--dry-run]
```

### Assembly

Most pipeline scripts have an `--assemble` flag that produces a single reading-order markdown file from the chapter JSONs, suitable for human reading or PDF generation.

---

## Why This Architecture?

### Why not a single LLM pass?

The problem is **too complex for a single pass** and the text is **too large for a single context window** at the granularity needed.

- **Layer separation** (Stage 4) requires careful paragraph-level attention to vocabulary, syntax, and voice shifts. This needs the full paragraph in focus.
- **Lacuna restoration** (Stage 5) requires the spiritual sense as an intermediate representation — you cannot reliably fill gaps in a text you haven’t understood at the spiritual level.
- **Corpus-scale review** (Stage 6) requires the *entire* text in context, but operates at finding-level rather than paragraph-level.

A single pass cannot simultaneously attend to paragraph-level extraction AND corpus-level consistency. The pipeline separates these concerns.

### Why metadata-driven extraction?

The original extraction pipeline (GPT-5.2 based, now `extract_core_gpt52.py`) used hardcoded word lists — manually curated dictionaries of "frame markers", "pastoral markers", etc. This approach had three problems:

1. **Incomplete**: The lists missed terms that signal layers but weren't noticed by the human curator
2. **Biased**: The lists reflected the curator's existing reading, not the text's own signals
3. **Circular**: When the lists were derived from already-extracted data, they reinforced extraction errors

The metadata stage (Stage 2) eliminates all three problems by having Claude read the *raw* text as a text-critical expert and derive the vocabulary, patterns, and templates directly from observation.

### Why Claude Opus 4.6?

The original pipeline used GPT-5.2 for extraction (Stage 4). Analysis showed a **56.8% extraction rate with 16.3% loss** — GPT-5.2 over-stripped teaching content, especially cosmological narrative that it couldn't distinguish from editorial material. Claude's extended thinking, larger context window, and superior instruction-following produce significantly more accurate layer classification.

### Why does Stage 5 do both spiritual reading AND lacuna restoration?

The script was originally conceived as a spiritual-sense translation (the "reading" part). The lacuna restoration was added later when we realized the spiritual reading provides the *exact* constraint needed to fill gaps: if you know what spiritual reality a position expresses, you can translate that back into the text's vocabulary to fill the lacuna. The primary value turned out to be the restoration, not the reading — hence the name `stage_5_restore.py`.

---

## Project System

The pipeline is designed to process multiple books, each with its own configuration. Currently:

| Project | Book | Status |
|---|---|---|
| `kephalaia` | Kephalaia of the Teacher (123 chapters) | Core extraction + restoration complete |
| `shabuhragan` | Šābuhragān (11 sections) | Core extraction complete |

Each project is configured in `scripts/projects/<name>/config.yaml` and has its own clean script in `scripts/projects/<name>/stage_1_clean.py`.

```bash
# Process a specific project
python scripts/stage_4_extract.py --project kephalaia
python scripts/stage_4_extract.py --project shabuhragan
```

## Repository Structure

```
manichaean-analysis/
├── .github/
│   └── copilot-instructions.md     # Editorial instructions
├── data/                            # Source PDFs + OCR JSON
├── output/
│   ├── texts/                      # Stage 0: raw markdown
│   ├── kephalaia_pages/            # Coptic page images (JPEG, from PDF)
│   ├── kephalaia_coptic/           # Coptic transcription output (pass1, pass2, JSON)
│   └── projects/
│       ├── kephalaia/
│       │   ├── cleaned/chapters/   # Stage 1: cleaned JSONs
│       │   ├── corpus_metadata.json # Stage 2: text-critical metadata
│       │   ├── core/chapters/      # Stage 4: extracted core
│       │   ├── restored/    # Stage 5: restored + spiritual reading
│       │   ├── corpus_review.json  # Stage 6: review findings
│       │   ├── corrected/chapters/ # Stage 7: corrected output
│       │   └── analysis/           # Stage 3: text-critical analysis
│       └── shabuhragan/
│           └── ...
├── scripts/
│   ├── stage_0_ingest.py           # Stage 0: OCR → markdown
│   ├── stage_2_discover.py          # Stage 2: corpus metadata
│   ├── stage_3_score.py             # Stage 3: text-critical analysis (no LLM)
│   ├── stage_4_extract.py           # Stage 4: core extraction (Claude)
│   ├── extract_core_gpt52.py       # (legacy GPT-5.2 extraction, unused)
│   ├── stage_5_restore.py           # Stage 5: restoration + spiritual reading
│   ├── stage_6_review.py            # Stage 6: corpus-wide review
│   ├── stage_7_correct.py           # Stage 7: apply corrections
│   ├── stage_8_compose.py           # Stage 8: structural composition
│   ├── extract_kephalaia_pages.py  # Coptic page extraction (PDF → JPEG)
│   ├── transcribe_coptic.py        # Coptic transcription v1 (single-pass)
│   ├── transcribe_coptic_v2.py     # Coptic transcription v2 (two-pass pipeline)
│   ├── project_config.py           # Project configuration system
│   ├── projects/
│   │   ├── kephalaia/
│   │   │   ├── config.yaml
│   │   │   └── stage_1_clean.py     # Stage 1: Kephalaia-specific cleaning
│   │   └── shabuhragan/
│   │       ├── config.yaml
│   │       └── stage_1_clean.py
│   └── tools/
│       └── corpus_base.py          # Shared base class for corpus-level analysis
├── findings/                        # Correspondential findings (YAML)
├── docs/
│   └── COPTIC_TRANSCRIPTION.md     # Coptic pipeline technical documentation
├── cache/                           # Build cache
├── secrets/                         # API credentials (gitignored)
│   └── azure_openai.env            # Azure OpenAI + Anthropic credentials
└── environment.yml                  # Conda environment (manichaean)
```

## Setup

```bash
conda env create -f environment.yml
conda activate manichaean
```

### Credentials

Create `secrets/azure_openai.env`:
```env
# Azure OpenAI (GPT-5.2, used in Stage 1 cleaning)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-52

# Anthropic via Azure AI Foundry (Claude Opus 4.6, used in Stages 2–8)
ANTHROPIC_ENDPOINT=https://your-foundry-endpoint
ANTHROPIC_API_KEY=your-key
ANTHROPIC_DEPLOYMENT=claude-opus-4-6
```

## Scraping (gnosis.org texts)

In addition to the OCR pipeline for the Kephalaia/Šābuhragān, the repo includes a scraper for Manichaean texts on gnosis.org:

```bash
python scripts/scrape_gnosis.py
python scripts/scrape_gnosis.py --category parthian_hymns
python scripts/scrape_gnosis.py --list-categories
python scripts/scrape_gnosis.py --dry-run
```

---

## Coptic Transcription Pipeline

In addition to Gardner's English translation (which feeds the main analysis pipeline), the repo includes an end-to-end pipeline for transcribing the **original Coptic text** from the Polotsky/Böhlig 1940 critical edition PDF.

**Source**: `data/Kephalaia -- Mani...Stuttgart.pdf` (522 PDF pages, ~235 Coptic pages at odd indices 49-517)

### Why the Coptic

The English translation is a lossy projection. The Coptic preserves what English cannot show: morphological structure, Lycopolitan dialect forms, grammatical particles, prefix/suffix constructions, and the exact Greek loanwords that signal the teaching's transmission path. The Coptic is the evidence; the English is commentary on the evidence.

### Architecture: Two-Pass OCR

The pipeline uses Claude Opus 4.6 vision to transcribe printed Coptic, with a two-pass architecture that prevents confirmation bias while maximizing accuracy:

```
PDF page ──→ JPEG extraction ──→ Pass 1 (blind) ──→ Pass 2 (validated) ──→ final text
                                      │                     ▲
                                      │                     │
                                      │         English translation
                                      │         (auto-extracted from Gardner)
                                      │                     │
                                      └─────────────────────┘
```

**Pass 1 — Blind Extraction**: The page image is sent to Claude with full Coptic philological expertise (Lycopolitan dialect awareness, Unicode letter guidance, editorial mark preservation) but **no English translation**. This prevents the model from reading what it expects to see rather than what is actually printed.

**Pass 2 — English-Guided Validation**: The same page image is sent again along with the Pass 1 output and the corresponding English translation (auto-extracted from Gardner). The English serves as a "red thread" — it tells the model what each line *means*, so it can identify character-level errors in the Coptic. Where the English says "apostle," the model checks that ⲁⲡⲟⲥⲧⲟⲗⲟⲥ is spelled correctly. Where it says "flesh," it verifies ⲥⲁⲣⲝ has the right ⲝ. But the English is the guide, not the goal — Coptic morphology, dialect forms, and grammatical constructions that have no English equivalent are preserved exactly.

### Auto-English Extraction

Gardner's translation contains inline `(N)` page markers for all 235 Coptic pages (10-244). The pipeline automatically extracts the corresponding English section for each page using regex matching — no manual alignment needed. This means the pipeline can run at full scale with `--pages all`.

### Usage

```bash
# Activate the environment:
conda activate nhl

# Single page (extracts from PDF, auto-selects English):
python scripts/transcribe_coptic_v2.py --pages 12

# Page range:
python scripts/transcribe_coptic_v2.py --pages 10-20

# All 235 Coptic pages:
python scripts/transcribe_coptic_v2.py --pages all

# Resume interrupted batch (skips completed pages):
python scripts/transcribe_coptic_v2.py --pages all --skip-existing

# Reuse pass1 output (e.g. after prompt refinement):
python scripts/transcribe_coptic_v2.py --pages 12 --reuse-pass1

# From pre-extracted image (backward compat):
python scripts/transcribe_coptic_v2.py --image output/kephalaia_pages/keph_p012.jpg
```

### Output

Per page, the pipeline produces:

| File | Content |
|---|---|
| `keph_pNNN_pass1.txt` | Pass 1 blind extraction (Coptic Unicode text) |
| `keph_pNNN_pass2.txt` | Pass 2 corrected transcription (final result) |
| `keph_pNNN_twopass.json` | Combined JSON with both passes, metadata, English text, token counts |

All output goes to `output/kephalaia_coptic/`. Page images are cached in `output/kephalaia_pages/`.

### Performance

Per page: ~75s Pass 1 + ~45s Pass 2 = ~2 minutes total. Full corpus (~235 pages): ~8 hours.

Pass 2 typically corrects 30-40% of lines, fixing proper names (ⲁⲇⲁⲙ, ⲥⲏⲑⲏⲗ, ⲃⲟⲩⲇⲇⲁⲥ, ⲍⲁⲣⲁⲑⲟⲩⲥⲧⲣⲁ), Greek loanwords (ⲥⲁⲣⲝ, ⲁⲡⲟⲥⲧⲟⲗⲟⲥ, ⲥⲁⲧⲁⲛⲁⲥ), and visually ambiguous letterforms.

### Known Limitations

- **Lycopolitan letter**: The dialect-specific letter (resembling a numeral 6) is still rendered inconsistently across pages. The model has no stable Unicode target for it.
- **Supralinear strokes**: Combining overline (U+0305) placement is sometimes missed or inconsistent.
- **No ground truth**: Without a published digital Coptic text, accuracy can only be validated against the image + English translation.

See [docs/COPTIC_TRANSCRIPTION.md](docs/COPTIC_TRANSCRIPTION.md) for detailed technical documentation.

## Companion Repositories

| Repository | Purpose |
|---|---|
| [literary-compilation](https://github.com/kayna-of-light/literary-compilation) | The Divine Bricolage framework — knowledge graph, source documents |
| [structured-data-analysis](https://github.com/kayna-of-light/structured-data-analysis) | Empirical data analysis — NDE, past-life memory, MallWorld |
| [NagHammadiLibrary](https://github.com/kayna-of-light/NagHammadiLibrary) | NHL correspondential reading project |
| [ProtoLuke](https://github.com/kayna-of-light/ProtoLuke) | Proto-Luke reconstruction — the Jamesian Protograph |
