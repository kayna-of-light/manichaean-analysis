# Kephalaia Layer Analysis v4 — Temporal-Axis Results

**Date**: 2026-02-16
**Data Source**: LLM-cleaned structured JSON (output/cleaned/chapters/)
**Chapters analyzed**: 123
**Total teaching words**: 83,698
**Total paragraphs**: 1429

---

## 1. Tier Classification Summary

| Tier | Count | % | Description |
|------|------:|--:|-------------|
| Core | 4 | 3.3% | Strong teaching substrate + structural markers, minimal overlay |
| Secondary | 56 | 45.5% | Teaching dominant with some overlay present |
| Mixed | 24 | 19.5% | Both teaching and overlay vocabulary present |
| Pastoral | 26 | 21.1% | Institutional/overlay vocabulary dominant — later layer |
| Hagiographic | 2 | 1.6% | Biographical/veneration material dominant |
| Peripheral | 11 | 8.9% | Low vocabulary signal — inconclusive |
| Fragmentary | 0 | 0.0% | Too short for reliable analysis (<30 words) |

## 2. Agreement with Manual Layer 1 Extract

| Metric | Value |
|--------|-------|
| Manual Layer 1 chapters | 21 |
| Computed Core+Secondary | 60 |
| True Positive | 12 |
| True Negative | 54 |
| False Positive (computed core, manual excluded) | 48 |
| False Negative (computed other, manual included) | 9 |
| **Agreement** | **53.7%** |
| **Cohen's κ** | **0.058** |

### False Negatives (in manual extract but not computed core/secondary)

