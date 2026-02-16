# Kephalaia Core Recovery — v3 Paragraph-Level Analysis Report

## 1. Methodology

This analysis treats **chapter boundaries as editorial artifacts** and works at the paragraph level to recover the original Manichaean teaching underneath the editorial infrastructure imposed by later redactors.

### Pipeline
1. **Line Classification**: Every line tagged as FRONT_MATTER, CHAPTER_MARKER, PAGE_REF, TITLE, GARDNER, PAGE_HEADER, PAGE_NUMBER, FOOTNOTE, DIVIDER, TEACHING, or BLANK
2. **Paragraph Extraction**: Teaching text extracted, joined across page breaks, split at semantic boundaries (speaker changes, teaching formulas, closing formulas)
3. **Vocabulary Scoring**: 5 vocabulary categories (cosmological, persian_substrate, pastoral, nt_christian, hagiographic) scored per 100 words
4. **Composite Scoring**: Weighted combination of vocabulary densities
5. **Sub-Clustering**: TF-IDF + K-means on paragraph texts
6. **Tier Classification**: Paragraphs assigned to 5 tiers based on composite score
7. **Core Reconstruction**: Tier 1–3 paragraphs extracted in document order

## 2. Source Text Decomposition

| Line Type | Count | % |
|-----------|-------|---|
| TEACHING | 1878 | 37.6% |
| GARDNER | 338 | 6.8% |
| FRONT_MATTER | 551 | 11.0% |
| BLANK | 696 | 13.9% |
| DIVIDER | 347 | 7.0% |
| PAGE_HEADER | 323 | 6.5% |
| FOOTNOTE | 155 | 3.1% |
| CHAPTER_MARKER | 123 | 2.5% |
| PAGE_REF | 114 | 2.3% |
| TITLE | 125 | 2.5% |
| PAGE_NUMBER | 341 | 6.8% |
| **TOTAL** | **4991** | **100%** |

## 3. Paragraph Statistics

- **Total teaching paragraphs**: 466
- **Total teaching words**: 96,828
- **Mean paragraph length**: 208 words
- **Median paragraph length**: 210 words
- **Range**: 5 – 443 words

## 4. Score Distribution

- **Mean**: 0.95
- **Median**: 0.69
- **Std Dev**: 3.50
- **Range**: -17.28 to 21.05

## 5. Tier Breakdown

| Tier | Label | Threshold | Paragraphs | Words | % Words |
|------|-------|-----------|------------|-------|---------|
| T1 | Definite Core | >= 4.0 | 72 | 14,679 | 15.2% |
| T2 | Strong Core | 2.0–4.0 | 67 | 13,843 | 14.3% |
| T3 | Probable Core | 0.5–2.0 | 97 | 21,677 | 22.4% |
| T4 | Borderline | -0.5–0.5 | 122 | 22,126 | 22.9% |
| T5 | Editorial | < -0.5 | 108 | 24,503 | 25.3% |
| **T1–T3** | **Core Total** | **>= 0.5** | **236** | **50,199** | **51.8%** |

## 6. Sub-Clustering

**Optimal k**: 2

**Silhouette scores**:
- k=2: 0.0291 ← optimal
- k=3: 0.0242
- k=4: 0.0242
- k=5: 0.024
- k=6: 0.0222
- k=7: 0.0226
- k=8: 0.0228
- k=9: 0.0274
- k=10: 0.0243

### Cluster Profiles

**Cosmological** (n=444, avg_score=0.81)
- Top terms: shall, light, great, body, time, man, living, world, father, darkness
- Avg densities: {'cosmological': 0.95, 'persian_substrate': 0.019, 'pastoral': 0.567, 'nt_christian': 0.009, 'hagiographic': 0.001}

**Core Cosmological** (n=22, avg_score=3.86)
- Top terms: 20, 24, 15, 19, 29, 22, 16, 12, 21, 23
- Avg densities: {'cosmological': 2.188, 'persian_substrate': 0.088, 'pastoral': 0.197, 'nt_christian': 0.225, 'hagiographic': 0.045}

## 7. Top 30 Passages by Score

| Rank | ID | Ch. | Score | Words | Cosmo | Pastoral | Key Terms |
|------|-----|-----|-------|-------|-------|----------|-----------|
| 1 | P0149 | 42 | +21.05 | 76 | 10.5 | 0.0 | three vessels x2; rulers x2; vessels x2 |
| 2 | P0443 | 122 | +19.27 | 218 | 9.2 | 0.9 | first man x2; mother of life x1; father of greatness x1 |
| 3 | P0186 | 53 | +13.13 | 198 | 6.6 | 0.0 | first man x3; living spirit x1; living fire x1 |
| 4 | P0058 | 16 | +11.38 | 202 | 5.0 | 0.0 | first man x1; living spirit x2; mother of life x1 |
| 5 | P0051 | 10 | +9.74 | 195 | 4.6 | 0.5 | first man x1; living spirit x2; five sons x1 |
| 6 | P0269 | 75 | +8.49 | 212 | 4.2 | 0.0 | first man x4; living spirit x4; rulers x1 |
| 7 | P0446 | 122 | +7.96 | 201 | 4.0 | 0.0 | mother of life x2; jesus splendour x1; light mind x1 |
| 8 | P0189 | 54 | +7.93 | 227 | 4.0 | 0.0 | living spirit x3; mother of life x1; five sons x1 |
| 9 | P0087 | 24 | +7.83 | 115 | 2.6 | 0.0 | father of greatness x1; storehouses x1; aeons x1 |
| 10 | P0075 | 19 | +7.82 | 179 | 5.6 | 1.7 | first man x3; living spirit x2; mother of life x1 |
| 11 | P0102 | 28 | +7.69 | 221 | 3.2 | 0.0 | first man x2; living spirit x1; mother of life x1 |
| 12 | P0119 | 37 | +7.64 | 157 | 3.8 | 0.0 | living spirit x2; king of honour x1; five sons x1 |
| 13 | P0112 | 32 | +7.62 | 210 | 3.8 | 0.0 | first man x1; living spirit x1; five sons x1 |
| 14 | P0025 | 4 | +7.49 | 347 | 2.9 | 0.0 | first man x1; land of darkness x2; five elements x2 |
| 15 | P0106 | 29 | +7.08 | 226 | 3.5 | 0.0 | first man x1; mother of life x1; great builder x1 |
| 16 | P0071 | 18 | +7.06 | 184 | 2.7 | 0.0 | living soul x1; living fire x1; five elements x1 |
| 17 | P0457 | 122 | +7.00 | 200 | 3.5 | 0.0 | garment of fire x1; garment of wind x1; garment of water x1 |
| 18 | P0415 | 115 | +6.97 | 201 | 3.5 | 0.0 | first man x1; living spirit x3; mother of life x2 |
| 19 | P0167 | 46 | +6.90 | 29 | 3.4 | 0.0 | great builder x1 |
| 20 | P0450 | 122 | +6.83 | 205 | 4.4 | 1.0 | land of light x2; five worlds x1; storehouses x3 |
| 21 | P0057 | 15 | +6.75 | 252 | 3.6 | 0.8 | first man x4; land of darkness x1; five elements x1 |
| 22 | P0090 | 24 | +6.67 | 300 | 2.7 | 0.3 | first man x2; living spirit x1; father of greatness x2 |
| 23 | P0162 | 43 | +6.45 | 217 | 3.2 | 0.0 | firmaments x2; constructed x1; discharged x4 |
| 24 | P0160 | 43 | +6.35 | 63 | 3.2 | 0.0 | vessels x1; discharged x1 |
| 25 | P0152 | 42 | +6.28 | 191 | 3.1 | 0.0 | living fire x1; garment of wind x1; garment of water x1 |
| 26 | P0107 | 29 | +6.25 | 224 | 3.1 | 0.0 | first man x1; living spirit x2; third ambassador x1 |
| 27 | P0261 | 72 | +6.12 | 196 | 3.1 | 0.0 | perfect man x1; five worlds x1; rulers x1 |
| 28 | P0445 | 122 | +6.00 | 200 | 3.0 | 0.0 | living spirit x1; king of honour x1; keeper of splendour x1 |
| 29 | P0072 | 18 | +5.98 | 234 | 3.0 | 0.0 | living spirit x3; three vessels x1; rulers x2 |
| 30 | P0067 | 17 | +5.96 | 235 | 3.4 | 0.4 | first man x4; living spirit x1; land of darkness x1 |

## 8. Bottom 15 Passages (Most Editorial)

