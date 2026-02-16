# Kephalaia Layer Analysis — Computational Results

**Date**: 2026-02-16
**Source**: Kephalaia of the Teacher (Gardner 1995, OCR'd)
**Chapters analyzed**: 78
**Manual Layer 1 chapters**: 14

---

## 1. Computational vs. Manual Classification Agreement

| Metric | Value |
|--------|-------|
| Total chapters | 78 |
| True Positive (both say L1) | 13 |
| True Negative (both say not L1) | 17 |
| False Positive (computed L1, manual excluded) | 47 |
| False Negative (computed not L1, manual included) | 1 |
| **Agreement** | **38.5%** |
| **Cohen's κ** | **0.085** |

### Chapters in Layer 1 Extract but Computationally Flagged (False Negatives)

These chapters are in our manual Layer 1 extract but have negative purity scores:

- **Ch. 122** (Concerning the 'Assent' and the 'Amen'): purity=-5.76, L1=3.13, L2=0.20, L3=0.20
  - L2 terms: son of god (2), grace (1), jesus christ (2), paul (1), john (1)
  - L3 terms: paraclete (6), the holy church (1)

### Chapters Excluded but Computationally Pure (False Positives)

These chapters were excluded from Layer 1 but have positive purity — potential candidates for restoration:

- **Ch. 113** (The Chapter on whether any [Lig] /ht comes from the Three Vessels.): purity=3.60, L1=3.60, L2=0.00, L3=0.00
  - L1 terms: purification (1), eight earths (1), living spirit (1), vessels (5), firmaments (2)
- **Ch. 117** (Concerning why Some shall delay to come): purity=3.23, L1=3.23, L2=0.00, L3=0.00
  - L1 terms: matter (1)
- **Ch. 49** (Concerning the Whleel and the Conduits].): purity=3.02, L1=3.59, L2=0.00, L3=0.57
  - L1 terms: land of light (3), great spirit (2), beloved of the lights (2), emanation (4), descent (1), ambassador (1), evocation (6)
- **Ch. 28** (Concerning the T]welve 15 Judges [of] the Father): purity=2.61, L1=2.90, L2=0.04, L3=0.24
  - L1 terms: land of light (1), separation (2), new aeon (2), summons (6), great spirit (2), mother of life (1), king of honour (2), light mind (1)
- **Ch. 36** (Concerning the Wheel that exists): purity=2.45, L1=2.63, L2=0.00, L3=0.18
  - L1 terms: king of honour (5), living spirit (3), five sons (3), first man (1), mixture (1), firmaments (2)
- **Ch. 25** (Concerning the Advent of Five Fathers / from the Five Limbs of the Father]): purity=2.33, L1=3.49, L2=0.00, L3=1.16
  - L1 terms: mother of life (1), beloved of the lights (1), five limbs (1)
- **Ch. 17** (The Chapter of the / Thrlee] Seasons.): purity=2.17, L1=2.17, L2=0.00, L3=0.00
  - L1 terms: land of light (1), mother of life (2), living spirit (2), ascent (1), ambassador (5), first man (4)
- **Ch. 15** (Concerning the): purity=2.15, L1=2.23, L2=0.00, L3=0.08
  - L1 terms: hearer (1), father of greatness (1), summons (5), great spirit (1), mother of life (1), land of darkness (2), second time (1), emanation (2)
