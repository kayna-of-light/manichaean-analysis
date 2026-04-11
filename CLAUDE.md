# Manichaean Analysis — Correspondential Reading Project

## Project Overview

This repository contains Manichaean texts scraped from the Gnostic Society Library (gnosis.org) and other sources, structured for systematic reading through the **correspondential lens** — the same methodology applied to the Nag Hammadi Library.

### Why Manichaeism Matters for This Framework

Mani (216–274 CE) is the critical bridge figure. Born into an Elcesaite (Jewish-Christian Gnostic) community in Babylonia, he explicitly synthesized Zoroaster, Buddha, and Jesus into a universal religion — claiming that each prophet brought partial truth and he was completing the synthesis. This is **not** syncretism (mixing traditions arbitrarily). It is the claim of a correspondential key: the same spiritual content expressed through different cultural vessels.

**Key connections to the framework:**

1. **The Uyghur Khaganate**: The only state to officially adopt Manichaeism (762/763 CE). The Uyghur Kingdom of Qocho preserved Manichaean texts in cave libraries at Turfan — in the heart of Swedenborg's "Great Tartary."

2. **The Manichaean Psalm Book**: A liturgical collection that converges with Swedenborg's *Spiritual Diary* Entry 6077 (spirits from "Lesser Tartary" with a "Divine Book" identified as "the Psalms of David"). The Manichaeans in Great Tartary literally possessed a Psalm Book.

3. **Psalms of Thomas**: Part of the Manichaean Psalm Book, connected to the same apostolic tradition as the Gospel of Thomas. Cyril of Jerusalem attributed the Gospel of Thomas directly to the Manichaeans.

4. **Mani's Five Shekhinas**: The Father of Greatness possesses five attributes — Reason, Mind, Intelligence, Thought, Understanding — which map to discrete degrees of reception.

5. **Constant State, Variable Form in Practice**: Manichaean deities were renamed in each cultural context (Zoroastrian yazatas in Persian, bodhisattvas in Chinese) — the framework's principle operating as actual religious practice.

6. **The Book of Giants**: Mani used the Enochic Book of Giants as scripture. Fragments found at both Qumran and Turfan — confirming the transmission chain from Enochic/Essene tradition through Manichaeism into Central Asia.

### Companion Repositories

