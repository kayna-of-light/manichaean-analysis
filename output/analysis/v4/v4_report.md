# Kephalaia Layer Analysis v4 — Clean-Source Results

**Date**: 2026-02-16
**Data Source**: LLM-cleaned structured JSON (output/cleaned/chapters/)
**Chapters analyzed**: 123
**Total teaching words**: 83,698
**Total paragraphs**: 1429

---

## 1. Tier Classification Summary

| Tier | Count | % | Description |
|------|------:|--:|-------------|
| Core | 56 | 45.5% | Original correspondential cosmology — pre-Mani substrate |
| Secondary | 24 | 19.5% | Cosmological but with mixed signals |
| Mixed | 17 | 13.8% | Both cosmological and pastoral vocabulary |
| Pastoral | 25 | 20.3% | Church instruction dominant |
| Hagiographic | 1 | 0.8% | Biographical Mani material dominant |
| Peripheral | 0 | 0.0% | Low-signal chapters |
| Fragmentary | 0 | 0.0% | Too short for reliable analysis (<30 words) |

## 2. Agreement with Manual Layer 1 Extract

| Metric | Value |
|--------|-------|
| Manual Layer 1 chapters | 21 |
| Computed Core+Secondary | 80 |
| True Positive | 18 |
| True Negative | 40 |
| False Positive (computed core, manual excluded) | 62 |
| False Negative (computed other, manual included) | 3 |
| **Agreement** | **47.2%** |
| **Cohen's κ** | **0.118** |

### False Negatives (in manual extract but not computed core/secondary)

- **Ch. 85** (Concerning the Cross of Light: [...] trample upon ): tier=pastoral, score=-0.71, cosmo=0.63, pastoral=1.60
- **Ch. 86** (The Chapter of the Man who asks: Why [am] I someti): tier=mixed, score=0.28, cosmo=0.38, pastoral=0.28
- **Ch. 122** (Concerning the 'Assent' and the 'Amen'): tier=pastoral, score=0.45, cosmo=1.22, pastoral=1.33

### Candidates for Restoration (computed core/secondary, not in manual extract)

- **Ch. 20** (The Chapter of the Name of the Fathers): tier=core, score=17.75
  - Cosmological: father of greatness x4, third ambassador x1, jesus the splendour x1, living fire x1, ship of living waters x1, ship of living fire x1, living water x1
- **Ch. 53** (Concerning the First Man.): tier=core, score=13.31
  - Cosmological: first man x3, living spirit x1, living fire x1, land of darkness x3, thought of death x1, storehouses x6, rulers x1, elements x1
- **Ch. 15** ([Concerning the ... ...] Five [Parts ...] Worlds o): tier=core, score=11.58
  - Cosmological: first man x4, land of darkness x3, five elements x2, five worlds x3, five trees x1, elements x2, zodiac x1