- **Ch. 10** (Concerning the Interpretation of the Fourteen [great AJeons, / about which Sethel has spoken in [his PJrayer): purity=2.08, L1=2.08, L2=0.00, L3=0.00
  - L1 terms: living spirit (2), five sons (1), five elements (2), ambassador (2), first man (1)
- **Ch. 93** (A Catechumen asked the Apo/stle: When I would give an Offer10ing to the Saints, ): purity=2.06, L1=2.06, L2=0.00, L3=0.00
  - L1 terms: purification (1), elect (2), matter (2), living soul (5), catechumen (4)
- **Ch. 44** (Concerning the Sea): purity=1.99, L1=2.19, L2=0.00, L3=0.20
  - L1 terms: matter (1), ascent (1), three wheels (1), vessels (4), firmaments (2), king of glory (1), ten firmaments (1)
- **Ch. 79** (Concerning the Fasting of the Saints): purity=1.76, L1=2.75, L2=0.44, L3=0.55
  - L1 terms: elect (4), cross of light (1), matter (1), living soul (1), righteousness (8), catechumen (10)
- **Ch. 102** (Concerning the Light Mind, why): purity=1.64, L1=1.91, L2=0.27, L3=0.00
  - L1 terms: elect (3), light mind (1), matter (1), righteousness (2)
- **Ch. 51** (Concerning the First Man.): purity=1.56, L1=1.72, L2=0.00, L3=0.16
  - L1 terms: land of darkness (2), matter (5), living spirit (1), descent (1), first man (3), storehouses (10)
- **Ch. 45** (Concerning the Vessels.): purity=1.52, L1=1.52, L2=0.00, L3=0.00
  - L1 terms: matter (2), righteousness (1), adamant of light (1), vessels (3)
- **Ch. 34** (Concerning the Ten Things that the Am[bassa]): purity=1.48, L1=2.08, L2=0.00, L3=0.59
  - L1 terms: purification (1), new aeon (1), ascent (1), living soul (1), ambassador (2), great builder (1)
- **Ch. 43** (Concerning the Vessels.): purity=1.43, L1=1.87, L2=0.22, L3=0.22
  - L1 terms: porter (1), living spirit (2), ascent (1), dark elements (2), light elements (2), vessels (6), firmaments (3)
- **Ch. 106** (25 There is no Joy that shall remain / in the World till the End.): purity=1.34, L1=1.67, L2=0.00, L3=0.33
  - L1 terms: summons (1), living soul (3), mixture (1)
- **Ch. 11** (Concerning the Interpretation of] all [ the] Fathers of / [Light], who are distinguished from one another): purity=1.33, L1=1.56, L2=0.22, L3=0.00
  - L1 terms: virgin of light (1), light mind (1), porter (1), five sons (1), ambassador (1), great builder (1), pillar of glory (1)
- **Ch. 26** (Concerning the First Man and the Ambassa): purity=1.16, L1=1.27, L2=0.00, L3=0.12
  - L1 terms: new aeon (1), great spirit (1), matter (1), living spirit (2), living soul (2), ambassador (1), first man (2), five worlds (1)
- **Ch. 119** ((284,? - 286,23 ) [ ... ]): purity=1.05, L1=1.31, L2=0.00, L3=0.26
  - L1 terms: five sons (1), first man (3), catechumen (1)
- **Ch. 108** (Concerning the Seed Grain that shall be / formed by the Elements, [a]/nd also be destroyed by them): purity=1.03, L1=1.55, L2=0.00, L3=0.52
  - L1 terms: matter (1), five elements (1), righteousness (1)
- **Ch. 13** (Concer[ning] the Five Saviours, the Resurrectors / of they who are Dead; togethe): purity=1.02, L1=1.02, L2=0.00, L3=0.00
  - L1 terms: light mind (1)
- **Ch. 54** ([Concern]ing the Quality of the Garments.): purity=0.95, L1=1.19, L2=0.05, L3=0.19
  - L1 terms: purification (1), hearer (1), mother of life (1), light mind (8), five garments (1), second time (1), matter (10), living spirit (5)
- **Ch. 97** (Concerning the Three Creations of the Flesh: the ones): purity=0.88, L1=1.12, L2=0.00, L3=0.24
  - L1 terms: light mind (2), matter (1), descent (1), ambassador (1), mixture (2), catechumen (6), great fire (1)
- **Ch. 96** (The Three Earths that ex/ist, they bear Fruit.): purity=0.85, L1=1.14, L2=0.00, L3=0.28
  - L1 terms: elect (1), light mind (1), righteousness (1), catechumen (1)
- **Ch. 67** (Concerning the Light-Giver.): purity=0.83, L1=1.24, L2=0.00, L3=0.41
  - L1 terms: elect (3)
- **Ch. 77** (The Chapter of the Four Klingdoms].): purity=0.72, L1=1.52, L2=0.00, L3=0.30
  - L1 terms: last day (1), catechumen (4)
- **Ch. 111** (Concerning the Four Archetypes that occur / in the Eye, and the Fifth that is hidden / in them; to whom do they belong? /): purity=0.72, L1=0.72, L2=0.00, L3=0.00
  - L1 terms: matter (1)
- **Ch. 48** (Concerning the Conduits.): purity=0.72, L1=1.11, L2=0.00, L3=0.39
  - L1 terms: cross of light (1), matter (2), living spirit (3), ambassador (3), five trees (1), five worlds (2), firmaments (5)
- **Ch. 46** (Concerning the Ambassador.): purity=0.64, L1=0.64, L2=0.00, L3=0.00
  - L1 terms: new aeon (1), great builder (1)
- **Ch. 101** ([Concer]ning why, if the Person shall look down / into Water, [ ... ]): purity=0.61, L1=1.02, L2=0.20, L3=0.20
  - L1 terms: summons (2), obedience (1), first man (2)
- **Ch. 42** (Concerning the Three): purity=0.60, L1=0.86, L2=0.07, L3=0.20
  - L1 terms: purification (1), living spirit (2), vessels (9), firmaments (1)
- **Ch. 73** (Concerning the Envy of Matter): purity=0.58, L1=0.96, L2=0.00, L3=0.38
  - L1 terms: matter (1), first man (1), catechumen (2), thought of death (1)
- **Ch. 69** (Concerning the Twelve Signs of the Zodi): purity=0.55, L1=0.55, L2=0.00, L3=0.00
  - L1 terms: land of darkness (1), matter (1), five worlds (2), vessels (1)
- **Ch. 61** (Concerning the Garment of the Waters:): purity=0.52, L1=0.86, L2=0.17, L3=0.17
  - L1 terms: elect (1), descent (1), first man (2), first time (1)
- **Ch. 91** (Also concerning the Catechumen; / shall he be saved in a single Body ?): purity=0.49, L1=1.84, L2=0.10, L3=0.26
  - L1 terms: land of light (1), purification (2), elect (10), ascent (2), catechumen (21)