| Rank | ID | Ch. | Score | Words | Cosmo | Pastoral | Key Terms |
|------|-----|-----|-------|-------|-------|----------|-----------|
| 452 | P0270 | 75 | -5.40 | 185 | 0.5 | 3.2 | holy church x3; prayers x1; church x2 |
| 453 | P0330 | 87 | -5.70 | 316 | 0.0 | 2.8 | holy church x2; place of rest x3; catechumens x2 |
| 454 | P0411 | 115 | -5.71 | 105 | 1.9 | 4.8 | catechumens x2; elect x1; prayer x1 |
| 455 | P0349 | 91 | -6.16 | 357 | 0.0 | 3.1 | holy church x2; catechumens x2; elect x1 |
| 456 | P0287 | 80 | -6.19 | 226 | 0.0 | 3.1 | holy church x1; catechumen x2; alms x1 |
| 457 | P0353 | 91 | -6.28 | 382 | 0.3 | 3.4 | catechumen x2; elect x2; alms x2 |
| 458 | P0289 | 81 | -6.43 | 249 | 0.0 | 3.2 | catechumens x1; elect x2; fasting x4 |
| 459 | P0351 | 91 | -7.59 | 290 | 0.0 | 3.8 | holy church x1; catechumen x1; catechumens x1 |
| 460 | P0381 | 99 | -8.00 | 25 | 0.0 | 4.0 | catechumens x1 |
| 461 | P0358 | 92 | -8.89 | 180 | 0.0 | 4.4 | catechumen x5; elect x3 |
| 462 | P0332 | 88 | -9.30 | 129 | 0.0 | 4.7 | catechumen x3; elect x3 |
| 463 | P0356 | 92 | -10.94 | 128 | 0.8 | 6.2 | land of light x1; catechumen x3; catechumens x1 |
| 464 | P0331 | 87 | -11.11 | 126 | 0.8 | 6.3 | holy church x2; place of rest x3; catechumens x1 |
| 465 | P0329 | 87 | -13.19 | 273 | 0.4 | 7.0 | holy church x4; place of rest x2; catechumens x3 |
| 466 | P0288 | 80 | -17.28 | 81 | 0.0 | 8.6 | holy church x2; catechumen x1; catechumens x1 |

## 9. Editorial Chapter Coverage

How each editorial chapter's paragraphs distribute across tiers:

| Ch. | Paras | T1 | T2 | T3 | T4 | T5 | Avg Score | Verdict |
|-----|-------|----|----|----|----|----|-----------| --------|
| 1 | 12 | 0 | 0 | 0 | 4 | 8 | -1.55 | EDITORIAL |
| 2 | 8 | 0 | 1 | 1 | 6 | 0 | +0.56 | MIXED |
| 3 | 3 | 0 | 0 | 2 | 1 | 0 | +0.98 | MIXED |
| 4 | 4 | 2 | 2 | 0 | 0 | 0 | +5.19 | CORE |
| 5 | 4 | 2 | 1 | 0 | 1 | 0 | +3.29 | CORE |
| 6 | 6 | 1 | 2 | 1 | 2 | 0 | +1.84 | MIXED |
| 7 | 4 | 0 | 1 | 3 | 0 | 0 | +1.59 | MIXED |
| 8 | 1 | 0 | 0 | 0 | 0 | 1 | -0.84 | EDITORIAL |
| 9 | 8 | 2 | 2 | 2 | 1 | 1 | +2.20 | CORE |
| 10 | 2 | 1 | 0 | 1 | 0 | 0 | +5.60 | CORE |
| 11 | 1 | 1 | 0 | 0 | 0 | 0 | +4.39 | CORE |
| 12 | 1 | 0 | 0 | 1 | 0 | 0 | +0.95 | MIXED |
| 13 | 1 | 0 | 0 | 1 | 0 | 0 | +1.31 | MIXED |
| 14 | 1 | 0 | 0 | 1 | 0 | 0 | +1.79 | MIXED |
| 15 | 1 | 1 | 0 | 0 | 0 | 0 | +6.75 | CORE |
| 16 | 9 | 4 | 1 | 3 | 0 | 1 | +3.50 | CORE |
| 17 | 4 | 2 | 0 | 2 | 0 | 0 | +3.44 | CORE |
| 18 | 4 | 2 | 0 | 1 | 0 | 1 | +2.77 | CORE |
| 19 | 4 | 1 | 1 | 1 | 1 | 0 | +2.94 | CORE |
| 20 | 1 | 1 | 0 | 0 | 0 | 0 | +5.10 | CORE |
| 21 | 1 | 0 | 1 | 0 | 0 | 0 | +3.83 | CORE |
| 22 | 1 | 0 | 0 | 1 | 0 | 0 | +0.82 | MIXED |
| 23 | 5 | 1 | 3 | 0 | 1 | 0 | +2.28 | CORE |
| 24 | 8 | 4 | 1 | 2 | 1 | 0 | +3.63 | CORE |
| 25 | 1 | 1 | 0 | 0 | 0 | 0 | +4.55 | CORE |
| 26 | 3 | 0 | 2 | 1 | 0 | 0 | +2.78 | CORE |
| 27 | 3 | 0 | 0 | 1 | 2 | 0 | +0.26 | MIXED |
| 28 | 4 | 2 | 0 | 2 | 0 | 0 | +3.95 | CORE |
| 29 | 3 | 2 | 1 | 0 | 0 | 0 | +5.13 | CORE |
| 30 | 1 | 0 | 0 | 0 | 1 | 0 | +0.00 | MIXED |
| 31 | 2 | 0 | 1 | 1 | 0 | 0 | +2.22 | CORE |
| 32 | 2 | 1 | 1 | 0 | 0 | 0 | +5.44 | CORE |
| 33 | 1 | 0 | 1 | 0 | 0 | 0 | +2.04 | CORE |
| 34 | 1 | 0 | 1 | 0 | 0 | 0 | +2.76 | CORE |
| 35 | 1 | 0 | 0 | 1 | 0 | 0 | +1.59 | MIXED |
| 36 | 2 | 1 | 1 | 0 | 0 | 0 | +3.92 | CORE |
| 37 | 1 | 1 | 0 | 0 | 0 | 0 | +7.64 | CORE |
| 38 | 21 | 2 | 4 | 6 | 4 | 5 | +1.02 | MIXED |
| 39 | 4 | 0 | 2 | 1 | 1 | 0 | +1.89 | MIXED |
| 40 | 1 | 0 | 0 | 1 | 0 | 0 | +1.26 | MIXED |
| 41 | 3 | 0 | 0 | 1 | 1 | 1 | +0.37 | MIXED |
| 42 | 9 | 4 | 1 | 3 | 1 | 0 | +4.76 | CORE |
| 43 | 5 | 3 | 1 | 0 | 1 | 0 | +4.36 | CORE |
| 44 | 3 | 1 | 1 | 0 | 1 | 0 | +3.00 | CORE |
| 45 | 1 | 1 | 0 | 0 | 0 | 0 | +5.45 | CORE |
| 46 | 3 | 1 | 0 | 1 | 1 | 0 | +2.61 | CORE |
| 47 | 3 | 0 | 1 | 0 | 2 | 0 | +1.00 | MIXED |
| 48 | 7 | 1 | 2 | 2 | 2 | 0 | +1.96 | MIXED |
| 49 | 1 | 0 | 0 | 1 | 0 | 0 | +0.99 | MIXED |
| 50 | 2 | 0 | 1 | 0 | 1 | 0 | +1.32 | MIXED |
| 51 | 1 | 0 | 1 | 0 | 0 | 0 | +2.11 | CORE |
| 52 | 2 | 0 | 0 | 0 | 1 | 1 | -0.49 | EDITORIAL |
| 53 | 3 | 3 | 0 | 0 | 0 | 0 | +7.54 | CORE |
| 54 | 3 | 1 | 0 | 1 | 1 | 0 | +3.22 | CORE |
| 55 | 6 | 3 | 1 | 1 | 1 | 0 | +3.36 | CORE |
| 56 | 11 | 0 | 1 | 3 | 6 | 1 | +0.53 | MIXED |
| 57 | 5 | 0 | 0 | 1 | 3 | 1 | -0.05 | EDITORIAL |
| 58 | 2 | 0 | 0 | 1 | 0 | 1 | +0.32 | MIXED |
| 59 | 4 | 0 | 1 | 0 | 2 | 1 | +0.30 | MIXED |
| 60 | 3 | 0 | 1 | 1 | 1 | 0 | +1.14 | MIXED |
| 61 | 5 | 0 | 2 | 2 | 1 | 0 | +1.85 | MIXED |
| 62 | 1 | 0 | 0 | 1 | 0 | 0 | +0.78 | MIXED |
| 63 | 2 | 0 | 1 | 0 | 1 | 0 | +1.00 | MIXED |
| 64 | 4 | 0 | 0 | 2 | 2 | 0 | +0.70 | MIXED |
| 65 | 9 | 0 | 1 | 3 | 5 | 0 | +0.56 | MIXED |
| 66 | 1 | 0 | 0 | 0 | 0 | 1 | -3.12 | EDITORIAL |
| 67 | 1 | 0 | 0 | 0 | 0 | 1 | -3.02 | EDITORIAL |
| 68 | 1 | 0 | 0 | 0 | 1 | 0 | +0.00 | MIXED |
| 69 | 5 | 0 | 2 | 1 | 2 | 0 | +1.23 | MIXED |
| 70 | 8 | 1 | 3 | 3 | 1 | 0 | +2.21 | CORE |
| 71 | 1 | 0 | 0 | 1 | 0 | 0 | +1.42 | MIXED |
| 72 | 3 | 1 | 0 | 1 | 1 | 0 | +2.29 | CORE |
| 73 | 3 | 0 | 0 | 0 | 2 | 1 | -0.66 | EDITORIAL |
| 74 | 2 | 1 | 1 | 0 | 0 | 0 | +4.40 | CORE |
| 75 | 3 | 1 | 0 | 0 | 1 | 1 | +1.03 | MIXED |
| 76 | 9 | 0 | 0 | 1 | 5 | 3 | -0.52 | EDITORIAL |
| 77 | 3 | 0 | 0 | 0 | 1 | 2 | -1.86 | EDITORIAL |
| 78 | 1 | 0 | 0 | 0 | 1 | 0 | +0.00 | MIXED |
| 79 | 1 | 0 | 0 | 0 | 0 | 1 | -3.23 | EDITORIAL |
| 80 | 3 | 0 | 0 | 0 | 0 | 3 | -8.71 | EDITORIAL |
| 81 | 6 | 0 | 0 | 0 | 2 | 4 | -2.11 | EDITORIAL |
| 82 | 6 | 0 | 0 | 0 | 2 | 4 | -1.43 | EDITORIAL |
| 83 | 5 | 0 | 0 | 0 | 3 | 2 | -0.74 | EDITORIAL |
| 84 | 8 | 0 | 0 | 1 | 7 | 0 | +0.12 | MIXED |
| 85 | 9 | 0 | 0 | 2 | 1 | 6 | -1.90 | EDITORIAL |
| 86 | 6 | 0 | 1 | 3 | 2 | 0 | +0.85 | MIXED |
| 87 | 3 | 0 | 0 | 0 | 0 | 3 | -10.00 | EDITORIAL |
| 88 | 5 | 0 | 0 | 0 | 1 | 4 | -3.14 | EDITORIAL |
| 89 | 4 | 0 | 0 | 0 | 3 | 1 | -0.54 | EDITORIAL |
| 90 | 7 | 0 | 0 | 1 | 1 | 5 | -1.76 | EDITORIAL |
| 91 | 8 | 0 | 0 | 0 | 0 | 8 | -4.47 | EDITORIAL |
| 92 | 3 | 0 | 0 | 0 | 0 | 3 | -7.20 | EDITORIAL |
| 93 | 4 | 0 | 0 | 0 | 0 | 4 | -2.35 | EDITORIAL |
| 94 | 2 | 1 | 0 | 1 | 0 | 0 | +3.68 | CORE |
| 95 | 6 | 0 | 2 | 3 | 1 | 0 | +1.79 | MIXED |
| 96 | 2 | 0 | 0 | 0 | 2 | 0 | +0.00 | MIXED |
| 97 | 3 | 0 | 0 | 0 | 1 | 2 | -0.49 | EDITORIAL |
| 98 | 3 | 0 | 0 | 2 | 1 | 0 | +0.90 | MIXED |
| 99 | 3 | 0 | 0 | 0 | 0 | 3 | -3.96 | EDITORIAL |
| 100 | 3 | 0 | 0 | 0 | 2 | 1 | -0.43 | EDITORIAL |
| 101 | 3 | 0 | 0 | 1 | 2 | 0 | +0.65 | MIXED |
| 102 | 3 | 0 | 0 | 1 | 0 | 2 | -0.65 | EDITORIAL |
| 103 | 1 | 0 | 0 | 0 | 1 | 0 | +0.00 | MIXED |
| 104 | 1 | 0 | 0 | 0 | 1 | 0 | +0.00 | MIXED |
| 105 | 1 | 0 | 0 | 0 | 0 | 1 | -1.23 | EDITORIAL |
| 106 | 2 | 0 | 1 | 1 | 0 | 0 | +1.78 | MIXED |
| 107 | 1 | 0 | 0 | 0 | 1 | 0 | +0.00 | MIXED |
| 108 | 1 | 0 | 1 | 0 | 0 | 0 | +3.30 | CORE |
| 109 | 3 | 0 | 0 | 1 | 1 | 1 | -0.39 | EDITORIAL |
| 110 | 1 | 0 | 0 | 1 | 0 | 0 | +1.63 | MIXED |
| 111 | 1 | 0 | 0 | 0 | 1 | 0 | +0.00 | MIXED |
| 112 | 4 | 0 | 0 | 3 | 1 | 0 | +0.85 | MIXED |
| 113 | 1 | 0 | 1 | 0 | 0 | 0 | +2.63 | CORE |
| 114 | 3 | 0 | 3 | 0 | 0 | 0 | +3.22 | CORE |
| 115 | 15 | 4 | 0 | 2 | 0 | 9 | -0.18 | EDITORIAL |
| 116 | 2 | 0 | 0 | 0 | 2 | 0 | +0.00 | MIXED |
| 117 | 1 | 0 | 0 | 0 | 1 | 0 | +0.00 | MIXED |
| 119 | 2 | 0 | 0 | 1 | 0 | 1 | -0.05 | EDITORIAL |
| 120 | 3 | 0 | 0 | 0 | 2 | 1 | -0.64 | EDITORIAL |
| 121 | 3 | 0 | 0 | 2 | 0 | 1 | -0.05 | EDITORIAL |
| 122 | 30 | 10 | 6 | 3 | 5 | 6 | +2.68 | CORE |