- **Ch. 2** (The Second, concerning the Parable of the Tree.): tier=mixed, score=0.51, cosmo=1.24, pastoral=0.51
- **Ch. 40** (Concerning the Three Things that were established ): tier=mixed, score=0.69, cosmo=1.37, pastoral=0.68
- **Ch. 56** ([Concerning Saklas and his Powers]): tier=mixed, score=0.23, cosmo=0.78, pastoral=0.46
- **Ch. 75** ([Concerning the Letter (?)]): tier=peripheral, score=-1.76, cosmo=3.02, pastoral=2.27
- **Ch. 85** (Concerning the Cross of Light: [...] trample upon ): tier=pastoral, score=-3.02, cosmo=0.63, pastoral=1.60
- **Ch. 86** (The Chapter of the Man who asks: Why [am] I someti): tier=peripheral, score=-0.66, cosmo=0.38, pastoral=0.28
- **Ch. 109** (Concerning the Fifty Lord's Days; to what Mysterie): tier=pastoral, score=-1.55, cosmo=0.73, pastoral=1.09
- **Ch. 115** (The Catechumen asks the Apostle: will Rest come ab): tier=peripheral, score=-1.29, cosmo=1.89, pastoral=1.93
- **Ch. 122** (Concerning the 'Assent' and the 'Amen'): tier=peripheral, score=-0.83, cosmo=1.22, pastoral=1.33

### Candidates for Restoration (computed core/secondary, not in manual extract)

- **Ch. 20** (The Chapter of the Name of the Fathers): tier=secondary, score=9.47
  - Cosmological: father of greatness x4, third ambassador x1, living fire x1, ship of living waters x1, ship of living fire x1, living water x1
- **Ch. 53** (Concerning the First Man.): tier=secondary, score=9.38
  - Cosmological: first man x3, living spirit x1, living fire x1, land of darkness x3, thought of death x1, storehouses x6, rulers x1, elements x1
- **Ch. 15** ([Concerning the ... ...] Five [Parts ...] Worlds o): tier=secondary, score=7.89
  - Cosmological: first man x4, land of darkness x3, five elements x2, five worlds x3, five trees x1, elements x2, zodiac x1
- **Ch. 10** (Concerning the Interpretation of the Fourteen [Gre): tier=core, score=6.54
  - Cosmological: first man x2, living spirit x2, five sons x1, five elements x1, aeons x6
- **Ch. 4** (Concerning the Four Great Days that have come fort): tier=core, score=5.92
  - Cosmological: first man x3, living spirit x3, third ambassador x1, five sons x2, land of darkness x2, old man x3, pillar of glory x1, five elements x2
- **Ch. 18** ([Concerning the Five] War[s that the] Sons of [Li]): tier=core, score=5.57
  - Cosmological: living spirit x3, third ambassador x2, living soul x1, living fire x1, five elements x1, five worlds x1, five trees x1, three vessels x1
- **Ch. 45** (Concerning the Vessels): tier=secondary, score=5.34
  - Cosmological: adamant of light x1, vessels x1, fashioned x2, constructed x7, discharged x2
- **Ch. 22** ([On] the Land of Light): tier=secondary, score=4.74
  - Cosmological: land of light x2, aeons x1
- **Ch. 19** (Concerning the Five Releases: what they are): tier=secondary, score=4.24
  - Cosmological: first man x7, living spirit x3, mother of life x1, third ambassador x2, firmaments x1, aeons x1, rulers x2, constructed x2
- **Ch. 37** (Concerning the Three Zones.): tier=secondary, score=4.14
  - Cosmological: living spirit x2, king of honour x1, five sons x1, firmaments x1, constructed x1
- **Ch. 32** (Concerning the Seven Works of the Living Spirit): tier=secondary, score=3.99
  - Cosmological: first man x1, living spirit x2, five sons x1, ships of light x1, three vessels x1, aeons x1, constructed x2, crucified x1
- **Ch. 21** ([C]oncerning the Father of Gr[eat]ness: [ho]w he i): tier=secondary, score=3.95
  - Cosmological: father of greatness x1, land of light x1, storehouses x1, aeons x2
- **Ch. 36** (Concerning the Wheel that exists in front of the K): tier=secondary, score=3.95
  - Cosmological: king of honour x4, firmaments x1, rulers x3, mixture x1
- **Ch. 54** ([Concerning] the Quality of the Garments): tier=secondary, score=3.85
  - Cosmological: first man x1, living spirit x3, mother of life x1, third ambassador x1, five sons x1, ships of light x1, wheel of the stars x1, ten firmaments x1
- **Ch. 24** ([... / ...]): tier=secondary, score=3.81
  - Cosmological: first man x7, living spirit x1, mother of life x4, father of greatness x4, virgin of light x1, great builder x1, land of light x1, great fire x1
- **Ch. 17** (The Chapter of the Three Seasons): tier=secondary, score=3.56
  - Cosmological: first man x10, living spirit x2, mother of life x3, third ambassador x1, land of darkness x1, land of light x1, constructed x1, crucified x1
- **Ch. 29** (Concerning the Eighteen Great Thrones of all the F): tier=secondary, score=3.51
  - Cosmological: first man x3, living spirit x2, mother of life x1, third ambassador x1, virgin of light x1, great builder x1, beloved of the lights x1, king of honour x2
- **Ch. 14** (The Interpretation [of] the S[i]lence, the Fast, [): tier=secondary, score=3.43
  - Cosmological: first man x1, ship of living waters x1, living water x1, pillar of glory x1
- **Ch. 43** (Concerning the Vessels.): tier=secondary, score=3.35
  - Cosmological: three vessels x3, porter x1, firmaments x3, rulers x1, vessels x5, constructed x1, discharged x9
- **Ch. 64** ([Concerning Adam]): tier=secondary, score=3.28
  - Cosmological: five sons x1, rulers x1, zodiac x1
- **Ch. 23** ([ ... ] which [ ... ]): tier=secondary, score=3.21
  - Cosmological: first man x3, father of greatness x1, land of darkness x2, land of light x1, land of the living x1, five garments x1, five dark x1, storehouses x1
- **Ch. 28** ([Concerning the T]welve Judges [of] the Father): tier=secondary, score=3.19
  - Cosmological: first man x3, living spirit x1, mother of life x1, father of greatness x1, third ambassador x1, light mind x1, virgin of light x1, great builder x1
- **Ch. 26** (Concerning the First Man and the Ambassador and th): tier=secondary, score=3.18
  - Cosmological: first man x3, living spirit x1, living soul x1, great spirit x1
- **Ch. 42** (Concerning the Three Vessels): tier=secondary, score=3.17
  - Cosmological: living spirit x3, living fire x1, garment of wind x1, garment of water x1, great fire x1, three vessels x3, firmaments x2, aeons x2
- **Ch. 44** (Concerning the Sea Giant): tier=secondary, score=3.11
  - Cosmological: living spirit x1, king of glory x1, three wheels x1, three vessels x3, wheel of the stars x1, ten firmaments x1, firmaments x1, zodiac x3
- **Ch. 110** (Concerning the Nourishment of the Person, for ther): tier=secondary, score=2.78
  - Cosmological: rulers x2
- **Ch. 16** ([Concerning the Five] Greatnesses who [went forth]): tier=secondary, score=2.68
  - Cosmological: first man x13, living spirit x11, mother of life x2, father of greatness x1, third ambassador x3, great builder x1, beloved of the lights x1, five sons x4
- **Ch. 5** (Concerning Four Hunters of Light and Four of Darkn): tier=secondary, score=2.68
  - Cosmological: first man x1, living spirit x1, third ambassador x1, living soul x3, land of darkness x1, great fire x2, five elements x1, five storehouses x1
- **Ch. 108** (Concerning the Seed Grain that shall be formed by ): tier=secondary, score=2.62
  - Cosmological: five elements x1, elements x1
- **Ch. 31** (Concerning the Summons, in which Limb of the Soul ): tier=secondary, score=2.45
  - Cosmological: first man x2, virgin of light x2, living soul x4, pillar of glory x1
- **Ch. 50** (Concerning these Names: God, Rich One, and Angel; ): tier=secondary, score=2.16
  - Cosmological: beloved of the lights x1, land of light x2, great spirit x1, emanations x1, entangled x1
- **Ch. 51** (Concerning the First Man.): tier=secondary, score=2.10
  - Cosmological: first man x1, living fire x4
- **Ch. 113** (The Chapter on whether any [Lig]ht comes from the ): tier=secondary, score=2.08
  - Cosmological: living ones x1, three vessels x1, firmaments x1, vessels x1
- **Ch. 25** ([Concerning the Advent of Five Fathers from the Fi): tier=secondary, score=1.79
  - Cosmological: mother of life x1, virgin of light x1, beloved of the lights x1, five limbs x1
- **Ch. 33** (Concerning the Five Things that he constructed wit): tier=secondary, score=1.69
  - Cosmological: living spirit x1, porter x1, constructed x1
- **Ch. 48** (Concerning the Conduits.): tier=secondary, score=1.68
  - Cosmological: living spirit x2, living soul x1, five worlds x3, five trees x1, wheel of the stars x1, firmaments x4, elements x1, zodiac x3
- **Ch. 94** (Concerning the Purification of these Four Elements): tier=secondary, score=1.67
  - Cosmological: light mind x1, land of the living x1, living ones x2, new man x1, elements x2
- **Ch. 95** (The Apostle asks his Disciples: What is Cloud?): tier=secondary, score=1.67
  - Cosmological: virgin of light x3, porter x1, rulers x11, mingled x1
- **Ch. 9** (The Explanation of the Peace, what it is; the Righ): tier=secondary, score=1.59
  - Cosmological: first man x14, living spirit x2, mother of life x3, light mind x3, land of light x2, living ones x1, light form x3, storehouses x1
- **Ch. 7** (The Seventh, concerning the Five Fathers): tier=secondary, score=1.55
  - Cosmological: father of greatness x1, third ambassador x2, light mind x2, virgin of light x1, beloved of the lights x1, light form x3, pillar of glory x1, perfect man x1
- **Ch. 106** (There is no Joy that shall remain in the World til): tier=secondary, score=1.37
  - Cosmological: living soul x3
- **Ch. 12** (Concerning the Interpretation of the Five Words th): tier=secondary, score=1.35
  - Cosmological: third ambassador x1
- **Ch. 69** (Concerning the Twelve Signs of the Zodiac and the ): tier=secondary, score=1.34
  - Cosmological: land of darkness x1, five worlds x3, rulers x1, zodiac x2, fashioned x1
- **Ch. 35** (Concerning the Four Works of the Ambassador): tier=secondary, score=1.30
  - Cosmological: living soul x1, firmaments x1
- **Ch. 27** (Concerning the Five Forms that exist in the Rulers): tier=secondary, score=1.27
  - Cosmological: five worlds x2, fashioned x1
- **Ch. 49** (Concerning the Wheel and the Conduits): tier=secondary, score=1.23
  - Cosmological: entangled x2
- **Ch. 34** (Concerning the Ten Things that the Ambassador bega): tier=secondary, score=1.14
  - Cosmological: third ambassador x1, great builder x1, rulers x1
- **Ch. 8** (Concerning the Fourteen Vehicles that Jesus has bo): tier=secondary, score=0.44
  - Cosmological: first man x1, living fire x1, living water x1, pillar of glory x1, perfect man x1

---

## 3. Strongest Teaching Substrate Chapters (by Temporal Composite)

| Rank | Ch. | Title | Score | Teaching | Overlay | Purity | Corr | Struct | Tier | Manual |
|------|-----|-------|------:|---------:|--------:|-------:|-----:|-------:|------|:------:|
| 1 | 20 | The Chapter of the Name of the Fath | 9.47 | 7.69 | 1.78 | 0.81 | 0 | 0 | secondary |  |
| 2 | 53 | Concerning the First Man. | 9.38 | 6.52 | 0.54 | 0.92 | 0 | 0 | secondary |  |
| 3 | 15 | [Concerning the ... ...] Five [Part | 7.89 | 5.53 | 0.53 | 0.91 | 0 | 0 | secondary |  |
| 4 | 10 | Concerning the Interpretation of th | 6.54 | 5.03 | 0.67 | 0.88 | 1 | 0 | core |  |
| 5 | 4 | Concerning the Four Great Days that | 5.92 | 4.22 | 0.35 | 0.92 | 2 | 0 | core |  |
| 6 | 71 | Concerning the Gathering in of the  | 5.72 | 4.58 | 0.76 | 0.86 | 0 | 0 | secondary | ✅ |
| 7 | 18 | [Concerning the Five] War[s that th | 5.57 | 4.06 | 0.35 | 0.92 | 1 | 0 | core |  |
| 8 | 45 | Concerning the Vessels | 5.34 | 3.56 | 0.00 | 1.00 | 0 | 0 | secondary |  |
| 9 | 22 | [On] the Land of Light | 4.74 | 2.84 | 0.00 | 1.00 | 0 | 0 | secondary |  |
| 10 | 114 | Concerning the Three Images that ar | 4.54 | 3.69 | 0.49 | 0.88 | 0 | 1 | core | ✅ |
| 11 | 19 | Concerning the Five Releases: what  | 4.24 | 3.99 | 0.83 | 0.83 | 0 | 0 | secondary |  |
| 12 | 37 | Concerning the Three Zones. | 4.14 | 4.14 | 1.38 | 0.75 | 0 | 0 | secondary |  |
| 13 | 55 | Concerning the Fashioning of Adam | 4.11 | 2.91 | 0.17 | 0.94 | 0 | 0 | secondary | ✅ |
| 14 | 32 | Concerning the Seven Works of the L | 3.99 | 3.32 | 0.66 | 0.83 | 0 | 0 | secondary |  |
| 15 | 74 | Concerning the living Fire: It is p | 3.98 | 2.95 | 0.29 | 0.91 | 0 | 1 | secondary | ✅ |
| 16 | 21 | [C]oncerning the Father of Gr[eat]n | 3.95 | 2.77 | 0.40 | 0.87 | 0 | 1 | secondary |  |
| 17 | 36 | Concerning the Wheel that exists in | 3.95 | 2.92 | 0.29 | 0.91 | 0 | 0 | secondary |  |
| 18 | 54 | [Concerning] the Quality of the Gar | 3.85 | 3.04 | 0.47 | 0.86 | 0 | 0 | secondary |  |
| 19 | 24 | [... / ...] | 3.81 | 2.52 | 0.06 | 0.97 | 1 | 1 | secondary |  |
| 20 | 17 | The Chapter of the Three Seasons | 3.56 | 3.42 | 0.96 | 0.78 | 0 | 1 | secondary |  |
| 21 | 29 | Concerning the Eighteen Great Thron | 3.51 | 3.42 | 0.86 | 0.80 | 0 | 2 | secondary |  |
| 22 | 70 | Concerning the Body: It was constru | 3.46 | 2.73 | 0.34 | 0.89 | 2 | 0 | secondary | ✅ |
| 23 | 14 | The Interpretation [of] the S[i]len | 3.43 | 2.29 | 0.00 | 1.00 | 0 | 0 | secondary |  |
| 24 | 43 | Concerning the Vessels. | 3.35 | 2.75 | 0.36 | 0.88 | 0 | 0 | secondary |  |
| 25 | 64 | [Concerning Adam] | 3.28 | 2.18 | 0.00 | 1.00 | 1 | 0 | secondary |  |

## 4. Strongest Overlay Chapters (by Temporal Composite)

| Rank | Ch. | Title | Score | Pastoral | NT | Hagio | Teaching | Tier |
|------|-----|-------|------:|---------:|---:|------:|---------:|------|
| 1 | 80 | The Chapter of the Commandments of Right | -9.45 | 4.20 | 0.42 | 0.21 | 0.21 | pastoral |
| 2 | 91 | Also concerning the Catechumen; shall he | -6.25 | 3.33 | 0.10 | 0.00 | 0.43 | pastoral |
| 3 | 87 | Concerning the Alms, that [ ... ] life i | -5.87 | 4.88 | 0.00 | 0.00 | 2.59 | pastoral |
| 4 | 79 | Concerning the Fasting of the Saints | -5.41 | 2.70 | 0.00 | 0.45 | 0.45 | pastoral |
| 5 | 67 | Concerning the Light-Giver. | -5.30 | 1.69 | 0.00 | 0.00 | 0.42 | pastoral |
| 6 | 77 | The Chapter of the Four Kingdoms | -4.50 | 1.70 | 0.00 | 0.24 | 0.00 | pastoral |
| 7 | 81 | The Chapter of Fasting, for it engenders | -4.31 | 1.71 | 0.19 | 0.09 | 0.09 | pastoral |
| 8 | 92 | The Apostle is asked: Why when you drew  | -4.24 | 3.01 | 0.00 | 0.00 | 1.09 | pastoral |
| 9 | 99 | Concerning Transmigration | -3.62 | 2.00 | 0.00 | 0.00 | 0.25 | pastoral |
| 10 | 90 | Concerning the Fifteen Paths; and whethe | -3.32 | 1.66 | 0.21 | 0.07 | 0.41 | pastoral |
| 11 | 105 | Concerning the Three Things that are gre | -3.27 | 0.38 | 0.77 | 0.00 | 0.00 | pastoral |
| 12 | 93 | A Catechumen asked the Apostle: When I w | -3.21 | 2.23 | 0.00 | 0.00 | 0.84 | pastoral |
| 13 | 85 | Concerning the Cross of Light: [...] tra | -3.02 | 1.60 | 0.00 | 0.00 | 0.68 | pastoral |
| 14 | 30 | Concerning the Three Garments | -2.87 | 0.57 | 0.00 | 0.00 | 0.57 | peripheral |
| 15 | 1 | Concerning the Ad[vent] of the Apostle. | -2.76 | 0.97 | 0.34 | 0.04 | 0.17 | pastoral |
| 16 | 103 | Concerning the Five Wonders that the Lig | -2.21 | 1.47 | 0.00 | 0.49 | 1.47 | pastoral |
| 17 | 102 | Concerning the Light Mind, why it does n | -2.09 | 1.25 | 0.21 | 0.00 | 0.63 | pastoral |
| 18 | 120 | Concerning the Two Essences | -1.91 | 0.38 | 0.00 | 0.00 | 0.38 | peripheral |
| 19 | 82 | The Chapter of Righteous [Judgement] | -1.87 | 0.77 | 0.00 | 0.11 | 0.00 | pastoral |
| 20 | 89 | The Chapter of the Nazorean who question | -1.81 | 0.60 | 0.15 | 0.15 | 0.00 | pastoral |

## 5. Editor Fatigue — Highest Intra-Chapter Shifts

| Ch. | Title | Shift | 1st Cosmo | 2nd Cosmo | 1st Pastoral | 2nd Pastoral |
|-----|-------|------:|----------:|----------:|-------------:|-------------:|
| 75 | [Concerning the Letter (?)] | 10.076 | 5.56 | 0.00 | 0.00 | 4.52 |
| 33 | Concerning the Five Things that he  | 6.818 | 6.82 | 0.00 | 0.00 | 0.00 |
| 53 | Concerning the First Man. | 5.978 | 8.70 | 2.72 | 0.00 | 0.00 |
| 80 | The Chapter of the Commandments of  | 4.622 | 0.42 | 0.00 | 2.10 | 6.30 |
| 18 | [Concerning the Five] War[s that th | 4.594 | 5.30 | 1.06 | 0.00 | 0.35 |
| 51 | Concerning the First Man. | 4.580 | 3.82 | 0.00 | 0.00 | 0.76 |
| 92 | The Apostle is asked: Why when you  | 4.372 | 1.09 | 0.55 | 1.09 | 4.92 |
| 32 | Concerning the Seven Works of the L | 4.009 | 5.33 | 1.32 | 0.00 | 0.00 |
| 54 | [Concerning] the Quality of the Gar | 3.738 | 4.67 | 0.93 | 0.00 | 0.00 |
| 8 | Concerning the Fourteen Vehicles th | 3.502 | 2.92 | 0.00 | 0.58 | 1.16 |
| 9 | The Explanation of the Peace, what  | 3.244 | 3.02 | 1.01 | 0.22 | 0.67 |
| 115 | The Catechumen asks the Apostle: wi | 3.057 | 2.90 | 0.89 | 1.37 | 2.49 |
| 28 | [Concerning the T]welve Judges [of] | 2.867 | 4.17 | 2.08 | 0.00 | 0.52 |
| 26 | Concerning the First Man and the Am | 2.842 | 3.55 | 0.70 | 0.00 | 0.00 |
| 0 | Introduction | 2.838 | 1.35 | 0.00 | 0.00 | 0.81 |

## 6. Gardner Editorial Observations

| Ch. | Title | Flags |
|-----|-------|-------|
| 0 | Introduction | canonical_source |
| 1 | Concerning the Ad[vent] of the Apostle. | christian_connection, gnostic_connection, canonical_source |
| 2 | The Second, concerning the Parable of th | correspondential_signal |
| 4 | Concerning the Four Great Days that have | secondary_material, gnostic_connection, pentadic_structure |
| 6 | Concerning the Five Storehouses that hav | redaction, corruption, secondary_material, textual_development, uncertain, parallel_text, gnostic_connection, canonical_source, mandaean_parallel, pentadic_structure |
| 8 | Concerning the Fourteen Vehicles that Je | correspondential_signal |
| 10 | Concerning the Interpretation of the Fou | gnostic_connection |
| 12 | Concerning the Interpretation of the Fiv | uncertain, christian_connection, mandaean_parallel |
| 13 | Concerning the Five Saviours, the Resurr | pentadic_structure |
| 14 | The Interpretation [of] the S[i]lence, t | cosmological_content |
| 15 | [Concerning the ... ...] Five [Parts ... | pentadic_structure, correspondential_signal |
| 16 | [Concerning the Five] Greatnesses who [w | pentadic_structure, correspondential_signal |
| 18 | [Concerning the Five] War[s that the] So | cosmological_content |
| 19 | Concerning the Five Releases: what they  | correspondential_signal |
| 24 | [... / ...] | uncertain |
| 26 | Concerning the First Man and the Ambassa | uncertain |
| 38 | Concerning the Light Mind and the Apostl | correspondential_signal |
| 41 | Concerning the Three Blows that befell t | redaction |
| 48 | Concerning the Conduits. | uncertain |
| 58 | The Four Powers that grieve | christian_connection, gnostic_connection |
| 61 | Concerning the Garment of the Waters: ho | cosmological_content |
| 65 | Concerning the Sun. | redaction, correspondential_signal |
| 69 | Concerning the Twelve Signs of the Zodia | gnostic_connection, pentadic_structure |
| 70 | Concerning the Body: It was constructed  | redaction, correspondential_signal |
| 71 | Concerning the Gathering in of the [E]le | correspondential_signal |
| 73 | Concerning the Envy of Matter | mani_attribution |
| 75 | [Concerning the Letter (?)] | liturgical_connection |
| 80 | The Chapter of the Commandments of Right | correspondential_signal |
| 82 | The Chapter of Righteous [Judgement] | correspondential_signal |
| 83 | Concerning the Man who is ugly in his Bo | christian_connection |
| 86 | The Chapter of the Man who asks: Why [am | buddhist_connection |
| 89 | The Chapter of the Nazorean who question | christian_connection |
| 90 | Concerning the Fifteen Paths; and whethe | redaction, buddhist_connection |
| 93 | A Catechumen asked the Apostle: When I w | uncertain |
| 94 | Concerning the Purification of these Fou | uncertain |
| 95 | The Apostle asks his Disciples: What is  | correspondential_signal |
| 101 | [Concer]ning why, if the Person shall lo | redaction, textual_development, correspondential_signal |
| 105 | Concerning the Three Things that are gre | christian_connection |
| 109 | Concerning the Fifty Lord's Days; to wha | correspondential_signal |
| 112 | The Human is less than all the Things of | cosmological_content |
| 113 | The Chapter on whether any [Lig]ht comes | cosmological_content |
| 120 | Concerning the Two Essences | uncertain, christian_connection |
| 121 | Concerning the Sect of the Basket | uncertain, cosmological_content |
| 122 | Concerning the 'Assent' and the 'Amen' | christian_connection |

## 7. NT Citation Distribution (from Footnotes)

| Ch. | Title | NT Citations | Tier |
|-----|-------|-------------|------|
| 1 | Concerning the Ad[vent] of the Apostle. | Phil. 2, Jn. 1 | pastoral |
| 2 | The Second, concerning the Parable of th | Lk. 6, Lk. 2 | mixed |
| 7 | The Seventh, concerning the Five Fathers | Jn. 8 | secondary |
| 9 | The Explanation of the Peace, what it is | Mk. 1 | secondary |
| 18 | [Concerning the Five] War[s that the] So | Mt. 3 | core |
| 19 | Concerning the Five Releases: what they  | Phil. 2 | secondary |
| 63 | Concerning Love. | Jn. 1 | mixed |
| 75 | [Concerning the Letter (?)] | Mt. 2, Jn 1 | peripheral |
| 76 | [Conce]rning Lord Manichaios: how he jou | Jn. 3 | pastoral |
| 77 | The Chapter of the Four Kingdoms | Mt. 1 | pastoral |
| 82 | The Chapter of Righteous [Judgement] | Mt. 6 | pastoral |
| 83 | Concerning the Man who is ugly in his Bo | Mt. 1 | peripheral |
| 85 | Concerning the Cross of Light: [...] tra | Mt. 6 | pastoral |
| 89 | The Chapter of the Nazorean who question | Mt. 6 | pastoral |
| 91 | Also concerning the Catechumen; shall he | Mt. 6, 1 Cor. 7 | pastoral |
| 109 | Concerning the Fifty Lord's Days; to wha | Mt. 4, Mt. 2, Lk. 2 | pastoral |

## 8. Structural Patterns (Temporal Markers)

- Chapters with formulaic opening: **60** (49%)
- Chapters with formulaic closing: **11** (9%)
- Chapters with Q&A formula: **7** (6%)
- Chapters with correspondence markers: **26** (21%)

### Chapters with Highest Correspondence Marker Density

| Ch. | Title | Corr Markers | Enum Markers | Tier | Score |
|-----|-------|:------------:|:------------:|------|------:|
| 38 | Concerning the Light Mind and the Apostl | 3 | 0 | secondary | 0.95 |
| 4 | Concerning the Four Great Days that have | 2 | 0 | core | 5.92 |
| 6 | Concerning the Five Storehouses that hav | 2 | 2 | secondary | 1.65 |
| 7 | The Seventh, concerning the Five Fathers | 2 | 1 | secondary | 1.55 |
| 27 | Concerning the Five Forms that exist in  | 2 | 0 | secondary | 1.27 |
| 28 | [Concerning the T]welve Judges [of] the  | 2 | 0 | secondary | 3.19 |
| 42 | Concerning the Three Vessels | 2 | 2 | secondary | 3.17 |
| 50 | Concerning these Names: God, Rich One, a | 2 | 0 | secondary | 2.16 |
| 65 | Concerning the Sun. | 2 | 1 | mixed | -0.29 |
| 69 | Concerning the Twelve Signs of the Zodia | 2 | 0 | secondary | 1.34 |
| 70 | Concerning the Body: It was constructed  | 2 | 0 | secondary | 3.46 |
| 0 | Introduction | 1 | 0 | mixed | -0.37 |
| 2 | The Second, concerning the Parable of th | 1 | 0 | mixed | 0.51 |
| 9 | The Explanation of the Peace, what it is | 1 | 1 | secondary | 1.59 |
| 10 | Concerning the Interpretation of the Fou | 1 | 0 | core | 6.54 |

## 9. TF-IDF Cluster Profiles

Optimal k=2 (silhouette=0.0157)

### Cluster 0: Mixed (n=47)
- Avg composite: -1.19
- Top TF-IDF terms: shall, light, body, good, church, catechumen, person, elect, like, come
- Chapters: 1, 2, 13, 27, 49, 56, 65, 68, 71, 75, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 99, 102, 103, 104, 107, 108, 109, 110, 113, 114, 115, 116, 117, 120, 121, 122
- Avg densities: {'cosmological': 0.827, 'persian_substrate': 0.035, 'pastoral': 0.993, 'nt_christian': 0.087, 'hagiographic': 0.131, 'correspondential': 0.105, 'application_voice': 0.168}

### Cluster 1: Teaching Substrate (n=76)
- Avg composite: 2.03
- Top TF-IDF terms: light, great, father, darkness, man, living, time, came, earth, universe
- Chapters: 0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 50, 51, 52, 53, 54, 55, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 69, 70, 72, 73, 74, 76, 98, 100, 101, 105, 106, 111, 112, 118, 119
- Avg densities: {'cosmological': 1.922, 'persian_substrate': 0.146, 'pastoral': 0.275, 'nt_christian': 0.084, 'hagiographic': 0.263, 'correspondential': 0.201, 'application_voice': 0.194}

---

## Appendix: Full Chapter Data

| Ch. | Title | Words | Score | Teach | Overlay | Purity | Shift | Tier | Manual |
|-----|-------|------:|------:|------:|--------:|-------:|------:|------|:------:|
| 0 | Introduction | 1480 | -0.37 | 0.81 | 0.88 | 0.48 | 2.838 | mixed |  |
| 1 | Concerning the Ad[vent] o | 2376 | -2.76 | 0.17 | 1.47 | 0.10 | -0.589 | pastoral |  |
| 2 | The Second, concerning th | 1371 | 0.51 | 1.97 | 1.24 | 0.61 | -0.583 | mixed | ✅ |
| 3 | The Interpretation of Hap | 434 | 3.11 | 3.92 | 1.61 | 0.71 | 1.843 | secondary | ✅ |
| 4 | Concerning the Four Great | 853 | 5.92 | 4.22 | 0.35 | 0.92 | 1.649 | core |  |
| 5 | Concerning Four Hunters o | 710 | 2.68 | 2.82 | 0.84 | 0.77 | -0.845 | secondary |  |
| 6 | Concerning the Five Store | 1397 | 1.65 | 2.43 | 1.36 | 0.64 | 2.149 | secondary | ✅ |
| 7 | The Seventh, concerning t | 808 | 1.55 | 2.60 | 1.24 | 0.68 | 2.723 | secondary |  |
| 8 | Concerning the Fourteen V | 343 | 0.44 | 1.46 | 0.87 | 0.62 | 3.502 | secondary |  |
| 9 | The Explanation of the Pe | 1788 | 1.59 | 2.18 | 1.01 | 0.68 | 3.244 | secondary |  |
| 10 | Concerning the Interpreta | 298 | 6.54 | 5.03 | 0.67 | 0.88 | 2.685 | core |  |
| 11 | [Concerning the Interpret | 295 | -1.19 | 3.39 | 3.39 | 0.50 | -2.022 | peripheral |  |
| 12 | Concerning the Interpreta | 111 | 1.35 | 0.90 | 0.00 | 0.99 | -1.786 | secondary |  |
| 13 | Concerning the Five Savio | 126 | -1.19 | 0.79 | 1.59 | 0.33 | 1.587 | hagiographic |  |
| 14 | The Interpretation [of] t | 175 | 3.43 | 2.29 | 0.00 | 1.00 | -2.260 | secondary |  |
| 15 | [Concerning the ... ...]  | 380 | 7.89 | 5.53 | 0.53 | 0.91 | 0.000 | secondary |  |
| 16 | [Concerning the Five] Gre | 1830 | 2.68 | 2.79 | 0.77 | 0.78 | 1.858 | secondary |  |
| 17 | The Chapter of the Three  | 731 | 3.56 | 3.42 | 0.96 | 0.78 | -0.268 | secondary |  |
| 18 | [Concerning the Five] War | 566 | 5.57 | 4.06 | 0.35 | 0.92 | 4.594 | core |  |
| 19 | Concerning the Five Relea | 602 | 4.24 | 3.99 | 0.83 | 0.83 | 2.326 | secondary |  |
| 20 | The Chapter of the Name o | 169 | 9.47 | 7.69 | 1.78 | 0.81 | -1.121 | secondary |  |
| 21 | [C]oncerning the Father o | 253 | 3.95 | 2.77 | 0.40 | 0.87 | 0.806 | secondary |  |
| 22 | [On] the Land of Light | 211 | 4.74 | 2.84 | 0.00 | 1.00 | -0.934 | secondary |  |
| 23 | [ ... ] which [ ... ] | 811 | 3.21 | 1.97 | 0.00 | 0.99 | -0.489 | secondary |  |
| 24 | [... / ...] | 1706 | 3.81 | 2.52 | 0.06 | 0.97 | 2.696 | secondary |  |
| 25 | [Concerning the Advent of | 84 | 1.79 | 4.76 | 3.57 | 0.57 | 0.000 | secondary |  |
| 26 | Concerning the First Man  | 283 | 3.18 | 2.12 | 0.00 | 1.00 | 2.842 | secondary |  |
| 27 | Concerning the Five Forms | 590 | 1.27 | 1.53 | 0.68 | 0.69 | 1.356 | secondary |  |
| 28 | [Concerning the T]welve J | 769 | 3.19 | 3.51 | 1.17 | 0.75 | 2.867 | secondary |  |
| 29 | Concerning the Eighteen G | 584 | 3.51 | 3.42 | 0.86 | 0.80 | 2.055 | secondary |  |
| 30 | Concerning the Three Garm | 174 | -2.87 | 0.57 | 2.30 | 0.20 | -3.448 | peripheral |  |
| 31 | Concerning the Summons, i | 449 | 2.45 | 2.23 | 0.45 | 0.83 | 1.345 | secondary |  |
| 32 | Concerning the Seven Work | 301 | 3.99 | 3.32 | 0.66 | 0.83 | 4.009 | secondary |  |
| 33 | Concerning the Five Thing | 89 | 1.69 | 3.37 | 2.25 | 0.60 | 6.818 | secondary |  |
| 34 | Concerning the Ten Things | 132 | 1.14 | 2.27 | 1.52 | 0.60 | -1.515 | secondary |  |
| 35 | Concerning the Four Works | 115 | 1.30 | 2.61 | 1.74 | 0.60 | 0.030 | secondary |  |
| 36 | Concerning the Wheel that | 342 | 3.95 | 2.92 | 0.29 | 0.91 | 0.585 | secondary |  |
| 37 | Concerning the Three Zone | 145 | 4.14 | 4.14 | 1.38 | 0.75 | -2.702 | secondary |  |
| 38 | Concerning the Light Mind | 4277 | 0.95 | 1.75 | 0.89 | 0.66 | 1.731 | secondary | ✅ |
| 39 | Concerning the Three Days | 709 | 1.90 | 2.40 | 0.99 | 0.71 | 0.567 | secondary | ✅ |
| 40 | Concerning the Three Thin | 292 | 0.69 | 1.37 | 0.68 | 0.66 | 1.370 | mixed | ✅ |
| 41 | Concerning the Three Blow | 241 | 1.25 | 0.83 | 0.00 | 0.99 | 1.667 | secondary | ✅ |
| 42 | Concerning the Three Vess | 1624 | 3.17 | 2.52 | 0.37 | 0.87 | 2.340 | secondary |  |
| 43 | Concerning the Vessels. | 836 | 3.35 | 2.75 | 0.36 | 0.88 | -1.196 | secondary |  |
| 44 | Concerning the Sea Giant | 821 | 3.11 | 2.31 | 0.24 | 0.90 | 2.198 | secondary |  |
| 45 | Concerning the Vessels | 365 | 5.34 | 3.56 | 0.00 | 1.00 | 1.663 | secondary |  |
| 46 | Concerning the Ambassador | 327 | -0.46 | 1.83 | 1.53 | 0.54 | 0.004 | mixed |  |
| 47 | Concerning the Four great | 732 | 0.82 | 0.82 | 0.27 | 0.74 | 1.639 | mixed |  |
| 48 | Concerning the Conduits. | 1515 | 1.68 | 1.45 | 0.26 | 0.84 | 0.662 | secondary |  |
| 49 | Concerning the Wheel and  | 243 | 1.23 | 0.82 | 0.00 | 0.99 | 0.007 | secondary |  |
| 50 | Concerning these Names: G | 394 | 2.16 | 2.79 | 1.52 | 0.65 | 0.508 | secondary |  |
| 51 | Concerning the First Man. | 262 | 2.10 | 1.91 | 0.38 | 0.83 | 4.580 | secondary |  |
| 52 | Concerning the [ ... ] of | 394 | -1.65 | 0.00 | 1.02 | 0.00 | 0.000 | hagiographic |  |
| 53 | Concerning the First Man. | 368 | 9.38 | 6.52 | 0.54 | 0.92 | 5.978 | secondary |  |
| 54 | [Concerning] the Quality  | 428 | 3.85 | 3.04 | 0.47 | 0.86 | 3.738 | secondary |  |
| 55 | Concerning the Fashioning | 1169 | 4.11 | 2.91 | 0.17 | 0.94 | -1.708 | secondary | ✅ |
| 56 | [Concerning Saklas and hi | 2181 | 0.23 | 1.51 | 1.15 | 0.57 | 0.825 | mixed | ✅ |
| 57 | Concerning the Generation | 1094 | -0.87 | 0.18 | 0.64 | 0.22 | 0.731 | pastoral |  |
| 58 | The Four Powers that grie | 344 | -0.29 | 1.16 | 1.16 | 0.50 | 2.326 | mixed |  |
| 59 | The Chapter of the Elemen | 802 | 0.37 | 0.75 | 0.37 | 0.66 | 1.746 | mixed |  |
| 60 | [Concerning the Four Fath | 452 | 0.78 | 1.11 | 0.44 | 0.71 | -0.442 | mixed |  |
| 61 | Concerning the Garment of | 816 | 0.74 | 0.98 | 0.37 | 0.72 | -1.226 | mixed |  |
| 62 | Concerning the Three Rock | 236 | 2.12 | 2.54 | 0.85 | 0.75 | 2.542 | secondary | ✅ |
| 63 | Concerning Love. | 360 | 0.97 | 1.94 | 1.11 | 0.63 | -1.667 | mixed |  |
| 64 | [Concerning Adam] | 595 | 3.28 | 2.18 | 0.00 | 1.00 | 0.338 | secondary |  |
| 65 | Concerning the Sun. | 1862 | -0.29 | 0.48 | 0.64 | 0.42 | 0.537 | mixed |  |
| 66 | Concerning the Ambassador | 501 | -1.10 | 0.40 | 1.00 | 0.28 | 1.995 | peripheral |  |
| 67 | Concerning the Light-Give | 236 | -5.30 | 0.42 | 3.39 | 0.11 | 0.000 | pastoral |  |
| 68 | Concerning Fire. | 116 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | mixed |  |
| 69 | Concerning the Twelve Sig | 935 | 1.34 | 1.07 | 0.21 | 0.83 | 0.215 | secondary |  |
| 70 | Concerning the Body: It w | 1761 | 3.46 | 2.73 | 0.34 | 0.89 | 2.046 | secondary | ✅ |
| 71 | Concerning the Gathering  | 131 | 5.72 | 4.58 | 0.76 | 0.86 | -6.037 | secondary | ✅ |
| 72 | Concerning the worn and t | 724 | 2.21 | 1.80 | 0.28 | 0.86 | 1.657 | secondary | ✅ |
| 73 | Concerning the Envy of Ma | 566 | -1.15 | 0.88 | 1.24 | 0.41 | 1.060 | pastoral |  |
| 74 | Concerning the living Fir | 339 | 3.98 | 2.95 | 0.29 | 0.91 | -1.754 | secondary | ✅ |
| 75 | [Concerning the Letter (? | 397 | -1.76 | 3.02 | 3.27 | 0.48 | 10.076 | peripheral | ✅ |
| 76 | [Conce]rning Lord Manicha | 1655 | -0.85 | 0.12 | 0.54 | 0.18 | 0.241 | pastoral |  |
| 77 | The Chapter of the Four K | 411 | -4.50 | 0.00 | 2.43 | 0.00 | 2.425 | pastoral |  |
| 78 | Concerning the Four Thing | 224 | -1.34 | 0.00 | 0.89 | 0.00 | 0.893 | peripheral |  |
| 79 | Concerning the Fasting of | 222 | -5.41 | 0.45 | 3.15 | 0.12 | 0.901 | pastoral |  |
| 80 | The Chapter of the Comman | 476 | -9.45 | 0.21 | 4.83 | 0.04 | 4.622 | pastoral |  |
| 81 | The Chapter of Fasting, f | 1055 | -4.31 | 0.09 | 2.27 | 0.04 | -1.899 | pastoral |  |
| 82 | The Chapter of Righteous  | 909 | -1.87 | 0.00 | 0.99 | 0.00 | -0.882 | pastoral |  |
| 83 | Concerning the Man who is | 1216 | -1.27 | 0.74 | 1.32 | 0.36 | -0.493 | peripheral |  |
| 84 | Concerning Wisdom; it is  | 1234 | -0.12 | 0.08 | 0.16 | 0.32 | -0.162 | pastoral |  |
| 85 | Concerning the Cross of L | 1754 | -3.02 | 0.68 | 2.17 | 0.24 | 1.026 | pastoral | ✅ |
| 86 | The Chapter of the Man wh | 1061 | -0.66 | 0.47 | 0.75 | 0.38 | -0.377 | peripheral | ✅ |
| 87 | Concerning the Alms, that | 656 | -5.87 | 2.59 | 5.03 | 0.34 | -5.793 | pastoral |  |
| 88 | Concerning the Catechumen | 804 | -1.24 | 0.62 | 1.12 | 0.36 | -0.000 | pastoral |  |
| 89 | The Chapter of the Nazore | 664 | -1.81 | 0.00 | 0.90 | 0.00 | 0.602 | pastoral |  |
| 90 | Concerning the Fifteen Pa | 1447 | -3.32 | 0.41 | 1.94 | 0.18 | 0.551 | pastoral |  |
| 91 | Also concerning the Catec | 2071 | -6.25 | 0.43 | 3.43 | 0.11 | -0.292 | pastoral |  |
| 92 | The Apostle is asked: Why | 366 | -4.24 | 1.09 | 3.01 | 0.27 | 4.372 | pastoral |  |
| 93 | A Catechumen asked the Ap | 717 | -3.21 | 0.84 | 2.23 | 0.27 | -0.562 | pastoral |  |
| 94 | Concerning the Purificati | 329 | 1.67 | 2.13 | 0.91 | 0.70 | -1.815 | secondary |  |
| 95 | The Apostle asks his Disc | 1170 | 1.67 | 1.62 | 0.43 | 0.79 | -0.513 | secondary |  |
| 96 | The Three Earths that Exi | 424 | -0.35 | 0.71 | 0.71 | 0.50 | -0.943 | mixed |  |
| 97 | Concerning the Three Crea | 245 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | mixed |  |
| 98 | What is Virginal; or, oth | 486 | 0.72 | 1.23 | 0.62 | 0.66 | -0.823 | mixed |  |
| 99 | Concerning Transmigration | 400 | -3.62 | 0.25 | 2.00 | 0.11 | -0.500 | pastoral |  |
| 100 | Concerning the Dragon wit | 476 | -0.63 | 0.42 | 0.63 | 0.40 | 0.840 | peripheral |  |
| 101 | [Concer]ning why, if the  | 490 | 0.41 | 0.61 | 0.20 | 0.74 | 1.224 | mixed |  |
| 102 | Concerning the Light Mind | 479 | -2.09 | 0.63 | 1.46 | 0.30 | -1.255 | pastoral |  |
| 103 | Concerning the Five Wonde | 204 | -2.21 | 1.47 | 2.45 | 0.37 | -4.902 | pastoral |  |
| 104 | Concerning Food: It shall | 170 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | mixed |  |
| 105 | Concerning the Three Thin | 260 | -3.27 | 0.00 | 1.54 | 0.00 | 1.538 | pastoral |  |
| 106 | There is no Joy that shal | 329 | 1.37 | 0.91 | 0.00 | 0.99 | -0.602 | secondary |  |
| 107 | Concerning the Form of th | 150 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | mixed |  |
| 108 | Concerning the Seed Grain | 191 | 2.62 | 1.57 | 0.00 | 0.99 | 0.011 | secondary |  |
| 109 | Concerning the Fifty Lord | 548 | -1.55 | 0.73 | 1.28 | 0.36 | 2.190 | pastoral | ✅ |
| 110 | Concerning the Nourishmen | 108 | 2.78 | 1.85 | 0.00 | 0.99 | 0.000 | secondary |  |
| 111 | Concerning the Four Arche | 161 | 0.93 | 0.62 | 0.00 | 0.98 | -1.235 | mixed |  |
| 112 | The Human is less than al | 802 | -0.12 | 0.37 | 0.37 | 0.49 | -0.499 | mixed |  |
| 113 | The Chapter on whether an | 168 | 2.08 | 2.38 | 0.60 | 0.80 | 0.000 | secondary |  |
| 114 | Concerning the Three Imag | 407 | 4.54 | 3.69 | 0.49 | 0.88 | 0.010 | core | ✅ |
| 115 | The Catechumen asks the A | 2486 | -1.29 | 2.09 | 2.21 | 0.48 | 3.057 | peripheral | ✅ |
| 116 | Concerning why if a [Nail | 307 | -0.49 | 0.00 | 0.33 | 0.00 | 0.000 | pastoral |  |
| 117 | Concerning why Some shall | 122 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | mixed |  |
| 118 | [ ... ] | 66 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | mixed |  |
| 119 | [ ... ] | 494 | 0.41 | 3.44 | 2.63 | 0.57 | 0.810 | mixed |  |
| 120 | Concerning the Two Essenc | 524 | -1.91 | 0.38 | 1.53 | 0.20 | 1.908 | peripheral |  |
| 121 | Concerning the Sect of th | 535 | -1.78 | 1.12 | 1.68 | 0.40 | 0.748 | pastoral |  |
| 122 | Concerning the 'Assent' a | 899 | -0.83 | 1.22 | 1.33 | 0.48 | 1.557 | peripheral | ✅ |