- **Ch. 100** (Concerning the Dragon with Fourte[en] He[ads];): purity=0.45, L1=0.45, L2=0.00, L3=0.00
  - L1 terms: elect (1)
- **Ch. 81** (The Chapter of Fasting, for 25 it engenders a Host of Angels.): purity=0.32, L1=0.75, L2=0.21, L3=0.21
  - L1 terms: elect (4), matter (2), catechumen (1)
- **Ch. 121** (Concerning the Sect of the Basket): purity=0.28, L1=0.84, L2=0.28, L3=0.28
  - L1 terms: summons (1), porter (1), obedience (1)
- **Ch. 47** (Concerning the Four 15 great Things.): purity=0.27, L1=0.41, L2=0.00, L3=0.14
  - L1 terms: eight earths (1), vessels (2)
- **Ch. 88** (Concerning the Catechumen who found): purity=0.25, L1=0.37, L2=0.12, L3=0.00
  - L1 terms: elect (1), catechumen (2)
- **Ch. 103** (Concerning the Five Wonders 10 that the Light Mind shall): purity=0.23, L1=0.69, L2=0.00, L3=0.46
  - L1 terms: elect (2), light mind (1)
- **Ch. 60** (Concerning the Four Fathers; / what they are like): purity=0.21, L1=0.43, L2=0.00, L3=0.21
  - L1 terms: living soul (1), storehouses (1)
