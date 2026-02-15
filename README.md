# Manichaean Analysis — Correspondential Reading Project

Reading the Manichaean texts through the correspondential lens — the same methodology applied to the [Nag Hammadi Library](https://github.com/marconian/NagHammadiLibrary).

## Why Manichaeism?

Mani (216–274 CE) explicitly synthesized Zoroaster, Buddha, and Jesus — claiming to complete their "partial truths" in a universal religion. The Manichaean tradition is the **only historical religion to have been officially adopted by the Uyghur Khaganate** (762/763 CE), placing its scriptures physically in the cave libraries of "Great Tartary" — the Turfan/Turpan region that Swedenborg described as preserving the Ancient Word.

The Manichaean Psalm Book — a liturgical collection including the Psalms of Thomas — converges with Swedenborg's *Spiritual Diary* Entry 6077, where spirits from "Lesser Tartary" possess a "Divine Book" identified as "the Psalms of David." The German Turfan expeditions (1902–1914) recovered thousands of Manichaean manuscript fragments from exactly these caves.

This is not coincidence. This is the natural degree expressing the spiritual degree. The correspondential lens is applied because it organizes the data better than alternatives.

## Repository Structure

```
manichaean-analysis/
├── .github/
│   └── copilot-instructions.md    # Editorial instructions
├── data/                           # Source files (if needed)
├── output/
│   ├── texts/                     # Scraped texts (markdown)
│   ├── cleaned/                   # Cleaned versions
│   └── pdfs/                      # Generated PDFs
├── findings/
│   ├── schema.yaml                # Findings schema
│   └── texts/                     # Per-text findings (YAML)
├── scripts/
│   └── scrape_gnosis.py           # Scraper for gnosis.org
├── cache/                          # Build cache
├── secrets/                        # Credentials (gitignored)
└── environment.yml                 # Conda environment
```

## Setup

```bash
conda env create -f environment.yml
conda activate manichaean
```

## Scraping

```bash
# Scrape all Manichaean texts from gnosis.org
python scripts/scrape_gnosis.py

# Scrape specific category only
python scripts/scrape_gnosis.py --category parthian_hymns

# List available categories without scraping
python scripts/scrape_gnosis.py --list-categories

# Dry run (show what would be scraped)
python scripts/scrape_gnosis.py --dry-run
```

## Companion Repositories

| Repository | Purpose |
|---|---|
| [literary-compilation](https://github.com/marconian/literary-compilation) | The Divine Bricolage framework — knowledge graph, source documents |
| [structured-data-analysis](https://github.com/marconian/structured-data-analysis) | Empirical data analysis — NDE, past-life memory, MallWorld |
| [NagHammadiLibrary](https://github.com/marconian/NagHammadiLibrary) | NHL correspondential reading project |
| [ProtoLuke](https://github.com/marconian/ProtoLuke) | Proto-Luke reconstruction — the Jamesian Protograph |