## Appendix: Full Paragraph Inventory

| ID | Ch. | Lines | Words | Score | Tier | Cluster | Cosmo | Pastoral |
|----|-----|-------|-------|-------|------|---------|-------|----------|
| P0001 | 1 | 843–845 | 310 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0002 | 1 | 846–852 | 182 | -3.30 | T5 | Cosmological | 0.0 | 1.6 |
| P0003 | 1 | 853–855 | 285 | -2.11 | T5 | Cosmological | 0.0 | 1.1 |
| P0004 | 1 | 856–864 | 215 | -0.93 | T5 | Cosmological | 0.0 | 0.5 |
| P0005 | 1 | 865–866 | 211 | -3.79 | T5 | Cosmological | 0.0 | 1.9 |
| P0006 | 1 | 867–874 | 278 | +0.18 | T4 | Cosmological | 0.4 | 0.0 |
| P0007 | 1 | 875–878 | 216 | -2.78 | T5 | Cosmological | 0.0 | 1.4 |
| P0008 | 1 | 885–887 | 239 | -3.77 | T5 | Cosmological | 0.0 | 1.3 |
| P0009 | 1 | 888–888 | 198 | -0.76 | T5 | Cosmological | 0.0 | 0.0 |
| P0010 | 1 | 895–898 | 304 | -1.32 | T5 | Cosmological | 0.0 | 0.7 |
| P0011 | 1 | 899–907 | 209 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0012 | 1 | 908–908 | 103 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0013 | 2 | 922–925 | 207 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0014 | 2 | 926–933 | 229 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0015 | 2 | 934–935 | 168 | +1.19 | T3 | Cosmological | 1.2 | 0.6 |
| P0016 | 2 | 936–945 | 302 | +3.31 | T2 | Cosmological | 2.3 | 0.7 |
| P0017 | 2 | 946–947 | 241 | +0.00 | T4 | Cosmological | 0.8 | 0.8 |
| P0018 | 2 | 948–955 | 251 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0019 | 2 | 956–958 | 235 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0020 | 2 | 959–959 | 23 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0021 | 3 | 970–973 | 207 | +0.97 | T3 | Cosmological | 1.0 | 0.5 |
| P0022 | 3 | 974–983 | 252 | +1.99 | T3 | Cosmological | 2.8 | 1.6 |
| P0023 | 3 | 984–984 | 35 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0024 | 4 | 997–999 | 207 | +5.80 | T1 | Cosmological | 2.9 | 0.0 |
| P0025 | 4 | 1000–1009 | 347 | +7.49 | T1 | Cosmological | 2.9 | 0.0 |
| P0026 | 4 | 1010–1017 | 213 | +3.76 | T2 | Cosmological | 1.9 | 0.0 |
| P0027 | 4 | 1018–1019 | 161 | +3.73 | T2 | Cosmological | 1.9 | 0.0 |
| P0028 | 5 | 1029–1031 | 199 | +5.03 | T1 | Cosmological | 2.5 | 0.0 |
| P0029 | 5 | 1032–1033 | 238 | +2.94 | T2 | Cosmological | 2.1 | 1.3 |
| P0030 | 5 | 1040–1043 | 193 | +5.18 | T1 | Cosmological | 2.6 | 0.0 |
| P0031 | 5 | 1044–1046 | 150 | +0.00 | T4 | Cosmological | 0.7 | 0.7 |
| P0032 | 6 | 1057–1064 | 232 | +5.17 | T1 | Cosmological | 2.6 | 0.0 |
| P0033 | 6 | 1065–1067 | 327 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0034 | 6 | 1075–1077 | 364 | +0.55 | T3 | Cosmological | 0.3 | 0.0 |
| P0035 | 6 | 1078–1086 | 265 | +3.02 | T2 | Cosmological | 1.5 | 0.0 |
| P0036 | 6 | 1087–1089 | 262 | +2.29 | T2 | Cosmological | 1.1 | 0.0 |
| P0037 | 6 | 1095–1095 | 63 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0038 | 7 | 1100–1109 | 197 | +1.02 | T3 | Cosmological | 0.5 | 0.0 |
| P0039 | 7 | 1110–1115 | 225 | +3.56 | T2 | Cosmological | 1.8 | 0.0 |
| P0040 | 7 | 1116–1127 | 213 | +0.94 | T3 | Cosmological | 0.9 | 0.5 |
| P0041 | 7 | 1128–1139 | 232 | +0.86 | T3 | Cosmological | 1.3 | 0.9 |
| P0042 | 8 | 1149–1157 | 237 | -0.84 | T5 | Cosmological | 0.4 | 0.8 |
| P0043 | 9 | 1172–1173 | 208 | +1.92 | T3 | Cosmological | 1.0 | 0.0 |
| P0044 | 9 | 1174–1182 | 201 | +2.98 | T2 | Cosmological | 2.0 | 0.5 |
| P0045 | 9 | 1183–1187 | 271 | +5.17 | T1 | Cosmological | 2.6 | 0.0 |
| P0046 | 9 | 1188–1196 | 240 | +5.00 | T1 | Cosmological | 2.9 | 0.4 |
| P0047 | 9 | 1197–1198 | 236 | +0.85 | T3 | Cosmological | 0.8 | 0.4 |
| P0048 | 9 | 1199–1209 | 254 | -0.79 | T5 | Cosmological | 1.2 | 1.6 |
| P0049 | 9 | 1210–1216 | 245 | +2.45 | T2 | Cosmological | 1.6 | 0.4 |
| P0050 | 9 | 1217–1219 | 271 | +0.00 | T4 | Cosmological | 0.4 | 0.4 |
| P0051 | 10 | 1231–1233 | 195 | +9.74 | T1 | Cosmological | 4.6 | 0.5 |
| P0052 | 10 | 1234–1234 | 138 | +1.45 | T3 | Cosmological | 0.7 | 0.0 |
| P0053 | 11 | 1244–1261 | 319 | +4.39 | T1 | Cosmological | 2.5 | 0.3 |
| P0054 | 12 | 1266–1276 | 210 | +0.95 | T3 | Cosmological | 0.5 | 0.0 |
| P0055 | 13 | 1281–1287 | 153 | +1.31 | T3 | Cosmological | 0.7 | 0.0 |
| P0056 | 14 | 1298–1302 | 223 | +1.79 | T3 | Cosmological | 0.9 | 0.0 |
| P0057 | 15 | 1317–1327 | 252 | +6.75 | T1 | Cosmological | 3.6 | 0.8 |
| P0058 | 16 | 1334–1345 | 202 | +11.38 | T1 | Cosmological | 5.0 | 0.0 |
| P0059 | 16 | 1346–1348 | 191 | +4.19 | T1 | Cosmological | 2.1 | 0.0 |
| P0060 | 16 | 1349–1357 | 328 | +1.83 | T3 | Cosmological | 1.5 | 0.6 |
| P0061 | 16 | 1358–1359 | 218 | +2.75 | T2 | Cosmological | 2.3 | 0.9 |
| P0062 | 16 | 1365–1367 | 241 | +5.81 | T1 | Cosmological | 2.9 | 0.0 |
| P0063 | 16 | 1368–1375 | 217 | +4.61 | T1 | Cosmological | 2.8 | 0.5 |
| P0064 | 16 | 1376–1377 | 234 | +1.71 | T3 | Cosmological | 0.9 | 0.0 |
| P0065 | 16 | 1378–1385 | 277 | +0.72 | T3 | Cosmological | 0.4 | 0.0 |
| P0066 | 16 | 1386–1387 | 131 | -1.53 | T5 | Cosmological | 0.0 | 0.8 |
| P0067 | 17 | 1394–1402 | 235 | +5.96 | T1 | Cosmological | 3.4 | 0.4 |
| P0068 | 17 | 1403–1404 | 201 | +1.00 | T3 | Cosmological | 1.5 | 1.0 |
| P0069 | 17 | 1405–1415 | 214 | +1.87 | T3 | Cosmological | 0.9 | 0.0 |
| P0070 | 17 | 1416–1418 | 162 | +4.94 | T1 | Cosmological | 2.5 | 0.0 |
| P0071 | 18 | 1434–1435 | 184 | +7.06 | T1 | Cosmological | 2.7 | 0.0 |
| P0072 | 18 | 1436–1444 | 234 | +5.98 | T1 | Cosmological | 3.0 | 0.0 |
| P0073 | 18 | 1445–1447 | 208 | +0.96 | T3 | Cosmological | 0.5 | 0.0 |
| P0074 | 18 | 1448–1456 | 68 | -2.94 | T5 | Cosmological | 0.0 | 1.5 |
| P0075 | 19 | 1461–1463 | 179 | +7.82 | T1 | Cosmological | 5.6 | 1.7 |
| P0076 | 19 | 1464–1472 | 224 | +1.79 | T3 | Cosmological | 1.3 | 0.4 |
| P0077 | 19 | 1473–1478 | 187 | +2.14 | T2 | Cosmological | 1.1 | 0.0 |
| P0078 | 19 | 1479–1488 | 101 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0079 | 20 | 1493–1504 | 255 | +5.10 | T1 | Cosmological | 2.4 | 0.4 |
| P0080 | 21 | 1508–1519 | 287 | +3.83 | T2 | Cosmological | 1.7 | 0.3 |
| P0081 | 22 | 1524–1529 | 245 | +0.82 | T3 | Cosmological | 0.8 | 0.4 |
| P0082 | 23 | 1541–1544 | 179 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0083 | 23 | 1551–1553 | 199 | +3.02 | T2 | Cosmological | 1.5 | 0.0 |
| P0084 | 23 | 1554–1556 | 185 | +2.16 | T2 | Cosmological | 1.1 | 0.0 |
| P0085 | 23 | 1557–1568 | 172 | +4.07 | T1 | Cosmological | 1.7 | 0.6 |
| P0086 | 23 | 1569–1570 | 187 | +2.14 | T2 | Cosmological | 1.1 | 0.0 |
| P0087 | 24 | 1588–1598 | 115 | +7.83 | T1 | Cosmological | 2.6 | 0.0 |
| P0088 | 24 | 1599–1601 | 202 | +4.95 | T1 | Cosmological | 2.5 | 0.0 |
| P0089 | 24 | 1602–1609 | 237 | +4.64 | T1 | Cosmological | 1.7 | 0.0 |
| P0090 | 24 | 1610–1611 | 300 | +6.67 | T1 | Cosmological | 2.7 | 0.3 |
| P0091 | 24 | 1612–1619 | 179 | +1.12 | T3 | Cosmological | 0.6 | 0.0 |
| P0092 | 24 | 1620–1622 | 397 | +1.76 | T3 | Cosmological | 0.5 | 0.0 |
| P0093 | 24 | 1628–1633 | 197 | +2.03 | T2 | Cosmological | 1.0 | 0.0 |
| P0094 | 24 | 1634–1642 | 236 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0095 | 25 | 1646–1647 | 88 | +4.55 | T1 | Cosmological | 2.3 | 0.0 |
| P0096 | 26 | 1663–1663 | 62 | +3.23 | T2 | Cosmological | 1.6 | 0.0 |
| P0097 | 26 | 1664–1665 | 107 | +3.74 | T2 | Cosmological | 1.9 | 0.0 |
| P0098 | 26 | 1666–1668 | 146 | +1.37 | T3 | Cosmological | 0.7 | 0.0 |
| P0099 | 27 | 1679–1681 | 252 | +0.79 | T3 | Cosmological | 0.4 | 0.0 |
| P0100 | 27 | 1682–1696 | 286 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0101 | 27 | 1697–1698 | 108 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0102 | 28 | 1710–1713 | 221 | +7.69 | T1 | Cosmological | 3.2 | 0.0 |
| P0103 | 28 | 1714–1723 | 232 | +5.17 | T1 | Cosmological | 2.6 | 0.0 |
| P0104 | 28 | 1724–1728 | 215 | +1.86 | T3 | Cosmological | 1.4 | 0.5 |
| P0105 | 28 | 1734–1736 | 185 | +1.08 | T3 | Cosmological | 1.1 | 0.5 |
| P0106 | 29 | 1741–1751 | 226 | +7.08 | T1 | Cosmological | 3.5 | 0.0 |
| P0107 | 29 | 1752–1758 | 224 | +6.25 | T1 | Cosmological | 3.1 | 0.0 |
| P0108 | 29 | 1764–1768 | 194 | +2.06 | T2 | Cosmological | 1.5 | 0.5 |
| P0109 | 30 | 1773–1779 | 190 | +0.00 | T4 | Cosmological | 0.5 | 0.5 |
| P0110 | 31 | 1785–1795 | 194 | +3.09 | T2 | Cosmological | 1.5 | 0.0 |
| P0111 | 31 | 1796–1798 | 298 | +1.34 | T3 | Cosmological | 0.7 | 0.0 |
| P0112 | 32 | 1811–1817 | 210 | +7.62 | T1 | Cosmological | 3.8 | 0.0 |
| P0113 | 32 | 1823–1825 | 123 | +3.25 | T2 | Cosmological | 1.6 | 0.0 |
| P0114 | 33 | 1830–1835 | 98 | +2.04 | T2 | Cosmological | 1.0 | 0.0 |
| P0115 | 34 | 1845–1855 | 145 | +2.76 | T2 | Cosmological | 1.4 | 0.0 |
| P0116 | 35 | 1865–1869 | 126 | +1.59 | T3 | Cosmological | 0.8 | 0.0 |
| P0117 | 36 | 1878–1879 | 315 | +4.44 | T1 | Cosmological | 2.2 | 0.0 |
| P0118 | 36 | 1880–1880 | 59 | +3.39 | T2 | Cosmological | 1.7 | 0.0 |
| P0119 | 37 | 1891–1891 | 157 | +7.64 | T1 | Cosmological | 3.8 | 0.0 |
| P0120 | 38 | 1906–1909 | 201 | +2.99 | T2 | Cosmological | 3.5 | 2.0 |
| P0121 | 38 | 1910–1919 | 219 | +2.74 | T2 | Cosmological | 1.4 | 0.0 |
| P0122 | 38 | 1920–1926 | 241 | +1.66 | T3 | Cosmological | 0.8 | 0.0 |
| P0123 | 38 | 1927–1933 | 286 | +3.50 | T2 | Cosmological | 1.7 | 0.0 |
| P0124 | 38 | 1934–1935 | 203 | +1.97 | T3 | Cosmological | 1.5 | 0.5 |
| P0125 | 38 | 1936–1947 | 265 | +3.77 | T2 | Cosmological | 2.3 | 0.4 |
| P0126 | 38 | 1948–1956 | 194 | +0.00 | T4 | Cosmological | 1.0 | 1.0 |
| P0127 | 38 | 1957–1960 | 217 | +1.84 | T3 | Cosmological | 0.9 | 0.0 |
| P0128 | 38 | 1961–1969 | 242 | +0.00 | T4 | Cosmological | 0.4 | 0.4 |
| P0129 | 38 | 1970–1973 | 299 | -0.67 | T5 | Cosmological | 0.3 | 0.7 |
| P0130 | 38 | 1979–1980 | 265 | +1.51 | T3 | Cosmological | 1.5 | 0.8 |
| P0131 | 38 | 1981–1982 | 202 | -3.96 | T5 | Cosmological | 0.0 | 2.0 |
| P0132 | 38 | 1988–1988 | 211 | +5.69 | T1 | Cosmological | 2.8 | 0.0 |
| P0133 | 38 | 1989–1990 | 189 | +4.23 | T1 | Cosmological | 2.6 | 0.5 |
| P0134 | 38 | 1991–1998 | 255 | -2.35 | T5 | Cosmological | 0.4 | 1.6 |
| P0135 | 38 | 1999–2000 | 204 | -2.94 | T5 | Cosmological | 0.0 | 1.5 |
| P0136 | 38 | 2001–2008 | 282 | +1.42 | T3 | Cosmological | 0.7 | 0.0 |
| P0137 | 38 | 2009–2012 | 198 | +1.01 | T3 | Cosmological | 0.5 | 0.0 |
| P0138 | 38 | 2018–2021 | 296 | +0.00 | T4 | Cosmological | 0.7 | 0.7 |
| P0139 | 38 | 2022–2031 | 404 | -0.99 | T5 | Cosmological | 0.2 | 0.7 |
| P0140 | 38 | 2032–2032 | 112 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0141 | 39 | 2042–2045 | 209 | +3.83 | T2 | Cosmological | 2.4 | 0.5 |
| P0142 | 39 | 2051–2054 | 265 | +2.26 | T2 | Cosmological | 1.1 | 0.0 |
| P0143 | 39 | 2055–2066 | 269 | +1.49 | T3 | Cosmological | 1.1 | 0.4 |
| P0144 | 39 | 2067–2067 | 22 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0145 | 40 | 2073–2084 | 318 | +1.26 | T3 | Cosmological | 1.3 | 0.6 |
| P0146 | 41 | 2097–2100 | 202 | +1.98 | T3 | Cosmological | 1.0 | 0.0 |
| P0147 | 41 | 2101–2107 | 230 | -0.87 | T5 | Cosmological | 0.0 | 0.4 |
| P0148 | 41 | 2108–2108 | 24 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0149 | 42 | 2122–2122 | 76 | +21.05 | T1 | Cosmological | 10.5 | 0.0 |
| P0150 | 42 | 2123–2124 | 204 | +0.98 | T3 | Cosmological | 0.5 | 0.0 |
| P0151 | 42 | 2125–2132 | 383 | +4.70 | T1 | Cosmological | 2.4 | 0.0 |
| P0152 | 42 | 2133–2143 | 191 | +6.28 | T1 | Cosmological | 3.1 | 0.0 |
| P0153 | 42 | 2144–2148 | 308 | +3.25 | T2 | Cosmological | 1.6 | 0.0 |
| P0154 | 42 | 2155–2156 | 159 | +1.26 | T3 | Cosmological | 0.6 | 0.0 |
| P0155 | 42 | 2157–2163 | 181 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0156 | 42 | 2164–2174 | 189 | +1.06 | T3 | Cosmological | 1.1 | 0.5 |
| P0157 | 42 | 2175–2175 | 93 | +4.30 | T1 | Cosmological | 3.2 | 1.1 |
| P0158 | 43 | 2190–2192 | 217 | +5.53 | T1 | Cosmological | 2.8 | 0.0 |
| P0159 | 43 | 2193–2200 | 167 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0160 | 43 | 2201–2201 | 63 | +6.35 | T1 | Cosmological | 3.2 | 0.0 |
| P0161 | 43 | 2202–2203 | 230 | +3.48 | T2 | Cosmological | 1.7 | 0.0 |
| P0162 | 43 | 2204–2213 | 217 | +6.45 | T1 | Cosmological | 3.2 | 0.0 |
| P0163 | 44 | 2225–2226 | 443 | +5.87 | T1 | Cosmological | 2.9 | 0.0 |
| P0164 | 44 | 2234–2239 | 319 | +3.13 | T2 | Cosmological | 1.6 | 0.0 |
| P0165 | 44 | 2240–2248 | 128 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0166 | 45 | 2263–2265 | 110 | +5.45 | T1 | Cosmological | 2.7 | 0.0 |
| P0167 | 46 | 2275–2276 | 29 | +6.90 | T1 | Cosmological | 3.4 | 0.0 |
| P0168 | 46 | 2282–2286 | 213 | +0.94 | T3 | Cosmological | 1.9 | 1.4 |
| P0169 | 46 | 2287–2289 | 147 | +0.00 | T4 | Cosmological | 0.7 | 0.7 |
| P0170 | 47 | 2301–2305 | 201 | +2.99 | T2 | Cosmological | 1.5 | 0.0 |
| P0171 | 47 | 2311–2312 | 266 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0172 | 47 | 2313–2320 | 314 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0173 | 48 | 2337–2339 | 77 | +2.60 | T2 | Cosmological | 1.3 | 0.0 |
| P0174 | 48 | 2340–2343 | 253 | +0.79 | T3 | Cosmological | 0.4 | 0.0 |
| P0175 | 48 | 2349–2351 | 268 | +1.49 | T3 | Cosmological | 0.7 | 0.0 |
| P0176 | 48 | 2352–2360 | 225 | +4.44 | T1 | Cosmological | 2.2 | 0.0 |
| P0177 | 48 | 2361–2363 | 354 | +3.96 | T2 | Cosmological | 2.3 | 0.3 |
| P0178 | 48 | 2370–2373 | 425 | +0.47 | T4 | Cosmological | 0.2 | 0.0 |
| P0179 | 48 | 2380–2381 | 109 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0180 | 49 | 2387–2396 | 202 | +0.99 | T3 | Cosmological | 0.5 | 0.0 |
| P0181 | 50 | 2401–2413 | 209 | +0.00 | T4 | Cosmological | 1.0 | 1.0 |
| P0182 | 50 | 2414–2419 | 228 | +2.63 | T2 | Cosmological | 1.3 | 0.0 |
| P0183 | 51 | 2429–2430 | 285 | +2.11 | T2 | Cosmological | 1.4 | 0.4 |
| P0184 | 52 | 2440–2442 | 228 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0185 | 52 | 2450–2452 | 204 | -0.98 | T5 | Cosmological | 0.0 | 0.5 |
| P0186 | 53 | 2458–2467 | 198 | +13.13 | T1 | Cosmological | 6.6 | 0.0 |
| P0187 | 53 | 2468–2470 | 208 | +4.81 | T1 | Cosmological | 2.4 | 0.0 |
| P0188 | 53 | 2477–2479 | 213 | +4.69 | T1 | Cosmological | 2.3 | 0.0 |
| P0189 | 54 | 2484–2494 | 227 | +7.93 | T1 | Cosmological | 4.0 | 0.0 |
| P0190 | 54 | 2495–2496 | 231 | +1.73 | T3 | Cosmological | 0.9 | 0.0 |
| P0191 | 54 | 2504–2504 | 38 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0192 | 55 | 2511–2517 | 236 | +3.39 | T2 | Cosmological | 1.7 | 0.0 |
| P0193 | 55 | 2518–2520 | 374 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0194 | 55 | 2526–2528 | 196 | +5.10 | T1 | Cosmological | 2.6 | 0.0 |
| P0195 | 55 | 2529–2530 | 203 | +1.97 | T3 | Cosmological | 1.0 | 0.0 |
| P0196 | 55 | 2537–2540 | 221 | +4.52 | T1 | Cosmological | 2.3 | 0.0 |
| P0197 | 55 | 2541–2542 | 77 | +5.19 | T1 | Cosmological | 2.6 | 0.0 |
| P0198 | 56 | 2557–2558 | 225 | -0.89 | T5 | Cosmological | 0.0 | 0.4 |
| P0199 | 56 | 2564–2565 | 135 | +0.00 | T4 | Cosmological | 1.5 | 1.5 |
| P0200 | 56 | 2566–2568 | 244 | +3.28 | T2 | Cosmological | 2.0 | 0.4 |
| P0201 | 56 | 2577–2579 | 234 | +0.85 | T3 | Cosmological | 0.4 | 0.0 |
| P0202 | 56 | 2580–2589 | 230 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0203 | 56 | 2590–2593 | 217 | +1.84 | T3 | Cosmological | 0.9 | 0.0 |
| P0204 | 56 | 2594–2594 | 56 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0205 | 56 | 2595–2604 | 202 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0206 | 56 | 2605–2607 | 262 | +0.76 | T3 | Cosmological | 0.8 | 0.4 |
| P0207 | 56 | 2608–2615 | 325 | +0.00 | T4 | Cosmological | 0.9 | 0.9 |
| P0208 | 56 | 2616–2624 | 237 | +0.00 | T4 | Cosmological | 0.8 | 0.8 |
| P0209 | 57 | 2631–2639 | 225 | +0.89 | T3 | Cosmological | 0.9 | 0.4 |
| P0210 | 57 | 2640–2641 | 267 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0211 | 57 | 2642–2650 | 252 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0212 | 57 | 2651–2653 | 248 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0213 | 57 | 2660–2662 | 174 | -1.15 | T5 | Cosmological | 0.0 | 0.6 |
| P0214 | 58 | 2669–2676 | 213 | +1.88 | T3 | Cosmological | 0.9 | 0.0 |
| P0215 | 58 | 2677–2677 | 163 | -1.23 | T5 | Cosmological | 0.6 | 1.2 |
| P0216 | 59 | 2693–2701 | 252 | +2.38 | T2 | Cosmological | 1.2 | 0.0 |
| P0217 | 59 | 2702–2703 | 338 | -1.18 | T5 | Cosmological | 0.3 | 0.9 |
| P0218 | 59 | 2709–2711 | 243 | +0.00 | T4 | Cosmological | 0.4 | 0.4 |
| P0219 | 59 | 2712–2712 | 29 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0220 | 60 | 2723–2725 | 202 | +0.99 | T3 | Cosmological | 0.5 | 0.0 |
| P0221 | 60 | 2726–2734 | 248 | +2.42 | T2 | Cosmological | 1.2 | 0.0 |
| P0222 | 60 | 2735–2735 | 31 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0223 | 61 | 2740–2740 | 114 | +1.75 | T3 | Cosmological | 0.9 | 0.0 |
| P0224 | 61 | 2741–2751 | 212 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0225 | 61 | 2752–2754 | 266 | +2.26 | T2 | Cosmological | 1.1 | 0.0 |
| P0226 | 61 | 2762–2763 | 301 | +1.33 | T3 | Cosmological | 1.0 | 0.3 |
| P0227 | 61 | 2764–2765 | 102 | +3.92 | T2 | Cosmological | 2.0 | 0.0 |
| P0228 | 62 | 2778–2782 | 255 | +0.78 | T3 | Cosmological | 1.2 | 0.8 |
| P0229 | 63 | 2792–2794 | 229 | -0.44 | T4 | Cosmological | 0.9 | 1.7 |
| P0230 | 63 | 2795–2802 | 164 | +2.44 | T2 | Cosmological | 1.2 | 0.0 |
| P0231 | 64 | 2808–2816 | 195 | +1.03 | T3 | Cosmological | 0.5 | 0.0 |
| P0232 | 64 | 2817–2819 | 224 | +1.79 | T3 | Cosmological | 0.9 | 0.0 |
| P0233 | 64 | 2820–2830 | 196 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0234 | 64 | 2831–2831 | 23 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0235 | 65 | 2840–2848 | 269 | +0.74 | T3 | Cosmological | 0.4 | 0.0 |
| P0236 | 65 | 2849–2852 | 198 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0237 | 65 | 2859–2864 | 230 | +0.87 | T3 | Cosmological | 0.4 | 0.0 |
| P0238 | 65 | 2865–2875 | 240 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0239 | 65 | 2876–2877 | 160 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0240 | 65 | 2878–2890 | 295 | +1.36 | T3 | Cosmological | 0.7 | 0.0 |
| P0241 | 65 | 2891–2894 | 237 | +2.11 | T2 | Cosmological | 0.4 | 0.0 |
| P0242 | 65 | 2900–2901 | 226 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0243 | 65 | 2902–2903 | 139 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0244 | 66 | 2926–2928 | 128 | -3.12 | T5 | Cosmological | 0.0 | 1.6 |
| P0245 | 67 | 2938–2940 | 265 | -3.02 | T5 | Cosmological | 0.0 | 1.5 |
| P0246 | 68 | 2955–2955 | 12 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0247 | 69 | 2963–2971 | 281 | +1.42 | T3 | Cosmological | 0.7 | 0.0 |
| P0248 | 69 | 2972–2973 | 195 | +2.05 | T2 | Cosmological | 1.0 | 0.0 |
| P0249 | 69 | 2979–2982 | 227 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0250 | 69 | 2983–2993 | 223 | +2.69 | T2 | Cosmological | 1.3 | 0.0 |
| P0251 | 69 | 2994–2994 | 81 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0252 | 70 | 3004–3011 | 231 | +1.73 | T3 | Cosmological | 1.3 | 0.4 |
| P0253 | 70 | 3012–3022 | 217 | +5.53 | T1 | Cosmological | 2.8 | 0.0 |
| P0254 | 70 | 3023–3029 | 214 | +2.80 | T2 | Cosmological | 1.9 | 0.5 |
| P0255 | 70 | 3030–3039 | 200 | +2.00 | T2 | Cosmological | 1.5 | 0.5 |
| P0256 | 70 | 3040–3044 | 209 | +1.91 | T3 | Cosmological | 1.0 | 0.0 |
| P0257 | 70 | 3045–3054 | 289 | +2.77 | T2 | Cosmological | 1.4 | 0.0 |
| P0258 | 70 | 3055–3063 | 347 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0259 | 70 | 3064–3065 | 215 | +0.93 | T3 | Cosmological | 0.5 | 0.0 |
| P0260 | 71 | 3075–3077 | 141 | +1.42 | T3 | Cosmological | 1.4 | 0.7 |
| P0261 | 72 | 3090–3097 | 196 | +6.12 | T1 | Cosmological | 3.1 | 0.0 |
| P0262 | 72 | 3098–3102 | 271 | +0.74 | T3 | Cosmological | 0.4 | 0.0 |
| P0263 | 72 | 3103–3109 | 105 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0264 | 73 | 3117–3121 | 195 | +0.26 | T4 | Cosmological | 0.5 | 0.0 |
| P0265 | 73 | 3127–3129 | 356 | -2.25 | T5 | Cosmological | 0.0 | 1.1 |
| P0266 | 73 | 3130–3130 | 77 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0267 | 74 | 3140–3145 | 197 | +3.05 | T2 | Cosmological | 1.5 | 0.0 |
| P0268 | 74 | 3146–3155 | 174 | +5.75 | T1 | Cosmological | 2.9 | 0.0 |
| P0269 | 75 | 3161–3167 | 212 | +8.49 | T1 | Cosmological | 4.2 | 0.0 |
| P0270 | 75 | 3168–3169 | 185 | -5.40 | T5 | Cosmological | 0.5 | 3.2 |
| P0271 | 75 | 3170–3170 | 37 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0272 | 76 | 3180–3181 | 207 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0273 | 76 | 3182–3191 | 322 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0274 | 76 | 3192–3193 | 222 | -0.90 | T5 | Cosmological | 0.0 | 0.5 |
| P0275 | 76 | 3194–3201 | 195 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0276 | 76 | 3202–3202 | 194 | -1.03 | T5 | Cosmological | 0.0 | 0.5 |
| P0277 | 76 | 3203–3209 | 195 | +1.03 | T3 | Cosmological | 0.5 | 0.0 |
| P0278 | 76 | 3210–3211 | 195 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0279 | 76 | 3212–3213 | 244 | +0.00 | T4 | Cosmological | 0.4 | 0.4 |
| P0280 | 76 | 3219–3220 | 159 | -3.77 | T5 | Cosmological | 0.0 | 1.9 |
| P0281 | 77 | 3226–3238 | 203 | -0.99 | T5 | Cosmological | 0.0 | 0.5 |
| P0282 | 77 | 3239–3241 | 218 | -4.59 | T5 | Cosmological | 0.0 | 2.3 |
| P0283 | 77 | 3242–3242 | 41 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0284 | 78 | 3255–3261 | 243 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0285 | 79 | 3272–3278 | 248 | -3.23 | T5 | Cosmological | 0.4 | 2.0 |
| P0286 | 80 | 3292–3293 | 226 | -2.65 | T5 | Cosmological | 0.0 | 1.3 |
| P0287 | 80 | 3299–3301 | 226 | -6.19 | T5 | Cosmological | 0.0 | 3.1 |
| P0288 | 80 | 3302–3302 | 81 | -17.28 | T5 | Cosmological | 0.0 | 8.6 |
| P0289 | 81 | 3314–3315 | 249 | -6.43 | T5 | Cosmological | 0.0 | 3.2 |
| P0290 | 81 | 3316–3322 | 206 | -2.91 | T5 | Cosmological | 0.0 | 1.5 |
| P0291 | 81 | 3323–3325 | 313 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0292 | 81 | 3326–3333 | 188 | -1.06 | T5 | Cosmological | 0.0 | 0.5 |
| P0293 | 81 | 3334–3336 | 178 | -2.25 | T5 | Cosmological | 0.0 | 1.1 |
| P0294 | 81 | 3337–3337 | 49 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0295 | 82 | 3346–3348 | 263 | -4.56 | T5 | Cosmological | 0.0 | 2.3 |
| P0296 | 82 | 3349–3349 | 93 | -2.15 | T5 | Cosmological | 0.0 | 1.1 |
| P0297 | 82 | 3350–3357 | 300 | -1.33 | T5 | Cosmological | 0.0 | 0.7 |
| P0298 | 82 | 3358–3367 | 355 | -0.56 | T5 | Cosmological | 0.0 | 0.3 |
| P0299 | 82 | 3368–3370 | 193 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0300 | 82 | 3371–3371 | 5 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0301 | 83 | 3385–3394 | 249 | -2.41 | T5 | Cosmological | 0.0 | 1.2 |
| P0302 | 83 | 3395–3395 | 248 | -0.81 | T5 | Cosmological | 1.2 | 1.6 |
| P0303 | 83 | 3396–3405 | 430 | -0.47 | T4 | Cosmological | 0.0 | 0.2 |
| P0304 | 83 | 3406–3416 | 237 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0305 | 83 | 3417–3420 | 195 | +0.00 | T4 | Cosmological | 1.5 | 1.5 |
| P0306 | 84 | 3433–3433 | 113 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0307 | 84 | 3434–3441 | 246 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0308 | 84 | 3442–3444 | 278 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0309 | 84 | 3445–3446 | 134 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0310 | 84 | 3452–3453 | 208 | +0.96 | T3 | Cosmological | 0.5 | 0.0 |
| P0311 | 84 | 3454–3457 | 229 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0312 | 84 | 3458–3465 | 125 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0313 | 84 | 3466–3466 | 30 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0314 | 85 | 3472–3481 | 222 | -4.51 | T5 | Cosmological | 0.5 | 2.7 |
| P0315 | 85 | 3482–3483 | 279 | -4.30 | T5 | Cosmological | 0.0 | 2.2 |
| P0316 | 85 | 3484–3492 | 211 | -2.84 | T5 | Cosmological | 1.4 | 2.8 |
| P0317 | 85 | 3493–3494 | 249 | +0.80 | T3 | Cosmological | 0.4 | 0.0 |
| P0318 | 85 | 3495–3495 | 48 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0319 | 85 | 3496–3503 | 371 | +1.08 | T3 | Cosmological | 0.8 | 0.3 |
| P0320 | 85 | 3504–3512 | 251 | -0.80 | T5 | Cosmological | 0.0 | 0.4 |
| P0321 | 85 | 3513–3514 | 265 | -4.53 | T5 | Cosmological | 0.8 | 3.0 |
| P0322 | 85 | 3515–3523 | 199 | -2.01 | T5 | Cosmological | 0.0 | 1.0 |
| P0323 | 86 | 3527–3531 | 229 | +2.62 | T2 | Cosmological | 1.3 | 0.0 |
| P0324 | 86 | 3537–3538 | 248 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0325 | 86 | 3539–3540 | 133 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0326 | 86 | 3541–3549 | 304 | +0.66 | T3 | Cosmological | 0.7 | 0.3 |
| P0327 | 86 | 3550–3551 | 190 | +1.05 | T3 | Cosmological | 0.5 | 0.0 |
| P0328 | 86 | 3557–3559 | 256 | +0.78 | T3 | Cosmological | 0.4 | 0.0 |
| P0329 | 87 | 3571–3572 | 273 | -13.19 | T5 | Cosmological | 0.4 | 7.0 |
| P0330 | 87 | 3573–3580 | 316 | -5.70 | T5 | Cosmological | 0.0 | 2.8 |
| P0331 | 87 | 3581–3583 | 126 | -11.11 | T5 | Cosmological | 0.8 | 6.3 |
| P0332 | 88 | 3587–3593 | 129 | -9.30 | T5 | Cosmological | 0.0 | 4.7 |
| P0333 | 88 | 3594–3595 | 320 | -1.25 | T5 | Cosmological | 0.0 | 0.6 |
| P0334 | 88 | 3596–3603 | 262 | -1.53 | T5 | Cosmological | 0.0 | 0.8 |
| P0335 | 88 | 3604–3605 | 220 | -3.64 | T5 | Cosmological | 0.0 | 1.8 |
| P0336 | 88 | 3606–3606 | 82 | +0.00 | T4 | Cosmological | 1.2 | 1.2 |
| P0337 | 89 | 3617–3618 | 86 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0338 | 89 | 3619–3628 | 235 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0339 | 89 | 3629–3630 | 370 | -2.16 | T5 | Cosmological | 0.0 | 1.1 |
| P0340 | 89 | 3637–3637 | 31 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0341 | 90 | 3646–3653 | 210 | +0.95 | T3 | Cosmological | 1.0 | 0.5 |
| P0342 | 90 | 3654–3656 | 198 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0343 | 90 | 3657–3666 | 247 | -4.05 | T5 | Cosmological | 0.4 | 2.4 |
| P0344 | 90 | 3667–3669 | 263 | -4.56 | T5 | Cosmological | 0.0 | 2.3 |
| P0345 | 90 | 3675–3676 | 202 | -1.98 | T5 | Cosmological | 0.0 | 1.0 |
| P0346 | 90 | 3677–3679 | 237 | -1.69 | T5 | Cosmological | 0.0 | 0.8 |
| P0347 | 90 | 3685–3687 | 204 | -0.98 | T5 | Cosmological | 1.5 | 2.0 |
| P0348 | 91 | 3703–3704 | 275 | -3.64 | T5 | Cosmological | 0.0 | 1.8 |
| P0349 | 91 | 3711–3713 | 357 | -6.16 | T5 | Cosmological | 0.0 | 3.1 |
| P0350 | 91 | 3714–3723 | 213 | -2.82 | T5 | Cosmological | 0.5 | 1.9 |
| P0351 | 91 | 3724–3726 | 290 | -7.59 | T5 | Cosmological | 0.0 | 3.8 |
| P0352 | 91 | 3732–3734 | 308 | -3.25 | T5 | Cosmological | 1.0 | 2.6 |
| P0353 | 91 | 3735–3741 | 382 | -6.28 | T5 | Cosmological | 0.3 | 3.4 |
| P0354 | 91 | 3742–3743 | 234 | -1.71 | T5 | Cosmological | 0.4 | 1.3 |
| P0355 | 91 | 3749–3751 | 138 | -4.35 | T5 | Cosmological | 0.0 | 2.2 |
| P0356 | 92 | 3755–3756 | 128 | -10.94 | T5 | Cosmological | 0.8 | 6.2 |
| P0357 | 92 | 3757–3764 | 227 | -1.76 | T5 | Cosmological | 0.4 | 1.3 |
| P0358 | 92 | 3765–3766 | 180 | -8.89 | T5 | Cosmological | 0.0 | 4.4 |
| P0359 | 93 | 3779–3782 | 320 | -2.50 | T5 | Cosmological | 0.6 | 1.9 |
| P0360 | 93 | 3788–3790 | 223 | -0.90 | T5 | Cosmological | 0.0 | 0.4 |
| P0361 | 93 | 3791–3793 | 228 | -2.63 | T5 | Cosmological | 0.9 | 2.2 |
| P0362 | 93 | 3799–3800 | 59 | -3.39 | T5 | Cosmological | 1.7 | 3.4 |
| P0363 | 94 | 3806–3815 | 212 | +1.89 | T3 | Cosmological | 0.9 | 0.0 |
| P0364 | 94 | 3816–3818 | 146 | +5.48 | T1 | Cosmological | 3.4 | 0.7 |
| P0365 | 95 | 3835–3838 | 260 | +0.00 | T4 | Cosmological | 0.4 | 0.4 |
| P0366 | 95 | 3839–3847 | 207 | +1.93 | T3 | Cosmological | 1.0 | 0.0 |
| P0367 | 95 | 3848–3851 | 237 | +1.69 | T3 | Cosmological | 0.8 | 0.0 |
| P0368 | 95 | 3857–3859 | 192 | +3.12 | T2 | Cosmological | 1.6 | 0.0 |
| P0369 | 95 | 3860–3861 | 211 | +2.84 | T2 | Cosmological | 1.4 | 0.0 |
| P0370 | 95 | 3868–3869 | 173 | +1.16 | T3 | Cosmological | 0.6 | 0.0 |
| P0371 | 96 | 3874–3884 | 267 | +0.00 | T4 | Cosmological | 1.1 | 1.1 |
| P0372 | 96 | 3885–3885 | 198 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0373 | 97 | 3894–3895 | 262 | -0.76 | T5 | Cosmological | 0.0 | 0.4 |
| P0374 | 97 | 3896–3897 | 108 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0375 | 97 | 3903–3906 | 282 | -0.71 | T5 | Cosmological | 0.0 | 0.4 |
| P0376 | 98 | 3919–3921 | 193 | +1.04 | T3 | Cosmological | 0.5 | 0.0 |
| P0377 | 98 | 3922–3929 | 242 | +1.65 | T3 | Cosmological | 1.2 | 0.4 |
| P0378 | 98 | 3930–3930 | 34 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0379 | 99 | 3935–3943 | 271 | -1.48 | T5 | Cosmological | 0.0 | 0.7 |
| P0380 | 99 | 3944–3944 | 166 | -2.41 | T5 | Cosmological | 0.6 | 1.8 |
| P0381 | 99 | 3945–3945 | 25 | -8.00 | T5 | Cosmological | 0.0 | 4.0 |
| P0382 | 100 | 3955–3957 | 192 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0383 | 100 | 3958–3966 | 204 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0384 | 100 | 3967–3969 | 154 | -1.30 | T5 | Cosmological | 0.0 | 0.6 |
| P0385 | 101 | 3984–3984 | 195 | +0.00 | T4 | Cosmological | 0.5 | 0.5 |
| P0386 | 101 | 3985–3986 | 204 | +1.96 | T3 | Cosmological | 1.0 | 0.0 |
| P0387 | 101 | 3992–3993 | 146 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0388 | 102 | 3998–4005 | 210 | -1.91 | T5 | Cosmological | 1.0 | 1.9 |
| P0389 | 102 | 4006–4009 | 208 | -1.92 | T5 | Cosmological | 0.0 | 1.0 |
| P0390 | 102 | 4010–4012 | 106 | +1.89 | T3 | Cosmological | 0.9 | 0.0 |
| P0391 | 103 | 4022–4030 | 227 | +0.00 | T4 | Cosmological | 1.3 | 1.3 |
| P0392 | 104 | 4040–4045 | 183 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0393 | 105 | 4055–4068 | 285 | -1.23 | T5 | Cosmological | 0.0 | 0.4 |
| P0394 | 106 | 4073–4076 | 195 | +1.03 | T3 | Cosmological | 0.5 | 0.0 |
| P0395 | 106 | 4077–4085 | 158 | +2.53 | T2 | Cosmological | 1.3 | 0.0 |
| P0396 | 107 | 4090–4092 | 166 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0397 | 108 | 4102–4104 | 212 | +3.30 | T2 | Cosmological | 0.9 | 0.0 |
| P0398 | 109 | 4116–4124 | 327 | +0.61 | T3 | Cosmological | 0.6 | 0.3 |
| P0399 | 109 | 4125–4127 | 223 | -1.79 | T5 | Cosmological | 0.0 | 0.9 |
| P0400 | 109 | 4128–4137 | 55 | +0.00 | T4 | Cosmological | 1.8 | 1.8 |
| P0401 | 110 | 4142–4142 | 123 | +1.63 | T3 | Cosmological | 0.8 | 0.0 |
| P0402 | 111 | 4147–4155 | 194 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0403 | 112 | 4170–4171 | 258 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0404 | 112 | 4172–4181 | 222 | +0.90 | T3 | Cosmological | 0.5 | 0.0 |
| P0405 | 112 | 4182–4186 | 200 | +1.00 | T3 | Cosmological | 0.5 | 0.0 |
| P0406 | 112 | 4187–4196 | 133 | +1.50 | T3 | Cosmological | 0.8 | 0.0 |
| P0407 | 113 | 4202–4202 | 152 | +2.63 | T2 | Cosmological | 1.3 | 0.0 |
| P0408 | 114 | 4213–4217 | 181 | +3.32 | T2 | Cosmological | 2.2 | 0.6 |
| P0409 | 114 | 4218–4226 | 203 | +2.95 | T2 | Cosmological | 2.0 | 0.5 |
| P0410 | 114 | 4227–4227 | 59 | +3.39 | T2 | Cosmological | 1.7 | 0.0 |
| P0411 | 115 | 4244–4248 | 105 | -5.71 | T5 | Cosmological | 1.9 | 4.8 |
| P0412 | 115 | 4249–4252 | 203 | -3.94 | T5 | Cosmological | 0.0 | 2.0 |
| P0413 | 115 | 4258–4260 | 222 | -2.70 | T5 | Cosmological | 0.0 | 1.4 |
| P0414 | 115 | 4261–4269 | 223 | +5.38 | T1 | Cosmological | 3.1 | 0.4 |
| P0415 | 115 | 4270–4273 | 201 | +6.97 | T1 | Cosmological | 3.5 | 0.0 |
| P0416 | 115 | 4274–4281 | 214 | +5.61 | T1 | Cosmological | 3.7 | 0.9 |
| P0417 | 115 | 4282–4284 | 227 | +0.88 | T3 | Cosmological | 1.8 | 1.3 |
| P0418 | 115 | 4285–4285 | 35 | +5.71 | T1 | Cosmological | 2.9 | 0.0 |
| P0419 | 115 | 4286–4294 | 276 | -0.72 | T5 | Cosmological | 1.1 | 1.4 |
| P0420 | 115 | 4295–4296 | 212 | +1.89 | T3 | Cosmological | 1.4 | 0.5 |
| P0421 | 115 | 4297–4307 | 232 | -3.45 | T5 | Cosmological | 1.3 | 3.0 |
| P0422 | 115 | 4308–4309 | 225 | -4.45 | T5 | Cosmological | 0.4 | 2.7 |
| P0423 | 115 | 4310–4317 | 187 | -1.07 | T5 | Cosmological | 0.0 | 0.5 |
| P0424 | 115 | 4318–4320 | 239 | -2.51 | T5 | Cosmological | 1.7 | 2.9 |
| P0425 | 115 | 4321–4329 | 174 | -4.60 | T5 | Cosmological | 0.6 | 2.9 |
| P0426 | 116 | 4334–4336 | 202 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0427 | 116 | 4344–4345 | 150 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0428 | 117 | 4350–4353 | 135 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0429 | 119 | 4369–4379 | 342 | -1.17 | T5 | Cosmological | 1.5 | 2.0 |
| P0430 | 119 | 4380–4389 | 188 | +1.06 | T3 | Cosmological | 1.1 | 0.5 |
| P0431 | 120 | 4395–4404 | 241 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0432 | 120 | 4405–4406 | 209 | -1.91 | T5 | Cosmological | 0.0 | 1.0 |
| P0433 | 120 | 4407–4408 | 152 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0434 | 121 | 4421–4423 | 274 | +0.73 | T3 | Cosmological | 0.4 | 0.0 |
| P0435 | 121 | 4430–4432 | 239 | -2.51 | T5 | Cosmological | 0.4 | 1.7 |
| P0436 | 121 | 4433–4433 | 123 | +1.63 | T3 | Cosmological | 0.8 | 0.0 |
| P0437 | 122 | 4447–4455 | 400 | -0.50 | T4 | Cosmological | 1.8 | 2.0 |
| P0438 | 122 | 4456–4457 | 259 | +0.77 | T3 | Cosmological | 0.4 | 0.0 |
| P0439 | 122 | 4463–4464 | 339 | -2.36 | T5 | Cosmological | 0.0 | 1.2 |
| P0440 | 122 | 4465–4477 | 175 | +2.29 | T2 | Core Cosmological | 1.1 | 0.0 |
| P0441 | 122 | 4478–4496 | 202 | +5.45 | T1 | Core Cosmological | 3.0 | 0.0 |
| P0442 | 122 | 4497–4517 | 199 | +2.01 | T2 | Core Cosmological | 1.0 | 0.0 |
| P0443 | 122 | 4518–4538 | 218 | +19.27 | T1 | Core Cosmological | 9.2 | 0.9 |
| P0444 | 122 | 4539–4555 | 199 | +5.53 | T1 | Core Cosmological | 2.5 | 0.5 |
| P0445 | 122 | 4556–4575 | 200 | +6.00 | T1 | Core Cosmological | 3.0 | 0.0 |
| P0446 | 122 | 4576–4603 | 201 | +7.96 | T1 | Core Cosmological | 4.0 | 0.0 |
| P0447 | 122 | 4604–4629 | 202 | -0.49 | T4 | Core Cosmological | 0.5 | 0.0 |
| P0448 | 122 | 4630–4639 | 196 | +4.59 | T1 | Core Cosmological | 1.5 | 0.0 |
| P0449 | 122 | 4640–4662 | 201 | +1.00 | T3 | Core Cosmological | 0.5 | 0.0 |
| P0450 | 122 | 4663–4679 | 205 | +6.83 | T1 | Core Cosmological | 4.4 | 1.0 |
| P0451 | 122 | 4680–4699 | 199 | +4.02 | T1 | Core Cosmological | 2.5 | 0.5 |
| P0452 | 122 | 4704–4712 | 200 | +4.00 | T1 | Core Cosmological | 2.0 | 0.0 |
| P0453 | 122 | 4713–4723 | 202 | +3.96 | T2 | Core Cosmological | 2.5 | 0.5 |
| P0454 | 122 | 4728–4750 | 203 | +3.69 | T2 | Core Cosmological | 3.0 | 0.0 |
| P0455 | 122 | 4751–4774 | 205 | +0.98 | T3 | Core Cosmological | 0.5 | 0.0 |
| P0456 | 122 | 4775–4788 | 202 | +3.96 | T2 | Core Cosmological | 2.0 | 0.0 |
| P0457 | 122 | 4789–4813 | 200 | +7.00 | T1 | Core Cosmological | 3.5 | 0.0 |
| P0458 | 122 | 4814–4838 | 197 | +2.28 | T2 | Core Cosmological | 1.5 | 0.0 |
| P0459 | 122 | 4839–4859 | 200 | -2.00 | T5 | Core Cosmological | 0.0 | 0.0 |
| P0460 | 122 | 4860–4898 | 200 | -0.75 | T5 | Core Cosmological | 0.0 | 0.0 |
| P0461 | 122 | 4899–4952 | 215 | -2.56 | T5 | Core Cosmological | 0.0 | 0.9 |
| P0462 | 122 | 4953–4960 | 187 | -0.80 | T5 | Cosmological | 0.0 | 0.0 |
| P0463 | 122 | 4961–4968 | 193 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0464 | 122 | 4972–4979 | 187 | -1.60 | T5 | Cosmological | 0.0 | 0.0 |
| P0465 | 122 | 4980–4989 | 190 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
| P0466 | 122 | 4990–4990 | 22 | +0.00 | T4 | Cosmological | 0.0 | 0.0 |