- **Ch. 64** ([Concerning/ Adam.): purity=0.18, L1=0.36, L2=0.00, L3=0.18
  - L1 terms: ascent (1), five sons (1)
- **Ch. 112** (The Human is less than all the Things 5 of the Universe, and he is rebellious be): purity=0.13, L1=0.39, L2=0.13, L3=0.13
  - L1 terms: cross of light (1), righteousness (2)
- **Ch. 94** (Concerning the Purification of these Four Elements [that have been place]d in the Flesh.): purity=0.12, L1=0.43, L2=0.00, L3=0.31
  - L1 terms: virgin of light (2), elect (1), light mind (1), porter (1), ambassador (1), light elements (1)

---

## 2. Purest Layer 1 Chapters (by Purity Score)

| Rank | Ch. | Title | Purity | L1 | L2 | L3 | In Extract |
|------|-----|-------|--------|----|----|----|-----------:|
| 1 | 113 | The Chapter on whether any [Lig] /ht com | 3.60 | 3.60 | 0.00 | 0.00 | ❌ |
| 2 | 117 | Concerning why Some shall delay to come | 3.23 | 3.23 | 0.00 | 0.00 | ❌ |
| 3 | 71 | Concerning the Gathering in | 3.03 | 3.79 | 0.00 | 0.76 | ✅ |
| 4 | 49 | Concerning the Whleel and the Conduits]. | 3.02 | 3.59 | 0.00 | 0.57 | ❌ |
| 5 | 74 | Concerning the living Fire: | 2.74 | 2.74 | 0.00 | 0.00 | ✅ |
| 6 | 28 | Concerning the T]welve 15 Judges [of] th | 2.61 | 2.90 | 0.04 | 0.24 | ❌ |
| 7 | 36 | Concerning the Wheel that exists | 2.45 | 2.63 | 0.00 | 0.18 | ❌ |
| 8 | 25 | Concerning the Advent of Five Fathers /  | 2.33 | 3.49 | 0.00 | 1.16 | ❌ |
| 9 | 17 | The Chapter of the / Thrlee] Seasons. | 2.17 | 2.17 | 0.00 | 0.00 | ❌ |
| 10 | 15 | Concerning the | 2.15 | 2.23 | 0.00 | 0.08 | ❌ |
| 11 | 10 | Concerning the Interpretation of the Fou | 2.08 | 2.08 | 0.00 | 0.00 | ❌ |
| 12 | 93 | A Catechumen asked the Apo/stle: When I  | 2.06 | 2.06 | 0.00 | 0.00 | ❌ |
| 13 | 44 | Concerning the Sea | 1.99 | 2.19 | 0.00 | 0.20 | ❌ |
| 14 | 115 | The Catechumen asks / the Apostle: will  | 1.91 | 2.08 | 0.04 | 0.12 | ✅ |
| 15 | 79 | Concerning the Fasting of the Saints | 1.76 | 2.75 | 0.44 | 0.55 | ❌ |
| 16 | 102 | Concerning the Light Mind, why | 1.64 | 1.91 | 0.27 | 0.00 | ❌ |
| 17 | 70 | Concerning the Body: It was 25 construct | 1.62 | 1.73 | 0.00 | 0.11 | ✅ |
| 18 | 51 | Concerning the First Man. | 1.56 | 1.72 | 0.00 | 0.16 | ❌ |
| 19 | 45 | Concerning the Vessels. | 1.52 | 1.52 | 0.00 | 0.00 | ❌ |
| 20 | 34 | Concerning the Ten Things that the Am[ba | 1.48 | 2.08 | 0.00 | 0.59 | ❌ |

## 3. Most Contaminated Chapters (by L2+L3 Density)

| Rank | Ch. | Title | Purity | L1 | L2 | L3 | In Extract |
|------|-----|-------|--------|----|----|----|-----------:|
| 1 | 122 | Concerning the 'Assent' and the 'Amen' | -5.76 | 3.13 | 0.20 | 0.20 | ✅ |
| 2 | 105 | Concerning the Three Things that are gre | -1.40 | 0.00 | 0.93 | 0.47 | ❌ |
| 3 | 82 | The Chapter of / Righteous [Judgement]. | -1.39 | 0.77 | 0.00 | 0.15 | ❌ |
| 4 | 76 | [Conce]rning Lord Manichaios: / how he j | -1.09 | 0.00 | 0.00 | 0.09 | ❌ |
| 5 | 65 | Concerning the Sun | -1.03 | 0.12 | 0.18 | 0.47 | ❌ |
| 6 | 63 | Concerning Love. | -1.00 | 0.79 | 0.00 | 0.79 | ❌ |
| 7 | 78 | Concerning the Four Things over which Pe | -0.45 | 0.00 | 0.00 | 0.45 | ❌ |
| 8 | 18 | Concerning the Five] War[s that the] Son | -0.44 | 1.70 | 0.00 | 0.14 | ❌ |
| 9 | 89 | The Chapter of the Nazo2 rean who questi | -0.34 | 0.97 | 0.22 | 0.09 | ❌ |
| 10 | 84 | Concerning Wisdom; it is far superior wh | -0.29 | 0.96 | 0.04 | 0.21 | ❌ |
| 11 | 66 | Concerning the Ambassador. | -0.22 | 0.22 | 0.00 | 0.44 | ❌ |
| 12 | 14 | The Interpretation [of] the S[i]lence, t | 0.00 | 0.00 | 0.00 | 0.00 | ❌ |
| 13 | 68 | Concerning Fire. | 0.00 | 0.00 | 0.00 | 0.00 | ❌ |
| 14 | 107 | Concerning the Form of the Word, that [  | 0.00 | 0.00 | 0.00 | 0.00 | ❌ |
| 15 | 110 | Concerning the Nourishment of the Person | 0.00 | 0.00 | 0.00 | 0.00 | ❌ |
| 16 | 116 | Concerning why if a [Nail] is cut | 0.00 | 0.00 | 0.00 | 0.00 | ❌ |
| 17 | 118 | The mostly destroyed leaves 283-284 perh | 0.00 | 0.00 | 0.00 | 0.00 | ❌ |
| 18 | 120 | Concerning the Two Essences | 0.00 | 0.00 | 0.00 | 0.00 | ❌ |
| 19 | 94 | Concerning the Purification of these Fou | 0.12 | 0.43 | 0.00 | 0.31 | ❌ |
| 20 | 112 | The Human is less than all the Things 5  | 0.13 | 0.39 | 0.13 | 0.13 | ❌ |

## 4. Editor Fatigue — Highest Intra-Chapter Shifts

Chapters where Layer 2 vocabulary increases significantly in the second half
relative to Layer 1 (suggesting interpolated material was added to an original core):

| Ch. | Title | Shift Score | 1st Half L1 | 2nd Half L1 | 1st Half L2 | 2nd Half L2 |
|-----|-------|-------------|-------------|-------------|-------------|-------------|
| 75 | Concerning the Letter (?)] / | 5.211 | 5.73 | 0.52 | 0.00 | 0.00 |
| 70 | Concerning the Body: It was 25 cons | 3.468 | 3.58 | 0.11 | 0.00 | 0.00 |
| 113 | The Chapter on whether any [Lig] /h | 2.878 | 5.04 | 2.16 | 0.00 | 0.00 |
| 74 | Concerning the living Fire: | 2.769 | 4.59 | 1.82 | 0.00 | 0.00 |
| 11 | Concerning the Interpretation of] a | 2.667 | 3.56 | 0.44 | 0.44 | 0.00 |
| 25 | Concerning the Advent of Five Fathe | 2.326 | 4.65 | 2.33 | 0.00 | 0.00 |
| 45 | Concerning the Vessels. | 2.174 | 2.61 | 0.43 | 0.00 | 0.00 |
| 26 | Concerning the First Man and the Am | 2.089 | 2.55 | 0.46 | 0.00 | 0.00 |
| 13 | Concer[ning] the Five Saviours, the | 2.041 | 2.04 | 0.00 | 0.00 | 0.00 |
| 15 | Concerning the | 1.938 | 3.45 | 1.52 | 0.00 | 0.00 |
| 122 | Concerning the 'Assent' and the 'Am | 1.864 | 4.12 | 2.43 | 0.11 | 0.28 |
| 103 | Concerning the Five Wonders 10 that | 1.852 | 1.85 | 0.00 | 0.00 | 0.00 |
| 109 | Concerning the Fifty Lord's Days; | 1.794 | 3.59 | 1.79 | 0.00 | 0.00 |
| 34 | Concerning the Ten Things that the  | 1.793 | 2.98 | 1.18 | 0.00 | 0.00 |
| 62 | Concerning the Three Rocks. | 1.681 | 3.36 | 1.68 | 0.00 | 0.00 |

## 5. Gardner's Editorial Flags