- **Ch. 10** (Concerning the Interpretation of the Fourteen [Gre): tier=core, score=10.74
  - Cosmological: first man x2, living spirit x2, five sons x1, five elements x1, aeons x6
- **Ch. 4** (Concerning the Four Great Days that have come fort): tier=core, score=9.96
  - Cosmological: first man x3, living spirit x3, third ambassador x1, jesus the splendour x1, five sons x2, land of darkness x2, old man x3, pillar of glory x1
- **Ch. 29** (Concerning the Eighteen Great Thrones of all the F): tier=core, score=9.16
  - Cosmological: first man x3, living spirit x2, mother of life x1, third ambassador x1, jesus the splendour x2, virgin of light x1, great builder x1, beloved of the lights x1
- **Ch. 18** ([Concerning the Five] War[s that the] Sons of [Li]): tier=core, score=8.66
  - Cosmological: living spirit x3, third ambassador x2, living soul x1, living fire x1, five elements x1, five worlds x1, five trees x1, three vessels x1
- **Ch. 37** (Concerning the Three Zones.): tier=core, score=8.62
  - Cosmological: living spirit x2, king of honour x1, five sons x1, firmaments x1, constructed x1
- **Ch. 25** ([Concerning the Advent of Five Fathers from the Fi): tier=core, score=8.33
  - Cosmological: mother of life x1, virgin of light x1, beloved of the lights x1, five limbs x1
- **Ch. 19** (Concerning the Five Releases: what they are): tier=core, score=8.14
  - Cosmological: first man x7, living spirit x3, mother of life x1, third ambassador x2, jesus the splendour x1, firmaments x1, aeons x1, rulers x2
- **Ch. 64** ([Concerning Adam]): tier=core, score=7.73
  - Cosmological: five sons x1, rulers x1, zodiac x1
- **Ch. 17** (The Chapter of the Three Seasons): tier=core, score=7.52
  - Cosmological: first man x10, living spirit x2, mother of life x3, third ambassador x1, land of darkness x1, land of light x1, constructed x1, crucified x1
- **Ch. 45** (Concerning the Vessels): tier=core, score=7.12
  - Cosmological: adamant of light x1, vessels x1, fashioned x2, constructed x7, discharged x2
- **Ch. 28** ([Concerning the T]welve Judges [of] the Father): tier=core, score=6.96
  - Cosmological: first man x3, living spirit x1, mother of life x1, father of greatness x1, third ambassador x1, jesus the splendour x2, light mind x1, virgin of light x1
- **Ch. 22** ([On] the Land of Light): tier=core, score=6.87
  - Cosmological: land of light x2, aeons x1
- **Ch. 16** ([Concerning the Five] Greatnesses who [went forth]): tier=core, score=6.23
  - Cosmological: first man x13, living spirit x11, mother of life x2, father of greatness x1, third ambassador x3, jesus the splendour x4, great builder x1, beloved of the lights x1
- **Ch. 32** (Concerning the Seven Works of the Living Spirit): tier=core, score=5.98
  - Cosmological: first man x1, living spirit x2, five sons x1, ships of light x1, three vessels x1, aeons x1, constructed x2, crucified x1
- **Ch. 21** ([C]oncerning the Father of Gr[eat]ness: [ho]w he i): tier=core, score=5.93
  - Cosmological: father of greatness x1, land of light x1, storehouses x1, aeons x2
- **Ch. 54** ([Concerning] the Quality of the Garments): tier=core, score=5.72
  - Cosmological: first man x1, living spirit x3, mother of life x1, third ambassador x1, five sons x1, ships of light x1, wheel of the stars x1, ten firmaments x1
- **Ch. 36** (Concerning the Wheel that exists in front of the K): tier=core, score=5.70
  - Cosmological: king of honour x4, firmaments x1, rulers x3, mixture x1
- **Ch. 24** ([... / ...]): tier=core, score=5.66
  - Cosmological: first man x7, living spirit x1, mother of life x4, father of greatness x4, jesus the splendour x1, virgin of light x1, great builder x1, land of light x1
- **Ch. 7** (The Seventh, concerning the Five Fathers): tier=core, score=5.45
  - Cosmological: father of greatness x1, third ambassador x2, jesus the splendour x2, light mind x2, virgin of light x1, beloved of the lights x1, light form x3, pillar of glory x1
- **Ch. 5** (Concerning Four Hunters of Light and Four of Darkn): tier=core, score=5.28
  - Cosmological: first man x1, living spirit x1, third ambassador x1, jesus the splendour x1, living soul x3, land of darkness x1, great fire x2, five elements x1
- **Ch. 50** (Concerning these Names: God, Rich One, and Angel; ): tier=core, score=5.20
  - Cosmological: beloved of the lights x1, land of light x2, great spirit x1, emanations x1, entangled x1
- **Ch. 119** ([ ... ]): tier=core, score=5.06
  - Cosmological: first man x5, five sons x1, aeons x3
- **Ch. 11** ([Concerning the Interpretation of] all [the] Fathe): tier=core, score=4.92
  - Cosmological: first man x1, living spirit x1, mother of life x1, jesus the splendour x1, light mind x1, virgin of light x1, great builder x1, beloved of the lights x1
- **Ch. 43** (Concerning the Vessels.): tier=core, score=4.90
  - Cosmological: three vessels x3, porter x1, firmaments x3, rulers x1, vessels x5, constructed x1, discharged x9
- **Ch. 42** (Concerning the Three Vessels): tier=core, score=4.83
  - Cosmological: living spirit x3, living fire x1, garment of wind x1, garment of water x1, great fire x1, three vessels x3, firmaments x2, aeons x2
- **Ch. 14** (The Interpretation [of] the S[i]lence, the Fast, [): tier=core, score=4.57
  - Cosmological: first man x1, ship of living waters x1, living water x1, pillar of glory x1
- **Ch. 33** (Concerning the Five Things that he constructed wit): tier=core, score=4.49
  - Cosmological: living spirit x1, porter x1, constructed x1
- **Ch. 31** (Concerning the Summons, in which Limb of the Soul ): tier=core, score=4.45
  - Cosmological: first man x2, virgin of light x2, living soul x4, pillar of glory x1
- **Ch. 23** ([ ... ] which [ ... ]): tier=core, score=4.44
  - Cosmological: first man x3, father of greatness x1, land of darkness x2, land of light x1, land of the living x1, five garments x1, five dark x1, storehouses x1
- **Ch. 44** (Concerning the Sea Giant): tier=core, score=4.38
  - Cosmological: living spirit x1, king of glory x1, three wheels x1, three vessels x3, wheel of the stars x1, ten firmaments x1, firmaments x1, zodiac x3
- **Ch. 26** (Concerning the First Man and the Ambassador and th): tier=core, score=4.24
  - Cosmological: first man x3, living spirit x1, living soul x1, great spirit x1
- **Ch. 9** (The Explanation of the Peace, what it is; the Righ): tier=core, score=3.97
  - Cosmological: first man x14, living spirit x2, mother of life x3, light mind x3, land of light x2, living ones x1, light form x3, storehouses x1
- **Ch. 35** (Concerning the Four Works of the Ambassador): tier=core, score=3.91
  - Cosmological: living soul x1, firmaments x1
- **Ch. 110** (Concerning the Nourishment of the Person, for ther): tier=core, score=3.70
  - Cosmological: rulers x2
- **Ch. 108** (Concerning the Seed Grain that shall be formed by ): tier=core, score=3.67
  - Cosmological: five elements x1, elements x1
- **Ch. 113** (The Chapter on whether any [Lig]ht comes from the ): tier=core, score=3.57
  - Cosmological: living ones x1, three vessels x1, firmaments x1, vessels x1
- **Ch. 94** (Concerning the Purification of these Four Elements): tier=core, score=3.50
  - Cosmological: light mind x1, land of the living x1, living ones x2, new man x1, elements x2
- **Ch. 27** (Concerning the Five Forms that exist in the Rulers): tier=core, score=3.39
  - Cosmological: five worlds x2, fashioned x1
- **Ch. 51** (Concerning the First Man.): tier=core, score=3.24
  - Cosmological: first man x1, living fire x4
- **Ch. 95** (The Apostle asks his Disciples: What is Cloud?): tier=core, score=3.21
  - Cosmological: virgin of light x3, porter x1, rulers x11, mingled x1
- **Ch. 34** (Concerning the Ten Things that the Ambassador bega): tier=core, score=3.03
  - Cosmological: third ambassador x1, great builder x1, rulers x1
- **Ch. 48** (Concerning the Conduits.): tier=secondary, score=2.94
  - Cosmological: living spirit x2, living soul x1, five worlds x3, five trees x1, wheel of the stars x1, firmaments x4, elements x1, zodiac x3
- **Ch. 98** (What is Virginal; or, otherwise, what is Continent): tier=secondary, score=2.88
  - Cosmological: light mind x1, new man x1, old man x1, aeons x1
- **Ch. 63** (Concerning Love.): tier=secondary, score=2.78
  - Cosmological: father of greatness x1, living soul x1, cross of light x1, land of darkness x1, aeons x1
- **Ch. 60** ([Concerning the Four Fathers; what they are like.]): tier=secondary, score=2.43
  - Cosmological: jesus the splendour x1, living soul x2, ships of light x1, storehouses x1, aeons x1
- **Ch. 69** (Concerning the Twelve Signs of the Zodiac and the ): tier=secondary, score=2.19
  - Cosmological: land of darkness x1, five worlds x3, rulers x1, zodiac x2, fashioned x1
- **Ch. 73** (Concerning the Envy of Matter): tier=secondary, score=1.94
  - Cosmological: first man x1, thought of death x1
- **Ch. 106** (There is no Joy that shall remain in the World til): tier=secondary, score=1.82
  - Cosmological: living soul x3
- **Ch. 12** (Concerning the Interpretation of the Five Words th): tier=secondary, score=1.80
  - Cosmological: third ambassador x1
- **Ch. 49** (Concerning the Wheel and the Conduits): tier=secondary, score=1.65
  - Cosmological: entangled x2
- **Ch. 8** (Concerning the Fourteen Vehicles that Jesus has bo): tier=secondary, score=1.60
  - Cosmological: first man x1, living fire x1, living water x1, pillar of glory x1, perfect man x1
- **Ch. 61** (Concerning the Garment of the Waters: how great is): tier=secondary, score=1.41
  - Cosmological: first man x2, garment of water x1, rulers x4, elements x1
- **Ch. 47** (Concerning the Four great Things): tier=secondary, score=1.37
  - Cosmological: three vessels x1, wheel of the stars x1, ten firmaments x1, eight earths x1, firmaments x1, vessels x1
- **Ch. 111** (Concerning the Four Archetypes that occur in the E): tier=secondary, score=1.24
  - Cosmological: first man x1
- **Ch. 46** (Concerning the Ambassador.): tier=secondary, score=1.22
  - Cosmological: third ambassador x1, great builder x1, ships of light x1, zodiac x1, fashioned x1, constructed x1
- **Ch. 0** (Introduction): tier=secondary, score=1.05
  - Cosmological: first man x1, living spirit x1, third ambassador x1, three vessels x1, aeons x2, vessels x1, constructed x1, crucified x1
- **Ch. 58** (The Four Powers that grieve): tier=secondary, score=0.87
  - Cosmological: first man x1, mother of life x1, light mind x1, five sons x1
- **Ch. 101** ([Concer]ning why, if the Person shall look down in): tier=secondary, score=0.82
  - Cosmological: first man x2, living spirit x1
- **Ch. 65** (Concerning the Sun.): tier=secondary, score=0.75
  - Cosmological: father of greatness x1, living soul x2, aeons x1, fashioned x1

---

## 3. Purest Core Chapters (by Composite Score)

| Rank | Ch. | Title | Score | Cosmo | Corresp | Persian | Pastoral | NT | Hagio | Tier | Manual |
|------|-----|-------|------:|------:|--------:|--------:|---------:|---:|------:|------|:------:|
| 1 | 20 | The Chapter of the Name of the Fath | 17.75 | 5.92 | 0.00 | 2.37 | 0.00 | 0.00 | 1.18 | core |  |
| 2 | 53 | Concerning the First Man. | 13.31 | 5.71 | 0.00 | 0.82 | 0.00 | 0.00 | 0.54 | core |  |
| 3 | 15 | [Concerning the ... ...] Five [Part | 11.58 | 4.21 | 0.00 | 1.32 | 0.53 | 0.00 | 0.00 | core |  |
| 4 | 10 | Concerning the Interpretation of th | 10.74 | 4.03 | 1.01 | 0.34 | 0.34 | 0.00 | 0.34 | core |  |
| 5 | 4 | Concerning the Four Great Days that | 9.96 | 3.52 | 0.70 | 0.47 | 0.00 | 0.00 | 0.23 | core |  |
| 6 | 29 | Concerning the Eighteen Great Thron | 9.16 | 3.60 | 0.68 | 0.17 | 0.17 | 0.00 | 0.00 | core |  |
| 7 | 18 | [Concerning the Five] War[s that th | 8.66 | 3.18 | 0.88 | 0.18 | 0.18 | 0.00 | 0.18 | core |  |
| 8 | 37 | Concerning the Three Zones. | 8.62 | 4.14 | 0.69 | 0.00 | 0.00 | 0.00 | 1.38 | core |  |
| 9 | 25 | [Concerning the Advent of Five Fath | 8.33 | 4.76 | 0.00 | 0.00 | 0.00 | 0.00 | 1.19 | core |  |
| 10 | 19 | Concerning the Five Releases: what  | 8.14 | 3.32 | 1.00 | 0.00 | 0.66 | 0.00 | 0.00 | core |  |
| 11 | 64 | [Concerning Adam] | 7.73 | 0.50 | 2.69 | 0.00 | 0.00 | 0.00 | 0.00 | core |  |
| 12 | 17 | The Chapter of the Three Seasons | 7.52 | 2.74 | 0.82 | 0.27 | 0.27 | 0.14 | 0.14 | core |  |
| 13 | 114 | Concerning the Three Images that ar | 7.25 | 2.46 | 1.23 | 0.00 | 0.49 | 0.00 | 0.00 | core | ✅ |
| 14 | 45 | Concerning the Vessels | 7.12 | 3.56 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | core |  |
| 15 | 28 | [Concerning the T]welve Judges [of] | 6.96 | 3.25 | 0.26 | 0.13 | 0.39 | 0.00 | 0.00 | core |  |
| 16 | 55 | Concerning the Fashioning of Adam | 6.89 | 2.05 | 1.11 | 0.00 | 0.00 | 0.00 | 0.00 | core | ✅ |
| 17 | 22 | [On] the Land of Light | 6.87 | 1.42 | 0.47 | 0.95 | 0.00 | 0.00 | 0.00 | core |  |
| 18 | 74 | Concerning the living Fire: It is p | 6.49 | 2.65 | 0.59 | 0.00 | 0.00 | 0.00 | 0.29 | core | ✅ |
| 19 | 16 | [Concerning the Five] Greatnesses w | 6.23 | 2.79 | 0.44 | 0.05 | 0.33 | 0.00 | 0.11 | core |  |
| 20 | 3 | The Interpretation of Happiness, Wi | 5.99 | 3.69 | 0.00 | 0.23 | 0.92 | 0.00 | 0.69 | core | ✅ |
| 21 | 32 | Concerning the Seven Works of the L | 5.98 | 3.32 | 0.00 | 0.00 | 0.00 | 0.00 | 0.66 | core |  |
| 22 | 21 | [C]oncerning the Father of Gr[eat]n | 5.93 | 1.98 | 0.00 | 0.79 | 0.00 | 0.00 | 0.40 | core |  |
| 23 | 71 | Concerning the Gathering in of the  | 5.72 | 3.82 | 0.00 | 0.00 | 0.76 | 0.00 | 0.76 | core | ✅ |
| 24 | 54 | [Concerning] the Quality of the Gar | 5.72 | 2.80 | 0.23 | 0.00 | 0.00 | 0.00 | 0.47 | core |  |
| 25 | 36 | Concerning the Wheel that exists in | 5.70 | 2.63 | 0.29 | 0.00 | 0.00 | 0.00 | 0.29 | core |  |

## 4. Most Contaminated Chapters

| Rank | Ch. | Title | Score | Pastoral | NT | Hagio | Tier |
|------|-----|-------|------:|---------:|---:|------:|------|
| 1 | 80 | The Chapter of the Commandments of Right | -6.41 | 4.20 | 0.42 | 0.21 | pastoral |
| 2 | 87 | Concerning the Alms, that [ ... ] life i | -5.95 | 6.10 | 0.00 | 0.00 | pastoral |
| 3 | 91 | Also concerning the Catechumen; shall he | -4.22 | 3.38 | 0.10 | 0.00 | pastoral |
| 4 | 79 | Concerning the Fasting of the Saints | -3.60 | 2.70 | 0.00 | 0.45 | pastoral |
| 5 | 92 | The Apostle is asked: Why when you drew  | -3.01 | 3.28 | 0.00 | 0.00 | pastoral |
| 6 | 81 | The Chapter of Fasting, for it engenders | -2.84 | 1.71 | 0.19 | 0.09 | pastoral |
| 7 | 77 | The Chapter of the Four Kingdoms | -2.80 | 1.70 | 0.00 | 0.24 | pastoral |
| 8 | 90 | Concerning the Fifteen Paths; and whethe | -2.14 | 1.66 | 0.21 | 0.07 | pastoral |
| 9 | 105 | Concerning the Three Things that are gre | -2.12 | 0.38 | 0.77 | 0.00 | pastoral |
| 10 | 99 | Concerning Transmigration | -1.88 | 2.00 | 0.00 | 0.00 | pastoral |
| 11 | 1 | Concerning the Ad[vent] of the Apostle. | -1.68 | 0.97 | 0.34 | 0.04 | pastoral |
| 12 | 89 | The Chapter of the Nazorean who question | -1.35 | 0.60 | 0.15 | 0.15 | pastoral |
| 13 | 93 | A Catechumen asked the Apostle: When I w | -1.32 | 2.23 | 0.00 | 0.00 | pastoral |
| 14 | 102 | Concerning the Light Mind, why it does n | -1.04 | 1.25 | 0.21 | 0.00 | pastoral |
| 15 | 52 | Concerning the [ ... ] of the Light | -0.89 | 0.25 | 0.00 | 0.51 | pastoral |
| 16 | 82 | The Chapter of Righteous [Judgement] | -0.71 | 0.77 | 0.00 | 0.11 | pastoral |
| 17 | 85 | Concerning the Cross of Light: [...] tra | -0.71 | 1.60 | 0.00 | 0.00 | pastoral |
| 18 | 76 | [Conce]rning Lord Manichaios: how he jou | -0.45 | 0.42 | 0.00 | 0.06 | pastoral |
| 19 | 67 | Concerning the Light-Giver. | -0.42 | 1.69 | 0.00 | 0.00 | pastoral |
| 20 | 116 | Concerning why if a [Nail] is cut the Pe | -0.33 | 0.00 | 0.00 | 0.33 | mixed |

## 5. Editor Fatigue — Highest Intra-Chapter Shifts

| Ch. | Title | Shift | 1st Cosmo | 2nd Cosmo | 1st Pastoral | 2nd Pastoral |
|-----|-------|------:|----------:|----------:|-------------:|-------------:|
| 75 | [Concerning the Letter (?)] | 10.078 | 5.56 | 0.00 | 0.00 | 4.52 |
| 33 | Concerning the Five Things that he  | 6.818 | 6.82 | 0.00 | 0.00 | 0.00 |
| 53 | Concerning the First Man. | 5.978 | 8.70 | 2.72 | 0.00 | 0.00 |
| 80 | The Chapter of the Commandments of  | 4.622 | 0.42 | 0.00 | 2.10 | 6.30 |
| 18 | [Concerning the Five] War[s that th | 4.594 | 5.30 | 1.06 | 0.00 | 0.35 |
| 51 | Concerning the First Man. | 4.580 | 3.82 | 0.00 | 0.00 | 0.76 |
| 32 | Concerning the Seven Works of the L | 4.009 | 5.33 | 1.32 | 0.00 | 0.00 |
| 54 | [Concerning] the Quality of the Gar | 3.738 | 4.67 | 0.93 | 0.00 | 0.00 |
| 8 | Concerning the Fourteen Vehicles th | 3.502 | 2.92 | 0.00 | 0.58 | 1.16 |
| 7 | The Seventh, concerning the Five Fa | 3.465 | 3.47 | 1.24 | 0.00 | 1.24 |
| 92 | The Apostle is asked: Why when you  | 3.279 | 0.55 | 0.55 | 1.64 | 4.92 |
| 26 | Concerning the First Man and the Am | 2.842 | 3.55 | 0.70 | 0.00 | 0.00 |
| 24 | [... / ...] | 2.814 | 3.63 | 0.82 | 0.00 | 0.00 |
| 29 | Concerning the Eighteen Great Thron | 2.740 | 4.79 | 2.40 | 0.00 | 0.34 |
| 115 | The Catechumen asks the Apostle: wi | 2.735 | 2.82 | 1.13 | 1.45 | 2.49 |

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
| 2 | The Second, concerning the Parable of th | Lk. 6, Lk. 2 | core |
| 7 | The Seventh, concerning the Five Fathers | Jn. 8 | core |
| 9 | The Explanation of the Peace, what it is | Mk. 1 | core |
| 18 | [Concerning the Five] War[s that the] So | Mt. 3 | core |
| 19 | Concerning the Five Releases: what they  | Phil. 2 | core |
| 63 | Concerning Love. | Jn. 1 | secondary |
| 75 | [Concerning the Letter (?)] | Mt. 2, Jn 1 | secondary |
| 76 | [Conce]rning Lord Manichaios: how he jou | Jn. 3 | pastoral |
| 77 | The Chapter of the Four Kingdoms | Mt. 1 | pastoral |
| 82 | The Chapter of Righteous [Judgement] | Mt. 6 | pastoral |
| 83 | Concerning the Man who is ugly in his Bo | Mt. 1 | pastoral |
| 85 | Concerning the Cross of Light: [...] tra | Mt. 6 | pastoral |
| 89 | The Chapter of the Nazorean who question | Mt. 6 | pastoral |
| 91 | Also concerning the Catechumen; shall he | Mt. 6, 1 Cor. 7 | pastoral |
| 109 | Concerning the Fifty Lord's Days; to wha | Mt. 4, Mt. 2, Lk. 2 | secondary |

## 8. Structural Patterns

- Chapters with formulaic opening: **60** (49%)
- Chapters with formulaic closing: **11** (9%)
- Chapters with Q&A formula: **7** (6%)
- Chapters with correspondence markers: **26** (21%)

### Chapters with Highest Correspondence Marker Density

| Ch. | Title | Corr Markers | Enum Markers | Tier | Score |
|-----|-------|:------------:|:------------:|------|------:|
| 38 | Concerning the Light Mind and the Apostl | 3 | 0 | secondary | 2.77 |
| 4 | Concerning the Four Great Days that have | 2 | 0 | core | 9.96 |
| 6 | Concerning the Five Storehouses that hav | 2 | 2 | core | 5.08 |
| 7 | The Seventh, concerning the Five Fathers | 2 | 1 | core | 5.45 |
| 27 | Concerning the Five Forms that exist in  | 2 | 0 | core | 3.39 |
| 28 | [Concerning the T]welve Judges [of] the  | 2 | 0 | core | 6.96 |
| 42 | Concerning the Three Vessels | 2 | 2 | core | 4.83 |
| 50 | Concerning these Names: God, Rich One, a | 2 | 0 | core | 5.20 |
| 65 | Concerning the Sun. | 2 | 1 | secondary | 0.75 |
| 69 | Concerning the Twelve Signs of the Zodia | 2 | 0 | secondary | 2.19 |
| 70 | Concerning the Body: It was constructed  | 2 | 0 | core | 5.42 |
| 0 | Introduction | 1 | 0 | secondary | 1.05 |
| 2 | The Second, concerning the Parable of th | 1 | 0 | core | 3.79 |
| 9 | The Explanation of the Peace, what it is | 1 | 1 | core | 3.97 |
| 10 | Concerning the Interpretation of the Fou | 1 | 0 | core | 10.74 |

## 9. TF-IDF Cluster Profiles

Optimal k=2 (silhouette=0.0157)

### Cluster 0: Mixed (n=47)
- Avg composite: 0.20
- Top TF-IDF terms: shall, light, body, good, church, catechumen, person, elect, like, come
- Chapters: 1, 2, 13, 27, 49, 56, 65, 68, 71, 75, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 99, 102, 103, 104, 107, 108, 109, 110, 113, 114, 115, 116, 117, 120, 121, 122
- Avg densities: {'cosmological': 0.783, 'persian_substrate': 0.035, 'pastoral': 1.045, 'nt_christian': 0.079, 'hagiographic': 0.131, 'correspondential': 0.153}

### Cluster 1: Cosmological (n=76)
- Avg composite: 4.33
- Top TF-IDF terms: light, great, father, darkness, man, living, time, came, earth, universe
- Chapters: 0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 50, 51, 52, 53, 54, 55, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 69, 70, 72, 73, 74, 76, 98, 100, 101, 105, 106, 111, 112, 118, 119
- Avg densities: {'cosmological': 1.955, 'persian_substrate': 0.146, 'pastoral': 0.279, 'nt_christian': 0.048, 'hagiographic': 0.263, 'correspondential': 0.303}

---

## Appendix: Full Chapter Data

| Ch. | Title | Words | Score | Cosmo | Pastoral | NT | Corr | TTR | Lac | Shift | Tier | Manual |
|-----|-------|------:|------:|------:|---------:|---:|-----:|----:|----:|------:|------|:------:|
| 0 | Introduction | 1480 | 1.05 | 0.68 | 0.41 | 0.07 | 0.20 | 0.283 | 4.32 | 2.162 | secondary |  |
| 1 | Concerning the Ad[vent] o | 2376 | -1.68 | 0.13 | 0.97 | 0.34 | 0.04 | 0.279 | 5.13 | -0.337 | pastoral |  |
| 2 | The Second, concerning th | 1371 | 3.79 | 1.31 | 0.51 | 0.29 | 0.95 | 0.277 | 9.99 | -1.020 | core | ✅ |
| 3 | The Interpretation of Hap | 434 | 5.99 | 3.69 | 0.92 | 0.00 | 0.00 | 0.378 | 3.92 | 1.843 | core | ✅ |
| 4 | Concerning the Four Great | 853 | 9.96 | 3.52 | 0.00 | 0.00 | 0.70 | 0.312 | 1.41 | 1.884 | core |  |
| 5 | Concerning Four Hunters o | 710 | 5.28 | 2.54 | 0.56 | 0.00 | 0.14 | 0.323 | 2.82 | -0.563 | core |  |
| 6 | Concerning the Five Store | 1397 | 5.08 | 1.86 | 0.00 | 0.14 | 0.29 | 0.347 | 0.86 | 1.434 | core | ✅ |
| 7 | The Seventh, concerning t | 808 | 5.45 | 2.35 | 0.62 | 0.00 | 0.62 | 0.347 | 0.50 | 3.465 | core |  |
| 8 | Concerning the Fourteen V | 343 | 1.60 | 1.46 | 0.87 | 0.00 | 0.00 | 0.458 | 0.29 | 3.502 | secondary |  |
| 9 | The Explanation of the Pe | 1788 | 3.97 | 2.01 | 0.45 | 0.00 | 0.11 | 0.251 | 0.95 | 2.461 | core |  |
| 10 | Concerning the Interpreta | 298 | 10.74 | 4.03 | 0.34 | 0.00 | 1.01 | 0.473 | 2.01 | 2.685 | core |  |
| 11 | [Concerning the Interpret | 295 | 4.92 | 3.73 | 0.34 | 0.68 | 0.00 | 0.464 | 1.69 | 0.023 | core |  |
| 12 | Concerning the Interpreta | 111 | 1.80 | 0.90 | 0.00 | 0.00 | 0.00 | 0.631 | 5.41 | -1.786 | secondary |  |
| 13 | Concerning the Five Savio | 126 | 0.00 | 0.79 | 0.00 | 0.00 | 0.00 | 0.492 | 15.08 | 1.587 | hagiographic |  |
| 14 | The Interpretation [of] t | 175 | 4.57 | 2.29 | 0.00 | 0.00 | 0.00 | 0.474 | 13.71 | -2.260 | core |  |
| 15 | [Concerning the ... ...]  | 380 | 11.58 | 4.21 | 0.53 | 0.00 | 0.00 | 0.408 | 8.95 | 0.000 | core |  |
| 16 | [Concerning the Five] Gre | 1830 | 6.23 | 2.79 | 0.33 | 0.00 | 0.44 | 0.299 | 3.66 | 1.858 | core |  |
| 17 | The Chapter of the Three  | 731 | 7.52 | 2.74 | 0.27 | 0.14 | 0.82 | 0.319 | 2.60 | 0.554 | core |  |
| 18 | [Concerning the Five] War | 566 | 8.66 | 3.18 | 0.18 | 0.00 | 0.88 | 0.390 | 9.89 | 4.594 | core |  |
| 19 | Concerning the Five Relea | 602 | 8.14 | 3.32 | 0.66 | 0.00 | 1.00 | 0.314 | 4.15 | 2.658 | core |  |
| 20 | The Chapter of the Name o | 169 | 17.75 | 5.92 | 0.00 | 0.00 | 0.00 | 0.521 | 1.18 | -2.297 | core |  |
| 21 | [C]oncerning the Father o | 253 | 5.93 | 1.98 | 0.00 | 0.00 | 0.00 | 0.451 | 7.11 | 0.806 | core |  |
| 22 | [On] the Land of Light | 211 | 6.87 | 1.42 | 0.00 | 0.00 | 0.47 | 0.403 | 12.32 | -0.934 | core |  |
| 23 | [ ... ] which [ ... ] | 811 | 4.44 | 1.48 | 0.00 | 0.00 | 0.00 | 0.335 | 6.66 | -0.489 | core |  |
| 24 | [... / ...] | 1706 | 5.66 | 2.23 | 0.00 | 0.00 | 0.06 | 0.253 | 6.33 | 2.814 | core |  |
| 25 | [Concerning the Advent of | 84 | 8.33 | 4.76 | 0.00 | 0.00 | 0.00 | 0.583 | 0.00 | 0.000 | core |  |
| 26 | Concerning the First Man  | 283 | 4.24 | 2.12 | 0.00 | 0.00 | 0.00 | 0.466 | 1.41 | 2.842 | core |  |
| 27 | Concerning the Five Forms | 590 | 3.39 | 0.51 | 0.00 | 0.00 | 1.02 | 0.395 | 2.03 | 0.339 | core |  |
| 28 | [Concerning the T]welve J | 769 | 6.96 | 3.25 | 0.39 | 0.00 | 0.26 | 0.378 | 1.04 | 2.608 | core |  |
| 29 | Concerning the Eighteen G | 584 | 9.16 | 3.60 | 0.17 | 0.00 | 0.68 | 0.339 | 0.86 | 2.740 | core |  |
| 30 | Concerning the Three Garm | 174 | 0.29 | 0.57 | 0.57 | 0.00 | 0.00 | 0.523 | 6.32 | 0.000 | mixed |  |
| 31 | Concerning the Summons, i | 449 | 4.45 | 2.00 | 0.00 | 0.22 | 0.45 | 0.432 | 3.56 | 1.345 | core |  |
| 32 | Concerning the Seven Work | 301 | 5.98 | 3.32 | 0.00 | 0.00 | 0.00 | 0.522 | 1.99 | 4.009 | core |  |
| 33 | Concerning the Five Thing | 89 | 4.49 | 3.37 | 0.00 | 0.00 | 0.00 | 0.596 | 0.00 | 6.818 | core |  |
| 34 | Concerning the Ten Things | 132 | 3.03 | 2.27 | 0.00 | 0.00 | 0.00 | 0.598 | 0.76 | -1.515 | core |  |
| 35 | Concerning the Four Works | 115 | 3.91 | 1.74 | 0.00 | 0.00 | 0.87 | 0.583 | 2.61 | 0.030 | core |  |
| 36 | Concerning the Wheel that | 342 | 5.70 | 2.63 | 0.00 | 0.00 | 0.29 | 0.418 | 1.75 | 0.585 | core |  |
| 37 | Concerning the Three Zone | 145 | 8.62 | 4.14 | 0.00 | 0.00 | 0.69 | 0.524 | 0.69 | -2.702 | core |  |
| 38 | Concerning the Light Mind | 4277 | 2.77 | 1.59 | 0.63 | 0.05 | 0.23 | 0.252 | 2.57 | 1.357 | secondary | ✅ |
| 39 | Concerning the Three Days | 709 | 4.66 | 1.83 | 0.28 | 0.14 | 0.56 | 0.398 | 1.13 | 1.415 | core | ✅ |
| 40 | Concerning the Three Thin | 292 | 1.71 | 1.37 | 0.68 | 0.00 | 0.00 | 0.514 | 2.40 | 1.370 | secondary | ✅ |
| 41 | Concerning the Three Blow | 241 | 2.70 | 0.83 | 0.00 | 0.00 | 0.41 | 0.519 | 0.00 | 1.667 | secondary | ✅ |
| 42 | Concerning the Three Vess | 1624 | 4.83 | 2.46 | 0.12 | 0.00 | 0.06 | 0.312 | 2.71 | 2.709 | core |  |
| 43 | Concerning the Vessels. | 836 | 4.90 | 2.75 | 0.00 | 0.24 | 0.00 | 0.310 | 0.72 | -1.196 | core |  |
| 44 | Concerning the Sea Giant | 821 | 4.38 | 2.31 | 0.00 | 0.00 | 0.00 | 0.364 | 1.34 | 2.198 | core |  |
| 45 | Concerning the Vessels | 365 | 7.12 | 3.56 | 0.00 | 0.00 | 0.00 | 0.455 | 2.19 | 1.663 | core |  |
| 46 | Concerning the Ambassador | 327 | 1.22 | 1.83 | 1.22 | 0.31 | 0.00 | 0.511 | 0.31 | 0.004 | secondary |  |
| 47 | Concerning the Four great | 732 | 1.37 | 0.82 | 0.00 | 0.00 | 0.00 | 0.380 | 0.82 | 1.639 | secondary |  |
| 48 | Concerning the Conduits. | 1515 | 2.94 | 1.32 | 0.07 | 0.07 | 0.26 | 0.263 | 1.91 | 0.662 | secondary |  |
| 49 | Concerning the Wheel and  | 243 | 1.65 | 0.82 | 0.00 | 0.00 | 0.00 | 0.494 | 0.00 | 0.007 | secondary |  |
| 50 | Concerning these Names: G | 394 | 5.20 | 1.52 | 0.00 | 0.00 | 0.76 | 0.393 | 0.25 | 0.000 | core |  |
| 51 | Concerning the First Man. | 262 | 3.24 | 1.91 | 0.38 | 0.00 | 0.00 | 0.500 | 3.05 | 4.580 | core |  |
| 52 | Concerning the [ ... ] of | 394 | -0.89 | 0.00 | 0.25 | 0.00 | 0.00 | 0.434 | 2.54 | 0.508 | pastoral |  |
| 53 | Concerning the First Man. | 368 | 13.31 | 5.71 | 0.00 | 0.00 | 0.00 | 0.397 | 4.08 | 5.978 | core |  |
| 54 | [Concerning] the Quality  | 428 | 5.72 | 2.80 | 0.00 | 0.00 | 0.23 | 0.428 | 8.18 | 3.738 | core |  |
| 55 | Concerning the Fashioning | 1169 | 6.89 | 2.05 | 0.00 | 0.00 | 1.11 | 0.337 | 2.40 | -1.707 | core | ✅ |
| 56 | [Concerning Saklas and hi | 2181 | 3.05 | 0.78 | 0.46 | 0.09 | 1.05 | 0.282 | 0.73 | 0.275 | core | ✅ |
| 57 | Concerning the Generation | 1094 | -0.27 | 0.18 | 0.37 | 0.00 | 0.00 | 0.335 | 0.27 | 0.366 | pastoral |  |
| 58 | The Four Powers that grie | 344 | 0.87 | 1.16 | 0.58 | 0.00 | 0.00 | 0.515 | 0.29 | 2.326 | secondary |  |
| 59 | The Chapter of the Elemen | 802 | 0.50 | 0.62 | 0.50 | 0.00 | 0.00 | 0.370 | 0.62 | 1.247 | mixed |  |
| 60 | [Concerning the Four Fath | 452 | 2.43 | 1.33 | 0.00 | 0.00 | 0.00 | 0.418 | 0.00 | -0.885 | secondary |  |
| 61 | Concerning the Garment of | 816 | 1.41 | 0.98 | 0.12 | 0.12 | 0.00 | 0.393 | 4.04 | -1.226 | secondary |  |
| 62 | Concerning the Three Rock | 236 | 4.03 | 2.12 | 0.85 | 0.00 | 0.42 | 0.492 | 0.00 | 2.542 | core | ✅ |
| 63 | Concerning Love. | 360 | 2.78 | 1.39 | 1.11 | 0.00 | 0.00 | 0.481 | 0.83 | -1.667 | secondary |  |
| 64 | [Concerning Adam] | 595 | 7.73 | 0.50 | 0.00 | 0.00 | 2.69 | 0.385 | 0.17 | 0.338 | core |  |
| 65 | Concerning the Sun. | 1862 | 0.75 | 0.27 | 0.05 | 0.05 | 0.16 | 0.285 | 0.16 | -0.215 | secondary |  |
| 66 | Concerning the Ambassador | 501 | 0.20 | 0.40 | 0.40 | 0.00 | 0.00 | 0.461 | 0.20 | 1.597 | mixed |  |
| 67 | Concerning the Light-Give | 236 | -0.42 | 0.00 | 1.69 | 0.00 | 0.85 | 0.547 | 0.00 | 0.000 | pastoral |  |
| 68 | Concerning Fire. | 116 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.595 | 0.00 | 0.000 | mixed |  |
| 69 | Concerning the Twelve Sig | 935 | 2.19 | 0.86 | 0.00 | 0.00 | 0.11 | 0.359 | 0.11 | 0.002 | secondary |  |
| 70 | Concerning the Body: It w | 1761 | 5.42 | 2.16 | 0.23 | 0.00 | 0.62 | 0.315 | 0.40 | 2.046 | core | ✅ |
| 71 | Concerning the Gathering  | 131 | 5.72 | 3.82 | 0.76 | 0.00 | 0.00 | 0.511 | 0.00 | -3.007 | core | ✅ |
| 72 | Concerning the worn and t | 724 | 3.25 | 1.80 | 0.14 | 0.00 | 0.00 | 0.442 | 1.38 | 1.657 | core | ✅ |
| 73 | Concerning the Envy of Ma | 566 | 1.94 | 0.35 | 0.88 | 0.18 | 1.24 | 0.463 | 1.77 | 1.060 | secondary |  |
| 74 | Concerning the living Fir | 339 | 6.49 | 2.65 | 0.00 | 0.00 | 0.59 | 0.425 | 1.47 | -1.754 | core | ✅ |
| 75 | [Concerning the Letter (? | 397 | 2.14 | 3.02 | 2.27 | 0.25 | 0.00 | 0.398 | 2.27 | 10.078 | secondary | ✅ |
| 76 | [Conce]rning Lord Manicha | 1655 | -0.45 | 0.12 | 0.42 | 0.00 | 0.00 | 0.286 | 1.27 | 0.121 | pastoral |  |
| 77 | The Chapter of the Four K | 411 | -2.80 | 0.00 | 1.70 | 0.00 | 0.00 | 0.421 | 1.22 | 2.425 | pastoral |  |
| 78 | Concerning the Four Thing | 224 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.536 | 4.91 | 0.000 | mixed |  |
| 79 | Concerning the Fasting of | 222 | -3.60 | 0.45 | 2.70 | 0.00 | 0.00 | 0.532 | 0.90 | 0.901 | pastoral |  |
| 80 | The Chapter of the Comman | 476 | -6.41 | 0.21 | 4.20 | 0.42 | 0.21 | 0.410 | 1.89 | 4.622 | pastoral |  |
| 81 | The Chapter of Fasting, f | 1055 | -2.84 | 0.09 | 1.71 | 0.19 | 0.00 | 0.360 | 3.32 | -1.709 | pastoral |  |
| 82 | The Chapter of Righteous  | 909 | -0.71 | 0.00 | 0.77 | 0.00 | 0.22 | 0.353 | 8.80 | -1.102 | pastoral |  |
| 83 | Concerning the Man who is | 1216 | -0.08 | 0.58 | 0.90 | 0.00 | 0.08 | 0.331 | 2.22 | -0.987 | pastoral |  |
| 84 | Concerning Wisdom; it is  | 1234 | -0.00 | 0.08 | 0.00 | 0.00 | 0.00 | 0.299 | 0.41 | -0.162 | mixed |  |
| 85 | Concerning the Cross of L | 1754 | -0.71 | 0.63 | 1.60 | 0.00 | 0.17 | 0.304 | 2.39 | 0.798 | pastoral | ✅ |
| 86 | The Chapter of the Man wh | 1061 | 0.28 | 0.38 | 0.28 | 0.09 | 0.09 | 0.345 | 0.94 | 0.189 | mixed | ✅ |
| 87 | Concerning the Alms, that | 656 | -5.95 | 0.91 | 6.10 | 0.00 | 0.00 | 0.345 | 0.46 | -3.659 | pastoral |  |
| 88 | Concerning the Catechumen | 804 | 0.06 | 0.37 | 1.12 | 0.00 | 0.25 | 0.417 | 1.87 | -0.000 | pastoral |  |
| 89 | The Chapter of the Nazore | 664 | -1.35 | 0.00 | 0.60 | 0.15 | 0.00 | 0.420 | 0.30 | 0.602 | pastoral |  |
| 90 | Concerning the Fifteen Pa | 1447 | -2.14 | 0.41 | 1.66 | 0.21 | 0.00 | 0.323 | 0.48 | 0.551 | pastoral |  |
| 91 | Also concerning the Catec | 2071 | -4.22 | 0.34 | 3.38 | 0.10 | 0.14 | 0.291 | 1.06 | -0.486 | pastoral |  |
| 92 | The Apostle is asked: Why | 366 | -3.01 | 0.55 | 3.28 | 0.00 | 0.00 | 0.396 | 4.64 | 3.279 | pastoral |  |
| 93 | A Catechumen asked the Ap | 717 | -1.32 | 0.84 | 2.23 | 0.00 | 0.14 | 0.358 | 7.39 | -0.562 | pastoral |  |
| 94 | Concerning the Purificati | 329 | 3.50 | 2.13 | 0.30 | 0.00 | 0.00 | 0.438 | 2.13 | -1.205 | core |  |
| 95 | The Apostle asks his Disc | 1170 | 3.21 | 1.37 | 0.09 | 0.09 | 0.34 | 0.303 | 2.99 | -0.855 | core |  |
| 96 | The Three Earths that Exi | 424 | 0.35 | 0.71 | 0.71 | 0.00 | 0.00 | 0.467 | 2.12 | -0.943 | mixed |  |
| 97 | Concerning the Three Crea | 245 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.510 | 6.12 | 0.000 | mixed |  |
| 98 | What is Virginal; or, oth | 486 | 2.88 | 0.82 | 0.41 | 0.00 | 0.82 | 0.391 | 0.62 | -0.823 | secondary |  |
| 99 | Concerning Transmigration | 400 | -1.88 | 0.25 | 2.00 | 0.00 | 0.25 | 0.405 | 4.75 | -0.500 | pastoral |  |
| 100 | Concerning the Dragon wit | 476 | 0.32 | 0.00 | 0.21 | 0.21 | 0.42 | 0.437 | 3.15 | 0.420 | pastoral |  |
| 101 | [Concer]ning why, if the  | 490 | 0.82 | 0.61 | 0.00 | 0.20 | 0.00 | 0.418 | 0.61 | 1.224 | secondary |  |
| 102 | Concerning the Light Mind | 479 | -1.04 | 0.63 | 1.25 | 0.21 | 0.00 | 0.428 | 0.84 | -1.255 | pastoral |  |
| 103 | Concerning the Five Wonde | 204 | 0.24 | 1.47 | 1.47 | 0.00 | 0.00 | 0.559 | 3.43 | -3.922 | mixed |  |
| 104 | Concerning Food: It shall | 170 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.559 | 0.00 | 0.000 | mixed |  |
| 105 | Concerning the Three Thin | 260 | -2.12 | 0.00 | 0.38 | 0.77 | 0.00 | 0.550 | 0.38 | 0.769 | pastoral |  |
| 106 | There is no Joy that shal | 329 | 1.82 | 0.91 | 0.00 | 0.00 | 0.00 | 0.489 | 0.61 | -0.602 | secondary |  |
| 107 | Concerning the Form of th | 150 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.553 | 0.00 | 0.000 | mixed |  |
| 108 | Concerning the Seed Grain | 191 | 3.67 | 1.05 | 0.00 | 0.00 | 0.00 | 0.529 | 3.66 | 0.011 | core |  |
| 109 | Concerning the Fifty Lord | 548 | 1.09 | 0.91 | 1.09 | 0.00 | 0.36 | 0.387 | 2.01 | 2.555 | secondary | ✅ |
| 110 | Concerning the Nourishmen | 108 | 3.70 | 1.85 | 0.00 | 0.00 | 0.00 | 0.565 | 5.56 | 0.000 | core |  |
| 111 | Concerning the Four Arche | 161 | 1.24 | 0.62 | 0.00 | 0.00 | 0.00 | 0.547 | 9.94 | -1.235 | secondary |  |
| 112 | The Human is less than al | 802 | 0.37 | 0.37 | 0.00 | 0.12 | 0.00 | 0.401 | 1.37 | -0.249 | mixed |  |
| 113 | The Chapter on whether an | 168 | 3.57 | 2.38 | 0.00 | 0.60 | 0.00 | 0.589 | 4.76 | 0.000 | core |  |
| 114 | Concerning the Three Imag | 407 | 7.25 | 2.46 | 0.49 | 0.00 | 1.23 | 0.405 | 1.23 | 0.010 | core | ✅ |
| 115 | The Catechumen asks the A | 2486 | 1.35 | 1.97 | 1.97 | 0.08 | 0.08 | 0.223 | 6.11 | 2.735 | secondary | ✅ |
| 116 | Concerning why if a [Nail | 307 | -0.33 | 0.00 | 0.00 | 0.00 | 0.00 | 0.420 | 3.91 | 0.000 | mixed |  |
| 117 | Concerning why Some shall | 122 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.484 | 3.28 | 0.000 | mixed |  |
| 118 | [ ... ] | 66 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.515 | 10.61 | 0.000 | mixed |  |
| 119 | [ ... ] | 494 | 5.06 | 1.82 | 1.62 | 0.00 | 1.62 | 0.405 | 3.24 | 1.215 | core |  |
| 120 | Concerning the Two Essenc | 524 | 0.29 | 0.19 | 0.38 | 0.00 | 0.19 | 0.416 | 4.96 | 0.382 | pastoral |  |
| 121 | Concerning the Sect of th | 535 | -0.09 | 0.93 | 0.75 | 0.56 | 0.19 | 0.361 | 10.65 | 1.122 | mixed |  |
| 122 | Concerning the 'Assent' a | 899 | 0.45 | 1.22 | 1.33 | 0.00 | 0.00 | 0.316 | 9.01 | 1.557 | pastoral | ✅ |