| Repository | Purpose |
|---|---|
| **[literary-compilation](https://github.com/kayna-of-light/literary-compilation)** | The Divine Bricolage framework — research collection, synthesis, and source documents |
| **[structured-data-analysis](https://github.com/kayna-of-light/structured-data-analysis)** | Empirical data analysis — NDE, past-life memory, MallWorld |
| **[NagHammadiLibrary](https://github.com/kayna-of-light/NagHammadiLibrary)** | NHL correspondential reading project |
| **[ProtoLuke](https://github.com/kayna-of-light/ProtoLuke)** | Proto-Luke reconstruction — the Jamesian Protograph |

---

## The Correspondential Lens

### What Correspondence Is

Correspondence is the **organic relationship** between a natural object and the spiritual reality it expresses. It is grounded in the object's actual function, not in arbitrary assignment.

- **Light** corresponds to **wisdom/truth** — because light enables the eye to distinguish forms
- **Fire** corresponds to **love/will** — because fire is the active principle that gives light existence
- **Water** corresponds to **truth in the natural degree** — because water sustains natural life
- **Garments/Robes** correspond to **external truths** — because garments clothe the body as truths clothe spiritual meaning
- **Ships** correspond to **doctrinal vessels** — because ships carry cargo across water as doctrine carries truth through the natural degree
- **Mountains** correspond to **elevated spiritual states** — height indicates proximity to the source of influx
- **Seeds/Plants** correspond to **interior truths growing into form** — as a seed contains the whole tree

### What Correspondence Is NOT

| Category | Description | Why It Fails |
|---|---|---|
| **Allegory** | Arbitrary substitution (scales = justice) | Correspondences are grounded in function, not convention |
| **Jungian archetypes** | Spiritual realities as psychic projections | The texts describe objective spiritual realities |
| **Metaphor** | "A is like B" | Correspondence says "A is B at the natural degree" |
| **Symbol** | Conventional sign pointing to abstract concept | Correspondence is organic participation, not pointing |

### Directionality

Correspondence flows in one direction: **inside → outside**. The spiritual causes the natural; the natural is the spiritual in ultimates. This is divine influx — interior reality bringing forth exterior form.

### Opposite Sense

The same natural image can express positive or negative correspondence depending on context:

| Image | Positive | Negative |
|---|---|---|
| Fire | Divine love, celestial warmth | Self-love burning, destructive passion |
| Water | Living truth | Falsity (stagnant/poisoned water) |
| Darkness | Obscurity before illumination | Active falsity, denial of truth |
| Lion | Strength of good in the natural degree | Power of self-love devouring |

### Discrete Degrees

Reality stratifies into celestial (love/will), spiritual (wisdom/truth), and natural (effects/ultimates). These are **discrete levels**, not a continuum.

### The Proprium

The proprium is the sense of self as separate — self-love. It is **not evil in itself** — it is the vessel that must be formed before it can receive. But when it claims what flows through it as its own possession, it becomes the obstacle.

---

## Repository Structure

```
manichaean-analysis/
├── .github/
│   └── copilot-instructions.md     # This file
├── data/                            # Source PDF/data files
├── output/
│   ├── texts/                      # Scraped texts (markdown, one per text)
│   ├── cleaned/                    # Cleaned/edited versions
│   └── pdfs/                       # Generated PDFs
├── findings/
│   ├── schema.yaml                 # Schema definition & documentation
│   └── texts/                      # Per-text findings (YAML)
├── scripts/
│   ├── scrape_gnosis.py            # Scraper for gnosis.org Manichaean collection
│   └── mirror_to_drive.py          # Sync to Google Drive (future)
├── cache/                           # Build cache
├── secrets/                         # Credentials (gitignored)
├── temp/                            # Working files
└── environment.yml                  # Conda environment
```

---

## Text Categories

The Manichaean corpus on gnosis.org is organized into these categories:

| Category | Description | Count |
|---|---|---|
| **Psalms to Jesus** | Devotional psalms from the Coptic Manichaean Psalm-Book | ~10 |
| **Bema Psalms** | Festival psalms for the Bema (Mercy Seat) celebration | ~8 |
| **Separate Psalms** | Individual psalms not part of a numbered collection | ~3 |
| **Kephalia** | "Chapters" — didactic discourses attributed to Mani | ~1 |
| **Parthian Hymns** | Hymns and prayers in Parthian/Middle Persian tradition | ~20 |
| **Writings of Mani** | Texts and hymns attributed directly to Mani | ~7 |
| **Parables** | Narrative parables in the Manichaean tradition | ~5 |
| **Miscellaneous** | Psalms of Thomas, fragments, prayers, eschatological texts | ~9 |
| **Augustine (Secondary)** | Anti-Manichaean polemical writings by Augustine | ~8 |

---

## The Findings System

### Purpose

As texts are systematically read through the correspondential lens, findings are recorded in structured YAML files — one per text. This captures:

- **What was found** — the specific observation
- **Where it was found** — passage reference
- **What principle it evidences** — which part of the framework
- **How confident we are** — strong, moderate, or tentative
- **What it connects to** — other texts, NHL tractates, framework documents

### Finding Categories

| Category | Description |
|---|---|
| `correspondence` | A specific natural→spiritual mapping |
| `explicit_statement` | Text explicitly teaches correspondence/influx/degrees |
| `structural_principle` | Framework principle operating as structural element |
| `cosmological_mapping` | Manichaean cosmology → correspondential architecture |
| `cross_reference` | Connection to NHL, Swedenborg, Zoroastrian, or other tradition |
| `transmission_evidence` | Evidence for the Ancient Word transmission chain |
| `anomaly` | Resists or complicates correspondential reading |

### Framework Principles

| Principle | Description |
|---|---|
| `correspondence` | Natural→spiritual mapping (the basic unit) |
| `discrete_degrees` | Celestial/spiritual/natural stratification |
| `influx` | Divine truth/good flowing into natural forms |
| `constant_state_variable_form` | Same reality, different perceptual expressions |
| `opposite_sense` | Same symbol meaning good or evil by context |
| `regeneration` | The spiritual transformation process |
| `proprium` | Self-love claiming what it receives |
| `divine_human` | The Grand Man; body-correspondence system |
| `ancient_word` | Evidence for pre-literary correspondential knowledge |
| `ruling_love` | Core orientation determining everything else |
| `accommodation` | Truth delivered at different levels for different receivers |
| `light_captivity` | The Manichaean motif of light trapped in matter |
| `call_and_response` | The awakening call from the realm of light |

---

## Reading Principles

### DO

- Read the natural sense first, then identify correspondential objects, then read the spiritual sense
- Record both levels — natural and correspondential — as parallel
- Check for consistency across texts
- Report hits as hits — when the framework predicts and the text confirms, say so
- Report anomalies honestly
- Trace cross-textual patterns with NHL tractates and Zoroastrian sources
- Note where Manichaean cosmology maps onto vs. deviates from Swedenborgian architecture
- Pay attention to the **Psalms of Thomas** connection to the Gospel of Thomas

### DO NOT

- Substitute Jungian, Freudian, or generic "symbolic" interpretation
- Treat Manichaeism as identical to the NHL tradition — they are related but distinct
- Force the framework where it doesn't fit
- Hedge against confirmed observations to appear "balanced"
- Dismiss the cosmological elaborations without checking for correspondential content
- Assume Manichaean "dualism" is the same as Swedenborgian discrete degrees — investigate first

---

## Technical Operations

### Conda Environment

```bash
conda env create -f environment.yml
conda activate manichaean
```

### Scraping

```bash
python scripts/scrape_gnosis.py
```

---

## Standing Rules

- **No git commits** — the user manages git operations directly
- **Honesty above all** — report what the data shows
- **Correspondences are ontological, not symbolic** — A IS B at the natural degree
- **The direction is inside→outside** — influx flows from spiritual to natural
- **Proprium ≠ evil** — it is the vessel; it becomes obstacle only when it claims ownership
- **Discrete degrees, not a continuum** — celestial, spiritual, natural are complete levels
- **Manichaean dualism ≠ Swedenborgian dualism** — investigate the relationship carefully