| Ch. | Title | Flags |
|-----|-------|-------|
| 6 | Concerning the Five Storehouses that hav | redaction, corruption, secondary_material, textual_development, uncertain, parallel_text, gnostic_connection, canonical_source |
| 10 | Concerning the Interpretation of the Fou | gnostic_connection |
| 26 | Concerning the First Man and the Ambassa | uncertain |
| 41 | Concerning the Three Blows that | redaction |
| 48 | Concerning the Conduits. | uncertain |
| 65 | Concerning the Sun | redaction |
| 69 | Concerning the Twelve Signs of the Zodi | gnostic_connection |
| 70 | Concerning the Body: It was 25 construct | redaction |
| 73 | Concerning the Envy of Matter | mani_attribution |
| 89 | The Chapter of the Nazo2 rean who questi | christian_connection |
| 93 | A Catechumen asked the Apo/stle: When I  | uncertain |
| 94 | Concerning the Purification of these Fou | uncertain |
| 101 | [Concer]ning why, if the Person shall lo | redaction, textual_development |
| 105 | Concerning the Three Things that are gre | christian_connection |
| 120 | Concerning the Two Essences | uncertain, christian_connection |
| 121 | Concerning the Sect of the Basket | uncertain |
| 122 | Concerning the 'Assent' and the 'Amen' | christian_connection |

## 6. NT Citation Distribution

| Ch. | Title | NT Citations | In Extract |
|-----|-------|-------------|:----------:|
| 6 | Concerning the Five Storehouses that hav | *16 Mk., Mk. 12 | ✅ |
| 18 | Concerning the Five] War[s that the] Son | *20 Mt., *23 Phil., Mt. 3, Phil. 2 | ❌ |
| 63 | Concerning Love. | *91 Jn., Jn. 15 | ❌ |
| 65 | Concerning the Sun | Gospel of Thomas | ❌ |
| 75 | Concerning the Letter (?)] / | *98 Mt., Mt. 21 | ✅ |
| 76 | [Conce]rning Lord Manichaios: / how he j | *99 Jn., Jn. 3 | ❌ |
| 77 | The Chapter of the Four Klingdoms]. | Mt. 10 | ❌ |
| 82 | The Chapter of / Righteous [Judgement]. | *111 Mt., *114 Mt., Mt. 6, Mt. 18 | ❌ |
| 84 | Concerning Wisdom; it is far superior wh | *120 Mt., Mt. 6 | ❌ |
| 89 | The Chapter of the Nazo2 rean who questi | *123 Mt., Mt. 6 | ❌ |
| 91 | Also concerning the Catechumen; / shall  | *127 1 Cor., 1 Cor. 7 | ❌ |
| 109 | Concerning the Fifty Lord's Days; | Mt. 4, Mt. 26, Lk. 24 | ✅ |
| 122 | Concerning the 'Assent' and the 'Amen' | Mt. 3, Mt. 6, Mt.10, Mt. 18, Mt. 21, Mk.12, Lk. 6, Lk. 22, Jn. 3, Jn. 8, Jn. 15, Jn. 15, Jn. 16, Jn. 16, Cor. 7, Cor. 15, Phil. 2 | ✅ |

## 7. Formulaic Opening Analysis

- Chapters with formulaic opening: **44** (56.4%)
- Chapters without formulaic opening: **34** (43.6%)

Chapters without standard opening (possible different source):

- Ch. 10 (Concerning the Interpretation of the Fourteen [gre)
- Ch. 11 (Concerning the Interpretation of] all [ the] Fathe)
- Ch. 13 (Concer[ning] the Five Saviours, the Resurrectors /)
- Ch. 14 (The Interpretation [of] the S[i]lence, the Fast, [)
- Ch. 17 (The Chapter of the / Thrlee] Seasons.)
- Ch. 41 (Concerning the Three Blows that)
- Ch. 44 (Concerning the Sea)
- Ch. 45 (Concerning the Vessels.)
- Ch. 46 (Concerning the Ambassador.)
- Ch. 60 (Concerning the Four Fathers; / what they are like)
- Ch. 69 (Concerning the Twelve Signs of the Zodi)
- Ch. 74 (Concerning the living Fire:)
- Ch. 76 ([Conce]rning Lord Manichaios: / how he journeyed.)
- Ch. 78 (Concerning the Four Things over which Peo)
- Ch. 88 (Concerning the Catechumen who found)
- Ch. 89 (The Chapter of the Nazo2 rean who questions the Te)
- Ch. 91 (Also concerning the Catechumen; / shall he be save)
- Ch. 93 (A Catechumen asked the Apo/stle: When I would give)
- Ch. 100 (Concerning the Dragon with Fourte[en] He[ads];)
- Ch. 101 ([Concer]ning why, if the Person shall look down / )
- Ch. 102 (Concerning the Light Mind, why)
- Ch. 108 (Concerning the Seed Grain that shall be / formed b)
- Ch. 109 (Concerning the Fifty Lord's Days;)
- Ch. 110 (Concerning the Nourishment of the Person,)
- Ch. 112 (The Human is less than all the Things 5 of the Uni)
- Ch. 113 (The Chapter on whether any [Lig] /ht comes from th)
- Ch. 114 (Concerning the Three Images that / are in the righ)
- Ch. 115 (The Catechumen asks / the Apostle: will Rest / com)
- Ch. 116 (Concerning why if a [Nail] is cut)
- Ch. 118 (The mostly destroyed leaves 283-284 perhaps contai)
- Ch. 119 ((284,? - 286,23 ) [ ... ])
- Ch. 120 (Concerning the Two Essences)
- Ch. 121 (Concerning the Sect of the Basket)
- Ch. 122 (Concerning the 'Assent' and the 'Amen')

---

## Appendix: Full Chapter Scores

| Ch. | Title | Words | Purity | L1 | L2 | L3 | TTR | AvgSent | Lacunae | Shift | Extract |
|-----|-------|------:|-------:|---:|---:|---:|----:|--------:|--------:|------:|:-------:|
| 6 | Concerning the Five Storehouse | 4690 | 0.43 | 1.68 | 0.09 | 0.17 | 0.232 | 19.4 | 0.70 | 0.000 | ✅ |
| 10 | Concerning the Interpretation  | 385 | 2.08 | 2.08 | 0.00 | 0.00 | 0.465 | 15.4 | 0.78 | 1.571 | ❌ |
| 11 | Concerning the Interpretation  | 450 | 1.33 | 1.56 | 0.22 | 0.00 | 0.480 | 14.3 | 1.78 | 2.667 | ❌ |
| 13 | Concer[ning] the Five Saviours | 98 | 1.02 | 1.02 | 0.00 | 0.00 | 0.592 | 12.8 | 10.20 | 2.041 | ❌ |
| 14 | The Interpretation [of] the S[ | 18 | 0.00 | 0.00 | 0.00 | 0.00 | 0.778 | 6.7 | 11.11 | 0.000 | ❌ |
| 15 | Concerning the | 2374 | 2.15 | 2.23 | 0.00 | 0.08 | 0.307 | 16.3 | 1.43 | 1.938 | ❌ |
| 17 | The Chapter of the / Thrlee] S | 690 | 2.17 | 2.17 | 0.00 | 0.00 | 0.383 | 14.0 | 1.01 | 1.449 | ❌ |
| 18 | Concerning the Five] War[s tha | 4358 | -0.44 | 1.70 | 0.00 | 0.14 | 0.235 | 12.2 | 3.90 | -0.367 | ❌ |
| 25 | Concerning the Advent of Five  | 86 | 2.33 | 3.49 | 0.00 | 1.16 | 0.581 | 17.6 | 0.00 | 2.326 | ❌ |
| 26 | Concerning the First Man and t | 863 | 1.16 | 1.27 | 0.00 | 0.12 | 0.392 | 17.5 | 1.27 | 2.089 | ❌ |
| 28 | Concerning the T]welve 15 Judg | 2487 | 2.61 | 2.90 | 0.04 | 0.24 | 0.265 | 18.9 | 1.29 | -0.480 | ❌ |
| 34 | Concerning the Ten Things that | 337 | 1.48 | 2.08 | 0.00 | 0.59 | 0.499 | 16.0 | 0.89 | 1.793 | ❌ |
| 36 | Concerning the Wheel that exis | 571 | 2.45 | 2.63 | 0.00 | 0.18 | 0.361 | 17.6 | 1.05 | -1.042 | ❌ |
| 38 | Concerning the Light Mind and  | 5177 | 1.18 | 1.37 | 0.06 | 0.14 | 0.232 | 15.7 | 1.20 | 0.850 | ✅ |
| 40 | Concerning the Three Things th | 192 | 0.52 | 1.04 | 0.00 | 0.52 | 0.542 | 22.0 | 3.65 | -1.042 | ✅ |
| 41 | Concerning the Three Blows tha | 348 | 0.57 | 0.57 | 0.00 | 0.00 | 0.494 | 19.4 | 0.00 | 1.149 | ✅ |
| 42 | Concerning the Three | 1506 | 0.60 | 0.86 | 0.07 | 0.20 | 0.339 | 26.1 | 2.79 | 0.531 | ❌ |
| 43 | Concerning the Vessels. | 909 | 1.43 | 1.87 | 0.22 | 0.22 | 0.321 | 24.3 | 0.66 | 0.224 | ❌ |
| 44 | Concerning the Sea | 502 | 1.99 | 2.19 | 0.00 | 0.20 | 0.444 | 35.1 | 2.19 | 0.000 | ❌ |
| 45 | Concerning the Vessels. | 460 | 1.52 | 1.52 | 0.00 | 0.00 | 0.448 | 29.2 | 1.52 | 2.174 | ❌ |
| 46 | Concerning the Ambassador. | 311 | 0.64 | 0.64 | 0.00 | 0.00 | 0.514 | 25.5 | 0.32 | -1.282 | ❌ |
| 47 | Concerning the Four 15 great T | 738 | 0.27 | 0.41 | 0.00 | 0.14 | 0.352 | 25.0 | 0.81 | 0.813 | ❌ |
| 48 | Concerning the Conduits. | 1530 | 0.72 | 1.11 | 0.00 | 0.39 | 0.268 | 24.1 | 1.63 | -0.523 | ❌ |
| 49 | Concerning the Whleel and the  | 529 | 3.02 | 3.59 | 0.00 | 0.57 | 0.388 | 15.2 | 0.19 | 1.148 | ❌ |
| 51 | Concerning the First Man. | 1278 | 1.56 | 1.72 | 0.00 | 0.16 | 0.326 | 22.8 | 2.27 | -3.286 | ❌ |
| 54 | [Concern]ing the Quality of th | 6319 | 0.95 | 1.19 | 0.05 | 0.19 | 0.219 | 18.6 | 0.95 | -0.063 | ❌ |
| 60 | Concerning the Four Fathers; / | 468 | 0.21 | 0.43 | 0.00 | 0.21 | 0.421 | 20.1 | 0.00 | 0.855 | ❌ |
| 61 | Concerning the Garment of the  | 582 | 0.52 | 0.86 | 0.17 | 0.17 | 0.426 | 19.4 | 3.95 | -2.062 | ❌ |
| 62 | Concerning the Three Rocks. | 238 | 1.26 | 2.10 | 0.00 | 0.84 | 0.479 | 13.5 | 0.00 | 1.681 | ✅ |
| 63 | Concerning Love. | 254 | -1.00 | 0.79 | 0.00 | 0.79 | 0.496 | 18.3 | 0.79 | 0.787 | ❌ |
| 64 | [Concerning/ Adam. | 559 | 0.18 | 0.36 | 0.00 | 0.18 | 0.390 | 24.6 | 0.18 | 0.001 | ❌ |
| 65 | Concerning the Sun | 1690 | -1.03 | 0.12 | 0.18 | 0.47 | 0.277 | 19.4 | 0.12 | -0.355 | ❌ |
| 66 | Concerning the Ambassador. | 456 | -0.22 | 0.22 | 0.00 | 0.44 | 0.476 | 28.5 | 0.22 | 0.877 | ❌ |
| 67 | Concerning the Light-Giver. | 241 | 0.83 | 1.24 | 0.00 | 0.41 | 0.506 | 22.0 | 0.00 | -0.820 | ❌ |
| 68 | Concerning Fire. | 97 | 0.00 | 0.00 | 0.00 | 0.00 | 0.588 | 20.6 | 0.00 | 0.000 | ❌ |
| 69 | Concerning the Twelve Signs of | 916 | 0.55 | 0.55 | 0.00 | 0.00 | 0.352 | 20.4 | 0.11 | 0.000 | ❌ |
| 70 | Concerning the Body: It was 25 | 1789 | 1.62 | 1.73 | 0.00 | 0.11 | 0.288 | 19.4 | 0.39 | 3.468 | ✅ |
| 71 | Concerning the Gathering in | 132 | 3.03 | 3.79 | 0.00 | 0.76 | 0.455 | 28.2 | 0.00 | -4.545 | ✅ |
| 72 | Concerning the worn / and torn | 684 | 0.44 | 0.73 | 0.00 | 0.29 | 0.418 | 16.1 | 1.02 | 0.292 | ✅ |
| 73 | Concerning the Envy of Matter | 520 | 0.58 | 0.96 | 0.00 | 0.38 | 0.479 | 14.8 | 1.92 | 0.385 | ❌ |
| 74 | Concerning the living Fire: | 219 | 2.74 | 2.74 | 0.00 | 0.00 | 0.484 | 14.1 | 2.28 | 2.769 | ✅ |
| 75 | Concerning the Letter (?)] / | 385 | 1.08 | 2.86 | 0.00 | 0.78 | 0.423 | 15.9 | 2.08 | 5.211 | ✅ |
| 76 | [Conce]rning Lord Manichaios:  | 1163 | -1.09 | 0.00 | 0.00 | 0.09 | 0.325 | 13.0 | 1.29 | 0.000 | ❌ |
| 77 | The Chapter of the Four Klingd | 328 | 0.72 | 1.52 | 0.00 | 0.30 | 0.430 | 22.5 | 1.22 | -1.829 | ❌ |
| 78 | Concerning the Four Things ove | 222 | -0.45 | 0.00 | 0.00 | 0.45 | 0.590 | 19.2 | 2.70 | 0.000 | ❌ |
| 79 | Concerning the Fasting of the  | 908 | 1.76 | 2.75 | 0.44 | 0.55 | 0.387 | 21.2 | 0.99 | 1.101 | ❌ |
| 81 | The Chapter of Fasting, for 25 | 934 | 0.32 | 0.75 | 0.21 | 0.21 | 0.385 | 17.3 | 3.10 | 0.428 | ❌ |
| 82 | The Chapter of / Righteous [Ju | 1303 | -1.39 | 0.77 | 0.00 | 0.15 | 0.400 | 15.5 | 1.61 | 1.076 | ❌ |
| 84 | Concerning Wisdom; it is far s | 5231 | -0.29 | 0.96 | 0.04 | 0.21 | 0.218 | 21.1 | 1.11 | -0.191 | ❌ |
| 88 | Concerning the Catechumen who  | 807 | 0.25 | 0.37 | 0.12 | 0.00 | 0.394 | 17.8 | 1.36 | 0.744 | ❌ |
| 89 | The Chapter of the Nazo2 rean  | 2275 | -0.34 | 0.97 | 0.22 | 0.09 | 0.283 | 20.3 | 0.40 | 0.001 | ❌ |
| 91 | Also concerning the Catechumen | 1952 | 0.49 | 1.84 | 0.10 | 0.26 | 0.299 | 20.1 | 1.64 | -0.820 | ❌ |
| 93 | A Catechumen asked the Apo/stl | 681 | 2.06 | 2.06 | 0.00 | 0.00 | 0.383 | 15.9 | 5.58 | -0.581 | ❌ |
| 94 | Concerning the Purification of | 1613 | 0.12 | 0.43 | 0.00 | 0.31 | 0.318 | 17.0 | 2.29 | 0.744 | ❌ |
| 96 | The Three Earths that ex/ist,  | 352 | 0.85 | 1.14 | 0.00 | 0.28 | 0.489 | 12.6 | 0.85 | 1.136 | ❌ |
| 97 | Concerning the Three Creations | 1254 | 0.88 | 1.12 | 0.00 | 0.24 | 0.341 | 15.8 | 1.44 | -0.319 | ❌ |
| 100 | Concerning the Dragon with Fou | 222 | 0.45 | 0.45 | 0.00 | 0.00 | 0.586 | 19.3 | 0.00 | 0.901 | ❌ |
| 101 | [Concer]ning why, if the Perso | 488 | 0.61 | 1.02 | 0.20 | 0.20 | 0.428 | 22.3 | 0.61 | 1.639 | ❌ |
| 102 | Concerning the Light Mind, why | 366 | 1.64 | 1.91 | 0.27 | 0.00 | 0.481 | 25.6 | 1.09 | -2.186 | ❌ |
| 103 | Concerning the Five Wonders 10 | 433 | 0.23 | 0.69 | 0.00 | 0.46 | 0.487 | 20.7 | 1.15 | 1.852 | ❌ |
| 105 | Concerning the Three Things th | 215 | -1.40 | 0.00 | 0.93 | 0.47 | 0.595 | 25.3 | 0.47 | -2.795 | ❌ |
| 106 | 25 There is no Joy that shall  | 299 | 1.34 | 1.67 | 0.00 | 0.33 | 0.515 | 22.4 | 0.67 | 1.347 | ❌ |
| 107 | Concerning the Form of the Wor | 152 | 0.00 | 0.00 | 0.00 | 0.00 | 0.559 | 18.7 | 0.00 | 0.000 | ❌ |
| 108 | Concerning the Seed Grain that | 194 | 1.03 | 1.55 | 0.00 | 0.52 | 0.567 | 20.5 | 1.55 | 1.031 | ❌ |
| 109 | Concerning the Fifty Lord's Da | 446 | 1.19 | 2.69 | 0.00 | 0.00 | 0.430 | 14.1 | 1.35 | 1.794 | ✅ |
| 110 | Concerning the Nourishment of  | 153 | 0.00 | 0.00 | 0.00 | 0.00 | 0.608 | 13.4 | 1.96 | 0.000 | ❌ |
| 111 | Concerning the Four Archetypes | 139 | 0.72 | 0.72 | 0.00 | 0.00 | 0.626 | 8.8 | 0.72 | -1.429 | ❌ |
| 112 | The Human is less than all the | 768 | 0.13 | 0.39 | 0.13 | 0.13 | 0.432 | 16.5 | 1.04 | -0.781 | ❌ |
| 113 | The Chapter on whether any [Li | 278 | 3.60 | 3.60 | 0.00 | 0.00 | 0.540 | 17.6 | 1.80 | 2.878 | ❌ |
| 114 | Concerning the Three Images th | 412 | 0.49 | 0.73 | 0.00 | 0.24 | 0.427 | 16.5 | 1.21 | 0.000 | ✅ |
| 115 | The Catechumen asks / the Apos | 2455 | 1.91 | 2.08 | 0.04 | 0.12 | 0.263 | 13.5 | 2.16 | 1.061 | ✅ |
| 116 | Concerning why if a [Nail] is  | 258 | 0.00 | 0.00 | 0.00 | 0.00 | 0.496 | 12.1 | 3.49 | 0.000 | ❌ |
| 117 | Concerning why Some shall dela | 31 | 3.23 | 3.23 | 0.00 | 0.00 | 0.903 | 7.0 | 6.45 | 0.000 | ❌ |
| 118 | The mostly destroyed leaves 28 | 36 | 0.00 | 0.00 | 0.00 | 0.00 | 0.722 | 19.5 | 2.78 | 0.000 | ❌ |
| 119 | (284,? - 286,23 ) [ ... ] | 381 | 1.05 | 1.31 | 0.00 | 0.26 | 0.451 | 13.4 | 3.15 | 1.582 | ❌ |
| 120 | Concerning the Two Essences | 438 | 0.00 | 0.00 | 0.00 | 0.00 | 0.479 | 16.6 | 3.20 | 0.000 | ❌ |
| 121 | Concerning the Sect of the Bas | 358 | 0.28 | 0.84 | 0.28 | 0.28 | 0.483 | 11.2 | 4.19 | -2.235 | ❌ |
| 122 | Concerning the 'Assent' and th | 3545 | -5.76 | 3.13 | 0.20 | 0.20 | 0.413 | 6.8 | 0.65 | 1.864 | ✅ |
