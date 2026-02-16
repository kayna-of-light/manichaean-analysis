# Kephalaia Core Recovery Analysis

**Method**: Data-driven layer detection using TF-IDF clustering,
vocabulary profiling, structural analysis, and editor fatigue detection.

**Date**: 2026-02-16
**Chapters parsed**: 123 (range 0-122)
**Chapters with sufficient text for clustering**: 122
**Min words threshold**: 50

---

## 1. Cluster Discovery (Unsupervised)

### Silhouette Analysis

| k | Silhouette Score |
|---|-----------------|
| 2 | 0.0132 **← optimal** |
| 3 | 0.0089 |
| 4 | 0.0129 |
| 5 | 0.0060 |
| 6 | 0.0095 |
| 7 | 0.0103 |

**Optimal k = 2** (highest average silhouette coefficient)

### Cluster Profiles

#### Cluster 0: NT-Influenced (41 chapters)

**Avg word count**: 971

**Vocabulary category densities** (per 100 words):

- cosmological: 0.254 ██
- persian_substrate: 0.049 
- nt_christian: 0.123 █
- hagiographic: 0.145 █
- pastoral: 1.908 ███████████████████

**Most distinctive terms**:

- `i` (0.0966)
- `a` (0.0578)
- `catechumen` (0.0406)
- `elect` (0.0341)
- `person` (0.0335)
- `church` (0.0304)
- `alms` (0.0296)
- `love` (0.0284)
- `people` (0.0271)
- `faith` (0.0259)
- `catechumens` (0.0251)
- `god` (0.0247)
- `deeds` (0.0237)
- `rest` (0.0214)
- `heart` (0.0202)

**Chapters**: 0, 1, 40, 57, 58, 59, 61, 63, 67, 73, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 96, 99, 100, 102, 104, 105, 108, 112, 115, 116, 117, 119, 120

#### Cluster 1: Core Cosmological (81 chapters)

**Avg word count**: 837

**Vocabulary category densities** (per 100 words):

- cosmological: 1.123 ███████████
- persian_substrate: 0.041 
- nt_christian: 0.047 
- hagiographic: 0.250 ██
- pastoral: 0.535 █████

**Most distinctive terms**:

- `five` (0.0457)
- `light` (0.0369)
- `father` (0.0311)
- `man` (0.0298)
- `fire` (0.0294)
- `image` (0.0290)
- `living` (0.0288)
- `living spirit` (0.0237)
- `powers` (0.0223)
- `above` (0.0222)
- `universe` (0.0219)
- `spirit` (0.0215)
- `below` (0.0215)
- `greatness` (0.0209)
- `rulers` (0.0201)

**Chapters**: 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 60, 62, 64, 65, 66, 68, 69, 70, 71, 72, 74, 75, 94, 95, 97, 98, 101, 103, 106, 107, 109, 110, 111, 113, 114, 121, 122

---

## 2. Originality Ranking

Chapters ranked by composite originality score. Higher = more likely part of the original cosmological core.

| Rank | Ch. | Title | Score | Cosmo | NT | Cluster | Manual L1 |
|------|-----|-------|-------|-------|----|---------|:---------:|
| 1 | 25 | Concerning the Advent of Five Fathers / from the F | 6.67 | 5.00 | -0.00 | Core Cosmological |  |
| 2 | 53 | Concerning the First Man | 6.62 | 3.75 | -0.00 | Core Cosmological |  |
| 3 | 15 | Concerning the | 6.34 | 3.53 | -0.00 | Core Cosmological |  |
| 4 | 29 | Concerning the Eighteen great / Thrones of all the | 5.99 | 3.96 | -0.00 | Core Cosmological |  |
| 5 | 106 | 25 There is no Joy that shall remain / in the Worl | 5.85 | 2.85 | -0.00 | Core Cosmological |  |
| 6 | 17 | The Chapter of the / Thrlee] Seasons | 5.70 | 3.60 | -0.00 | Core Cosmological |  |
| 7 | 62 | Concerning the Three Rocks | 5.30 | 2.87 | -0.00 | Core Cosmological | ✅ |
| 8 | 113 | The Chapter on whether any [Lig] /ht comes from th | 5.11 | 4.37 | -0.00 | Core Cosmological |  |
| 9 | 5 | Concerning Four Hunters of / Light and Four of Dar | 4.94 | 2.31 | -0.00 | Core Cosmological |  |
| 10 | 26 | Concerning the First Man and the Ambassa/dor and t | 4.76 | 1.76 | -0.00 | Core Cosmological |  |
| 11 | 39 | Concerning the Three Da15 ys and the Two Deaths | 4.55 | 2.42 | -0.62 | Core Cosmological | ✅ |
| 12 | 36 | Concerning the Wheel that exists / iIn front of th | 4.44 | 2.59 | -0.00 | Core Cosmological |  |
| 13 | 69 | Concerning the Twelve Signs of the Zodi/ac and the | 4.27 | 2.42 | -0.00 | Core Cosmological |  |
| 14 | 20 | The Chapter of / the Name of the Fathers | 4.21 | 4.43 | -0.00 | Core Cosmological |  |
| 15 | 49 | Concerning the Whleel and the Conduits] | 4.14 | 4.29 | -0.00 | Core Cosmological |  |
| 16 | 75 | Concerning the Letter (?)] / | 4.06 | 2.80 | -0.00 | Core Cosmological | ✅ |
| 17 | 4 | Concerning the Four great Days / th[at have] come  | 4.06 | 1.55 | -0.00 | Core Cosmological |  |
| 18 | 48 | Concerning the Conduits | 4.04 | 2.58 | -0.00 | Core Cosmological |  |
| 19 | 101 | [Concer]ning why, if the Person shall look down /  | 4.01 | 2.45 | -0.00 | Core Cosmological |  |
| 20 | 16 | Concerning the Five] Greatnesses who / [went forth | 4.01 | 2.69 | -0.21 | Core Cosmological |  |
| 21 | 64 | [Concerning/ Adam. | 3.89 | 1.24 | -0.00 | Core Cosmological |  |
| 22 | 74 | Concerning the living Fire: / It is present in Eig | 3.78 | 1.90 | -0.00 | Core Cosmological | ✅ |
| 23 | 24 | 10 [ ... / ... ] | 3.77 | 2.20 | -0.00 | Core Cosmological |  |
| 24 | 28 | Concerning the T]welve 15 Judges [of] the Father | 3.67 | 2.69 | -0.00 | Core Cosmological |  |
| 25 | 51 | Concerning the First Man | 3.55 | 1.94 | -0.00 | Core Cosmological |  |
| 26 | 22 | 15 [ ... / ... ] the Land of Light. | 3.37 | 1.37 | -0.00 | Core Cosmological |  |
| 27 | 27 | Concerning the Five Forms that exist / in the Rule | 3.34 | 0.21 | -0.00 | Core Cosmological |  |
| 28 | 44 | Concerning the Sea / Giant | 3.31 | 1.67 | -0.00 | Core Cosmological |  |
| 29 | 37 | Concerning the Three Zones | 3.30 | 2.69 | -0.00 | Core Cosmological |  |
| 30 | 6 | Concerning the Five Storehouses that have polured  | 3.23 | 1.05 | -1.76 | Core Cosmological | ✅ |
| 31 | 23 | [ ... ] 30 which [ ... ] | 3.19 | 1.47 | -0.00 | Core Cosmological |  |
| 32 | 38 | Concerning the Light Mind and 20 the Apostles and  | 3.18 | 1.57 | -0.19 | Core Cosmological | ✅ |
| 33 | 7 | The Seventh, concerning 15 the Five Fathers. | 3.15 | 1.70 | -0.00 | Core Cosmological |  |
| 34 | 70 | Concerning the Body: It was 25 constructed after t | 3.05 | 1.92 | -0.00 | Core Cosmological | ✅ |
| 35 | 107 | Concerning the Form of the Word, that [ | 3.00 | 0.00 | -0.00 | Core Cosmological |  |
| 36 | 103 | Concerning the Five Wonders 10 that the Light Mind | 2.75 | 0.62 | -0.00 | Core Cosmological |  |
| 37 | 14 | The Interpretation [of] the S[i]lence, the Fast, [ | 2.73 | 1.10 | -0.00 | Core Cosmological |  |
| 38 | 10 | Concerning the Interpretation of the Fourteen [gre | 2.70 | 2.11 | -0.00 | Core Cosmological |  |
| 39 | 18 | Concerning the Five] War[s that the] Sons / of [Li | 2.70 | 1.34 | -0.64 | Core Cosmological |  |
| 40 | 9 | The Explanation of the Peace, what it is; 30 the R | 2.69 | 1.85 | -0.49 | Core Cosmological |  |
| 41 | 19 | Concerning the Five RefleJas[es; 15 what] they [ar | 2.67 | 1.72 | -0.00 | Core Cosmological |  |
| 42 | 47 | Concerning the Four 15 great Things | 2.66 | 0.51 | -0.00 | Core Cosmological |  |
| 43 | 60 | Concerning the Four Fathers; / what they are like | 2.66 | 1.65 | -0.00 | Core Cosmological |  |
| 44 | 31 | Concerning the Summons, / in which Limb / of the S | 2.63 | 1.08 | -0.00 | Core Cosmological |  |
| 45 | 66 | Concerning the Ambassador | 2.54 | 0.80 | -0.00 | Core Cosmological |  |
| 46 | 8 | Concerning the Fourteen Vehicles / that Jesus has  | 2.53 | 2.51 | -0.00 | Core Cosmological |  |
| 47 | 55 | Concerning the Fashion/ing of Adam | 2.42 | 0.42 | -0.00 | Core Cosmological | ✅ |
| 48 | 30 | Concerning the Three Garments | 2.41 | 0.69 | -0.00 | Core Cosmological |  |
| 49 | 41 | Concerning the Three Blows that / befell the Enemy | 2.39 | 1.48 | -0.00 | Core Cosmological | ✅ |
| 50 | 111 | Concerning the Four Archetypes that occur / in the | 2.39 | 0.66 | -0.00 | Core Cosmological |  |
| 51 | 71 | Concerning the Gathering in / of the [E]lements | 2.35 | 3.17 | -0.00 | Core Cosmological | ✅ |
| 52 | 32 | Concerning the Seven Works / of the Living Spirit | 2.28 | 2.13 | -0.00 | Core Cosmological |  |
| 53 | 21 | [C]oncerning the Father of Gr[eat]ness: 15 [ho]w h | 2.26 | 0.43 | -0.00 | Core Cosmological |  |
| 54 | 72 | Concerning the worn / and torn apart Garments, or  | 2.20 | 0.79 | -0.00 | Core Cosmological | ✅ |
| 55 | 50 | Concerning these Na[mes]: God, Rich One, / and Ang | 2.10 | 1.35 | -0.00 | Core Cosmological |  |
| 56 | 34 | Concerning the Ten Things that the Am[bassa]/d[or] | 2.03 | 1.94 | -0.00 | Core Cosmological |  |
| 57 | 68 | Concerning Fire | 2.00 | 0.00 | -0.00 | Core Cosmological |  |
| 58 | 110 | Concerning the Nourishment of the Person, / for th | 2.00 | 0.00 | -0.00 | Core Cosmological |  |
| 59 | 54 | [Concern]ing the Quality of the Garments. | 1.97 | 0.97 | -0.00 | Core Cosmological |  |
| 60 | 40 | Concerning the Three Things that / were establishe | 1.90 | 1.22 | -1.02 | NT-Influenced | ✅ |
| 61 | 95 | The Apostle asks his 15 Disciples: What is Cloud? | 1.87 | 0.38 | -0.00 | Core Cosmological |  |
| 62 | 59 | The Chapter of the Ele/ments that wept | 1.81 | 1.00 | -0.00 | NT-Influenced |  |
| 63 | 114 | Concerning the Three Images that / are in the righ | 1.79 | 0.64 | -0.00 | Core Cosmological | ✅ |
| 64 | 97 | Concerning the Three Creations of the Flesh: the o | 1.78 | 0.41 | -0.00 | Core Cosmological |  |
| 65 | 122 | Concerning the 'Assent' and the 'Amen' | 1.77 | 2.38 | -1.46 | Core Cosmological | ✅ |
| 66 | 13 | Concer[ning] the Five Saviours, the Resurrectors / | 1.74 | 0.77 | -0.00 | Core Cosmological |  |
| 67 | 94 | Concerning the Purification of these Four Elements | 1.74 | 0.39 | -0.00 | Core Cosmological |  |
| 68 | 45 | Concerning the Vessels | 1.71 | 0.00 | -0.00 | Core Cosmological |  |
| 69 | 98 | What is Virginal; or, / otherwise, what is Contine | 1.63 | 0.27 | -0.00 | Core Cosmological |  |
| 70 | 3 | The Interpretation of Happiness, / Wisdom and Powe | 1.61 | 1.48 | -0.00 | Core Cosmological | ✅ |
| 71 | 52 | 25 Conce[rning] the [ ... ] *64 of the Light. | 1.59 | 0.00 | -0.00 | Core Cosmological |  |
| 72 | 12 | Concerning the Interpretation of the Five Words th | 1.53 | 0.70 | -0.00 | Core Cosmological |  |
| 73 | 33 | Concerning the Five Things that he 20 constructed  | 1.50 | 1.50 | -0.00 | Core Cosmological |  |
| 74 | 2 | The Second, concerning / the Parable of the Tree. | 1.47 | 1.22 | -1.27 | Core Cosmological | ✅ |
| 75 | 56 | [ConcernJing Saklas and his Powers. | 1.43 | 1.54 | -0.61 | Core Cosmological | ✅ |
| 76 | 42 | Concerning the Three / Vessels | 1.42 | 0.55 | -0.53 | Core Cosmological |  |
| 77 | 43 | Concerning the Vessels | 1.41 | 1.12 | -1.07 | Core Cosmological |  |
| 78 | 121 | Concerning the Sect of the Basket | 1.34 | 0.00 | -0.00 | Core Cosmological |  |
| 79 | 109 | Concerning the Fifty Lord's Days; / to what Myster | 1.25 | 0.66 | -0.00 | Core Cosmological | ✅ |
| 80 | 100 | Concerning the Dragon with Fourte[en] He[ads]; / w | 1.08 | 0.00 | -0.00 | NT-Influenced |  |
| 81 | 65 | Concerning the Sun | 0.37 | 0.17 | -1.38 | Core Cosmological |  |
| 82 | 46 | Concerning the Ambassador | 0.34 | 1.42 | -2.37 | Core Cosmological |  |
| 83 | 58 | The Four Powers that grieve. | 0.00 | 1.16 | -0.00 | NT-Influenced |  |
| 84 | 63 | Concerning Love | -0.00 | 0.46 | -0.00 | NT-Influenced |  |
| 85 | 104 | Concerning Food: It shall be allocated to / Five P | 0.00 | 0.00 | -0.00 | NT-Influenced |  |
| 86 | 115 | The Catechumen asks / the Apostle: will Rest / com | -0.00 | 1.49 | -0.48 | NT-Influenced | ✅ |
| 87 | 118 | The mostly destroyed leaves 283-284 perhaps contai | 0.00 | 0.00 | -0.00 |  |  |
| 88 | 86 | The Chapter of the Man / who asks: Why [am] I / so | -0.04 | 0.85 | -0.36 | NT-Influenced | ✅ |
| 89 | 67 | Concerning the Light-Giver | -0.12 | 0.00 | -0.00 | NT-Influenced |  |
| 90 | 116 | Concerning why if a [Nail] is cut / the Person sha | -0.12 | 0.00 | -0.00 | NT-Influenced |  |
| 91 | 84 | Concerning Wisdom; it is far superior when on the  | -0.14 | 0.00 | -0.00 | NT-Influenced |  |
| 92 | 102 | Concerning the Light Mind, why / it does not exerc | -0.18 | 0.54 | -0.00 | NT-Influenced |  |
| 93 | 35 | Concerning the Four Works / of the Ambassador | -0.24 | 1.12 | -0.00 | Core Cosmological |  |
| 94 | 108 | Concerning the Seed Grain that shall be / formed b | -0.27 | 0.66 | -0.00 | NT-Influenced |  |
| 95 | 61 | Concerning the Garment of the Waters: / how great  | -0.30 | 0.46 | -0.51 | NT-Influenced |  |
| 96 | 93 | A Catechumen asked the Apo/stle: When I would give | -0.36 | 1.10 | -0.46 | NT-Influenced |  |
| 97 | 78 | Concerning the Four Things over which Peo/ple kill | -0.37 | 0.00 | -0.00 | NT-Influenced |  |
| 98 | 73 | Concerning the Envy of Matter | -0.39 | 0.34 | -0.00 | NT-Influenced |  |
| 99 | 82 | The Chapter of / Righteous [Judgement] | -0.49 | 0.00 | -0.00 | NT-Influenced |  |
| 100 | 96 | The Three Earths that ex/ist, they bear Fruit. | -0.51 | 0.36 | -0.00 | NT-Influenced |  |
| 101 | 83 | Concerning the Man who is ugllly / in his Body, [b | -0.52 | 0.20 | -0.00 | NT-Influenced |  |
| 102 | 11 | Concerning the Interpretation of] all [ the] Fathe | -0.74 | 2.90 | -5.00 | Core Cosmological |  |
| 103 | 76 | [Conce]rning Lord Manichaios: / how he journeyed. | -0.78 | 0.00 | -0.00 | NT-Influenced |  |
| 104 | 85 | Concerning the Cross of Light: / [ | -0.81 | 0.51 | -0.00 | NT-Influenced | ✅ |
| 105 | 119 | (284,? - 286,23 ) [ ... ] | -1.05 | 1.37 | -0.76 | NT-Influenced |  |
| 106 | 117 | (282, 7 -? ) | -1.17 | 0.00 | -0.00 | NT-Influenced |  |
| 107 | 120 | Concerning the Two Essences | -1.23 | 0.00 | -0.58 | NT-Influenced |  |
| 108 | 1 | Concerning the Ad[vent] / of the Apostle | -1.28 | 0.10 | -0.99 | NT-Influenced |  |
| 109 | 87 | Concerning the Alms, that [ | -1.42 | 1.04 | -0.00 | NT-Influenced |  |
| 110 | 57 | Concerning the Generation of Adam | -1.57 | 0.50 | -0.00 | NT-Influenced |  |
| 111 | 88 | Concerning the Catechumen who found / fault with t | -1.61 | 0.00 | -0.54 | NT-Influenced |  |
| 112 | 112 | The Human is less than all the Things 5 of the Uni | -1.87 | 0.13 | -1.30 | NT-Influenced |  |
| 113 | 99 | Concerning Transmigration | -2.00 | 0.00 | -0.00 | NT-Influenced |  |
| 114 | 89 | The Chapter of the Nazo2 rean who questions the Te | -2.04 | 0.00 | -0.68 | NT-Influenced |  |
| 115 | 91 | Also concerning the Catechumen; / shall he be save | -2.07 | 0.34 | -0.45 | NT-Influenced |  |
| 116 | 92 | 25 The Apostle is asked: Why when / you drew every | -2.18 | 0.77 | -0.86 | NT-Influenced |  |
| 117 | 90 | Concerning the Fifteen Paths; and whether the Ca/t | -2.23 | 0.28 | -1.86 | NT-Influenced |  |
| 118 | 79 | Concerning the Fasting of the Saints | -2.96 | 0.58 | -0.00 | NT-Influenced |  |
| 119 | 81 | The Chapter of Fasting, for 25 it engenders a Host | -3.09 | 0.00 | -1.54 | NT-Influenced |  |
| 120 | 105 | Concerning the Three Things that are great with /  | -3.76 | 0.00 | -4.20 | NT-Influenced |  |
| 121 | 77 | The Chapter of the Four Klingdoms] | -4.39 | 0.00 | -4.08 | NT-Influenced |  |
| 122 | 80 | The Chapter of the Command 5 ments of Righteousnes | -7.21 | 0.00 | -4.49 | NT-Influenced |  |

---

## 3. Proposed Original Core

Chapters with originality score > 1.0 and assigned to the Core Cosmological cluster:

**Total core candidates**: 80
**Also in manual Layer 1**: 18 — 2, 3, 6, 38, 39, 40, 41, 55, 56, 62, 70, 71, 72, 74, 75, 109, 114, 122
**NEW (not in manual Layer 1)**: 62 — 4, 5, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 36, 37, 42, 43, 44, 45, 47, 48, 49, 50, 51, 52, 53, 54, 59, 60, 64, 66, 68, 69, 94, 95, 97, 98, 100, 101, 103, 106, 107, 110, 111, 113, 121

**In manual Layer 1 but NOT in computed core**: 3 — 85, 86, 115

---

## 4. Editor Fatigue Detection

Chapters where cosmological vocabulary is concentrated in the first half, suggesting an original core was diluted by later additions:

| Ch. | Title | Shift | 1st Cosmo | 2nd Cosmo | 1st NT | 2nd NT |
|-----|-------|-------|-----------|-----------|--------|--------|
| 25 | Concerning the Advent of Five Fathers / from  | 4.44 | 6.67 | 2.22 | 0.00 | 0.00 |
| 75 | Concerning the Letter (?)] / | 3.73 | 3.73 | 0.00 | 0.00 | 0.00 |
| 8 | Concerning the Fourteen Vehicles / that Jesus | 3.35 | 3.35 | 0.00 | 0.00 | 0.00 |
| 41 | Concerning the Three Blows that / befell the  | 1.97 | 1.97 | 0.00 | 0.00 | 0.00 |
| 38 | Concerning the Light Mind and 20 the Apostles | 1.69 | 1.84 | 0.26 | 0.00 | 0.07 |
| 77 | The Chapter of the Four Klingdoms] | 1.63 | 0.00 | 0.00 | 0.00 | 1.63 |
| 70 | Concerning the Body: It was 25 constructed af | 1.54 | 1.95 | 0.61 | 0.00 | 0.00 |
| 57 | Concerning the Generation of Adam | 1.50 | 0.67 | 0.00 | 0.00 | 0.00 |
| 9 | The Explanation of the Peace, what it is; 30  | 1.48 | 1.88 | 0.59 | 0.00 | 0.20 |
| 32 | Concerning the Seven Works / of the Living Sp | 1.43 | 2.86 | 0.00 | 0.00 | 0.00 |
| 122 | Concerning the 'Assent' and the 'Amen' | 1.42 | 1.88 | 1.29 | 0.18 | 0.40 |
| 92 | 25 The Apostle is asked: Why when / you drew  | 1.37 | 1.03 | 0.00 | 0.34 | 0.00 |
| 28 | Concerning the T]welve 15 Judges [of] the Fat | 1.34 | 2.47 | 1.12 | 0.00 | 0.00 |
| 51 | Concerning the First Man | 1.30 | 1.95 | 0.65 | 0.00 | 0.00 |
| 16 | Concerning the Five] Greatnesses who / [went  | 1.28 | 2.48 | 1.11 | 0.09 | 0.00 |
| 119 | (284,? - 286,23 ) [ ... ] | 1.22 | 1.52 | 0.30 | 0.30 | 0.00 |
| 53 | Concerning the First Man | 1.12 | 3.33 | 1.66 | 0.00 | 0.00 |
| 1 | Concerning the Ad[vent] / of the Apostle | 1.06 | 0.00 | 0.13 | 0.20 | 0.20 |
| 23 | [ ... ] 30 which [ ... ] | 1.05 | 1.51 | 0.45 | 0.00 | 0.00 |
| 113 | The Chapter on whether any [Lig] /ht comes fr | 0.97 | 3.88 | 1.94 | 0.00 | 0.00 |
| 115 | The Catechumen asks / the Apostle: will Rest  | 0.96 | 1.54 | 0.45 | 0.13 | 0.06 |
| 60 | Concerning the Four Fathers; / what they are  | 0.94 | 1.57 | 0.63 | 0.00 | 0.00 |
| 29 | Concerning the Eighteen great / Thrones of al | 0.93 | 3.11 | 2.17 | 0.00 | 0.00 |
| 30 | Concerning the Three Garments | 0.93 | 0.93 | 0.00 | 0.00 | 0.00 |
| 48 | Concerning the Conduits | 0.92 | 2.06 | 1.38 | 0.00 | 0.00 |

---

## 5. Gardner Editorial Flags

| Ch. | Title | Flags |
|-----|-------|-------|
| 1 | Concerning the Ad[vent] / of the Apostle | uncertain, textual_development, christian_connection, gnostic_connection, mani_attribution, buddhist_connection, zoroastrian_connection |
| 4 | Concerning the Four great Days / th[at have] come  | textual_development, christian_connection, gnostic_connection |
| 5 | Concerning Four Hunters of / Light and Four of Dar | parallel_text |
| 6 | Concerning the Five Storehouses that have polured  | redaction, corruption, uncertain, textual_development, parallel_text, christian_connection, gnostic_connection, mani_attribution |
| 10 | Concerning the Interpretation of the Fourteen [gre | gnostic_connection |
| 12 | Concerning the Interpretation of the Five Words th | uncertain, gnostic_connection |
| 20 | The Chapter of / the Name of the Fathers | parallel_text |
| 24 | 10 [ ... / ... ] | uncertain, parallel_text |
| 26 | Concerning the First Man and the Ambassa/dor and t | uncertain, buddhist_connection |
| 27 | Concerning the Five Forms that exist / in the Rule | parallel_text |
| 39 | Concerning the Three Da15 ys and the Two Deaths | parallel_text |
| 41 | Concerning the Three Blows that / befell the Enemy | redaction |
| 48 | Concerning the Conduits | uncertain, textual_development |
| 58 | The Four Powers that grieve. | christian_connection, gnostic_connection |
| 65 | Concerning the Sun | redaction, uncertain, parallel_text |
| 69 | Concerning the Twelve Signs of the Zodi/ac and the | gnostic_connection |
| 70 | Concerning the Body: It was 25 constructed after t | redaction |
| 83 | Concerning the Man who is ugllly / in his Body, [b | christian_connection |
| 89 | The Chapter of the Nazo2 rean who questions the Te | christian_connection |
| 90 | Concerning the Fifteen Paths; and whether the Ca/t | redaction, parallel_text, buddhist_connection |
| 92 | 25 The Apostle is asked: Why when / you drew every | buddhist_connection |
| 94 | Concerning the Purification of these Four Elements | corruption, uncertain, buddhist_connection |
| 98 | What is Virginal; or, / otherwise, what is Contine | buddhist_connection |
| 99 | Concerning Transmigration | buddhist_connection |
| 109 | Concerning the Fifty Lord's Days; / to what Myster | christian_connection |
| 121 | Concerning the Sect of the Basket | uncertain |
| 122 | Concerning the 'Assent' and the 'Amen' | christian_connection |

---

## 6. NT Citation Distribution

| Ch. | Title | Citations | Count |
|-----|-------|-----------|-------|
| 1 | Concerning the Ad[vent] / of the Apostle | Phil. 2, Jn. 16, Phil. 2:7, Jn. 16:7 | 4 |
| 2 | The Second, concerning / the Parable of the Tree. | Lk. 6, Lk. 22, Cor. 15, Lk. 6:43, Lk. 22:3,  Cor. 15:9 | 6 |
| 9 | The Explanation of the Peace, what it is; 30 the R | Mk. 12, Mk. 12:36 | 2 |
| 18 | Concerning the Five] War[s that the] Sons / of [Li | Mt. 3, Mt. 3:10 | 2 |
| 19 | Concerning the Five RefleJas[es; 15 what] they [ar | Phil. 2, Phil. 2:7 | 2 |
| 63 | Concerning Love | Jn. 15, Jn. 15:13 | 2 |
| 65 | Concerning the Sun | Gospel of Thomas | 1 |
| 75 | Concerning the Letter (?)] / | Mt. 21, Mt. 21:22, Jn 15:7 | 3 |
| 76 | [Conce]rning Lord Manichaios: / how he journeyed. | Jn. 3, Jn. 3:19 | 2 |
| 77 | The Chapter of the Four Klingdoms] | Mt. 10, Mt. 10:42 | 2 |
| 82 | The Chapter of / Righteous [Judgement] | Mt. 6, Mt. 6:21 | 2 |
| 83 | Concerning the Man who is ugllly / in his Body, [b | Mt. 18, Mt. 18:10 | 2 |
| 85 | Concerning the Cross of Light: / [ | Mt. 6, Mt. 6:21 | 2 |
| 89 | The Chapter of the Nazo2 rean who questions the Te | Mt. 6, Mt. 6:21 | 2 |
| 91 | Also concerning the Catechumen; / shall he be save | Mt. 6, Cor. 7, Mt. 6:21, 1 Cor. 7:29 | 4 |
| 109 | Concerning the Fifty Lord's Days; / to what Myster | Mt. 4, Mt. 26, Lk. 24, Mt. 4:2, Mt. 26:6, Lk. 24:46 | 6 |
| 122 | Concerning the 'Assent' and the 'Amen' | Mt. 3:10, Mt. 6:21, Mt.10:42, Mt. 18:10, Mt. 21:22, Mk.12:36, Lk. 6:43, Lk. 22:3, Jn. 3:19, Jn. 8:38, Jn. 15:7, Jn. 15:13, Jn. 16:7, Jn. 16:24,  Cor. 7:29,  Cor. 15:9, Phil. 2:7 | 17 |

---

## 7. Fragmentary Chapters (excluded from clustering)

Chapters with fewer than 50 words:

- **Ch. 118** (43 words): The mostly destroyed leaves 283-284 perhaps contained the end of chapter 117, certainly the whole of

---

## Appendix: Full Chapter Data

| Ch. | Words | Originality | Cosmo | NT | Hagio | Pastoral | Persian | Cluster | Fatigue | L1? |
|-----|------:|------------:|------:|---:|------:|---------:|--------:|---------|--------:|:---:|
| 1 | 3029 | -1.28 | 0.07 | 0.20 | 0.66 | 1.09 | 0.26 | NT-Influence | 1.06 |  |
| 2 | 1973 | 1.47 | 0.81 | 0.25 | 0.15 | 0.35 | 0.00 | Core Cosmolo | -1.42 | ✅ |
| 3 | 508 | 1.61 | 0.98 | 0.00 | 0.59 | 1.38 | 0.00 | Core Cosmolo | -2.36 | ✅ |
| 4 | 870 | 4.06 | 1.03 | 0.00 | 0.23 | 0.34 | 0.11 | Core Cosmolo | 0.69 |  |
| 5 | 846 | 4.94 | 1.54 | 0.00 | 0.00 | 0.59 | 0.00 | Core Cosmolo | 0.24 |  |
| 6 | 1422 | 3.23 | 0.70 | 0.35 | 0.14 | 0.70 | 0.56 | Core Cosmolo | 0.42 | ✅ |
| 7 | 883 | 3.15 | 1.13 | 0.00 | 0.45 | 1.02 | 0.00 | Core Cosmolo | 0.46 |  |
| 8 | 358 | 2.53 | 1.68 | 0.00 | 0.00 | 1.96 | 0.00 | Core Cosmolo | 3.35 |  |
| 9 | 2023 | 2.69 | 1.24 | 0.10 | 0.00 | 0.44 | 0.00 | Core Cosmolo | 1.48 |  |
| 10 | 356 | 2.70 | 1.40 | 0.00 | 0.56 | 0.56 | 0.00 | Core Cosmolo | -0.56 |  |
| 11 | 310 | -0.74 | 1.94 | 1.29 | 0.00 | 1.29 | 0.00 | Core Cosmolo | -2.58 |  |
| 12 | 213 | 1.53 | 0.47 | 0.00 | 0.47 | 0.47 | 0.00 | Core Cosmolo | 0.00 |  |
| 13 | 194 | 1.74 | 0.52 | 0.00 | 0.52 | 0.00 | 0.00 | Core Cosmolo | 0.00 |  |
| 14 | 273 | 2.73 | 0.73 | 0.00 | 0.00 | 0.73 | 0.00 | Core Cosmolo | -1.46 |  |
| 15 | 553 | 6.34 | 2.35 | 0.00 | 0.00 | 0.54 | 0.36 | Core Cosmolo | -1.80 |  |
| 16 | 2338 | 4.01 | 1.80 | 0.04 | 0.00 | 0.68 | 0.09 | Core Cosmolo | 1.28 |  |
| 17 | 875 | 5.70 | 2.40 | 0.00 | 0.00 | 0.34 | 0.11 | Core Cosmolo | 0.23 |  |
| 18 | 785 | 2.70 | 0.89 | 0.13 | 0.25 | 0.51 | 0.25 | Core Cosmolo | 0.00 |  |
| 19 | 787 | 2.67 | 1.14 | 0.00 | 0.13 | 1.27 | 0.00 | Core Cosmolo | 0.51 |  |
| 20 | 271 | 4.21 | 2.95 | 0.00 | 1.11 | 0.00 | 0.00 | Core Cosmolo | -8.11 |  |
| 21 | 350 | 2.26 | 0.29 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 0.57 |  |
| 22 | 328 | 3.37 | 0.91 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | -0.61 |  |
| 23 | 1328 | 3.19 | 0.98 | 0.00 | 0.00 | 0.38 | 0.08 | Core Cosmolo | 1.05 |  |
| 24 | 2246 | 3.77 | 1.47 | 0.00 | 0.00 | 0.49 | 0.00 | Core Cosmolo | 0.62 |  |
| 25 | 90 | 6.67 | 4.44 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 4.44 |  |
| 26 | 341 | 4.76 | 1.17 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 0.01 |  |
| 27 | 701 | 3.34 | 0.14 | 0.00 | 0.00 | 0.14 | 0.43 | Core Cosmolo | 0.29 |  |
| 28 | 892 | 3.67 | 1.79 | 0.00 | 0.00 | 1.23 | 0.00 | Core Cosmolo | 1.34 |  |
| 29 | 644 | 5.99 | 2.64 | 0.00 | 0.00 | 0.31 | 0.16 | Core Cosmolo | 0.93 |  |
| 30 | 217 | 2.41 | 0.46 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 0.93 |  |
| 31 | 556 | 2.63 | 0.72 | 0.00 | 0.36 | 0.54 | 0.18 | Core Cosmolo | -0.00 |  |
| 32 | 281 | 2.28 | 1.42 | 0.00 | 0.71 | 0.00 | 0.00 | Core Cosmolo | 1.43 |  |
| 33 | 100 | 1.50 | 1.00 | 0.00 | 2.00 | 0.00 | 0.00 | Core Cosmolo | -2.00 |  |
| 34 | 155 | 2.03 | 1.29 | 0.00 | 1.29 | 0.65 | 0.00 | Core Cosmolo | 0.00 |  |
| 35 | 134 | -0.24 | 0.75 | 0.00 | 1.49 | 0.75 | 0.00 | Core Cosmolo | -4.48 |  |
| 36 | 405 | 4.44 | 1.73 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 0.50 |  |
| 37 | 167 | 3.30 | 1.80 | 0.00 | 1.20 | 0.00 | 0.00 | Core Cosmolo | -3.59 |  |
| 38 | 5333 | 3.18 | 1.05 | 0.04 | 0.02 | 1.44 | 0.02 | Core Cosmolo | 1.69 | ✅ |
| 39 | 805 | 4.55 | 1.61 | 0.12 | 0.25 | 0.25 | 0.12 | Core Cosmolo | 0.00 | ✅ |
| 40 | 490 | 1.90 | 0.82 | 0.20 | 0.00 | 0.82 | 0.41 | NT-Influence | 0.41 | ✅ |
| 41 | 406 | 2.39 | 0.99 | 0.00 | 0.00 | 0.99 | 0.00 | Core Cosmolo | 1.97 | ✅ |
| 42 | 1899 | 1.42 | 0.37 | 0.11 | 0.26 | 0.47 | 0.05 | Core Cosmolo | -0.42 |  |
| 43 | 938 | 1.41 | 0.75 | 0.21 | 0.32 | 0.00 | 0.00 | Core Cosmolo | -1.71 |  |
| 44 | 901 | 3.31 | 1.11 | 0.00 | 0.00 | 0.44 | 0.00 | Core Cosmolo | 0.45 |  |
| 45 | 348 | 1.71 | 0.00 | 0.00 | 0.00 | 0.57 | 0.00 | Core Cosmolo | 0.00 |  |
| 46 | 422 | 0.34 | 0.95 | 0.47 | 0.00 | 1.42 | 0.00 | Core Cosmolo | 0.00 |  |
| 47 | 883 | 2.66 | 0.34 | 0.00 | 0.23 | 0.79 | 0.00 | Core Cosmolo | -0.68 |  |
| 48 | 1745 | 4.04 | 1.72 | 0.00 | 0.57 | 0.23 | 0.00 | Core Cosmolo | 0.92 |  |
| 49 | 280 | 4.14 | 2.86 | 0.00 | 1.07 | 0.00 | 0.00 | Core Cosmolo | -2.14 |  |
| 50 | 444 | 2.10 | 0.90 | 0.00 | 1.13 | 0.00 | 0.00 | Core Cosmolo | -0.45 |  |
| 51 | 309 | 3.55 | 1.29 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 1.30 |  |
| 52 | 605 | 1.59 | 0.00 | 0.00 | 0.00 | 0.83 | 0.00 | Core Cosmolo | 0.00 |  |
| 53 | 721 | 6.62 | 2.50 | 0.00 | 0.28 | 0.14 | 0.28 | Core Cosmolo | 1.12 |  |
| 54 | 616 | 1.97 | 0.65 | 0.00 | 0.32 | 0.32 | 0.00 | Core Cosmolo | 0.65 |  |
| 55 | 1420 | 2.42 | 0.28 | 0.00 | 0.00 | 0.42 | 0.07 | Core Cosmolo | 0.00 | ✅ |
| 56 | 2438 | 1.43 | 1.03 | 0.12 | 0.41 | 1.11 | 0.04 | Core Cosmolo | 0.82 | ✅ |
| 57 | 1203 | -1.57 | 0.33 | 0.00 | 0.58 | 0.91 | 0.00 | NT-Influence | 1.50 |  |
| 58 | 388 | 0.00 | 0.77 | 0.00 | 0.52 | 0.26 | 0.00 | NT-Influence | -0.52 |  |
| 59 | 897 | 1.81 | 0.67 | 0.00 | 0.00 | 0.11 | 0.00 | NT-Influence | 0.45 |  |
| 60 | 638 | 2.66 | 1.10 | 0.00 | 0.31 | 0.16 | 0.00 | Core Cosmolo | 0.94 |  |
| 61 | 987 | -0.30 | 0.30 | 0.10 | 0.20 | 0.30 | 0.10 | NT-Influence | -0.41 |  |
| 62 | 261 | 5.30 | 1.92 | 0.00 | 0.00 | 1.15 | 0.00 | Core Cosmolo | -0.75 | ✅ |
| 63 | 327 | -0.00 | 0.31 | 0.00 | 0.00 | 0.92 | 0.00 | NT-Influence | -0.61 |  |
| 64 | 604 | 3.89 | 0.83 | 0.00 | 0.00 | 0.50 | 0.00 | Core Cosmolo | 0.33 |  |
| 65 | 1811 | 0.37 | 0.11 | 0.28 | 0.00 | 0.83 | 0.00 | Core Cosmolo | -0.33 |  |
| 66 | 561 | 2.54 | 0.53 | 0.00 | 0.00 | 0.53 | 0.00 | Core Cosmolo | -0.35 |  |
| 67 | 268 | -0.12 | 0.00 | 0.00 | 0.00 | 2.24 | 0.00 | NT-Influence | 0.00 |  |
| 68 | 126 | 2.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 0.00 |  |
| 69 | 990 | 4.27 | 1.62 | 0.00 | 0.10 | 0.51 | 0.10 | Core Cosmolo | -1.01 |  |
| 70 | 1952 | 3.05 | 1.28 | 0.00 | 0.10 | 0.41 | 0.00 | Core Cosmolo | 1.54 | ✅ |
| 71 | 142 | 2.35 | 2.11 | 0.00 | 1.41 | 0.00 | 0.00 | Core Cosmolo | -7.04 | ✅ |
| 72 | 762 | 2.20 | 0.52 | 0.00 | 0.13 | 0.66 | 0.00 | Core Cosmolo | -0.26 | ✅ |
| 73 | 438 | -0.39 | 0.23 | 0.00 | 0.00 | 3.20 | 0.00 | NT-Influence | 0.46 |  |
| 74 | 394 | 3.78 | 1.27 | 0.00 | 0.00 | 0.25 | 0.00 | Core Cosmolo | -0.51 | ✅ |
| 75 | 482 | 4.06 | 1.87 | 0.00 | 0.00 | 1.24 | 0.00 | Core Cosmolo | 3.73 | ✅ |
| 76 | 2040 | -0.78 | 0.00 | 0.00 | 0.34 | 0.78 | 0.10 | NT-Influence | -0.49 |  |
| 77 | 490 | -4.39 | 0.00 | 0.82 | 0.00 | 2.86 | 0.20 | NT-Influence | 1.63 |  |
| 78 | 272 | -0.37 | 0.00 | 0.00 | 0.00 | 0.74 | 0.00 | NT-Influence | 0.00 |  |
| 79 | 260 | -2.96 | 0.38 | 0.00 | 0.77 | 5.38 | 0.00 | NT-Influence | -2.31 |  |
| 80 | 557 | -7.21 | 0.00 | 0.90 | 0.36 | 6.28 | 0.00 | NT-Influence | -0.36 |  |
| 81 | 1295 | -3.09 | 0.00 | 0.31 | 0.00 | 3.09 | 0.00 | NT-Influence | -0.62 |  |
| 82 | 1419 | -0.49 | 0.00 | 0.00 | 0.00 | 0.99 | 0.00 | NT-Influence | 0.00 |  |
| 83 | 1526 | -0.52 | 0.13 | 0.00 | 0.20 | 1.05 | 0.07 | NT-Influence | -0.66 |  |
| 84 | 1397 | -0.14 | 0.00 | 0.00 | 0.00 | 0.29 | 0.00 | NT-Influence | 0.00 |  |
| 85 | 2337 | -0.81 | 0.34 | 0.00 | 0.00 | 2.44 | 0.00 | NT-Influence | 0.34 | ✅ |
| 86 | 1406 | -0.04 | 0.57 | 0.07 | 0.07 | 0.78 | 0.00 | NT-Influence | -0.00 | ✅ |
| 87 | 868 | -1.42 | 0.69 | 0.00 | 0.23 | 6.22 | 0.00 | NT-Influence | -0.46 |  |
| 88 | 932 | -1.61 | 0.00 | 0.11 | 0.11 | 1.72 | 0.00 | NT-Influence | 0.00 |  |
| 89 | 740 | -2.04 | 0.00 | 0.14 | 0.00 | 2.57 | 0.00 | NT-Influence | 0.27 |  |
| 90 | 1612 | -2.23 | 0.19 | 0.37 | 0.00 | 2.05 | 0.12 | NT-Influence | -0.37 |  |
| 91 | 2226 | -2.07 | 0.22 | 0.09 | 0.04 | 4.81 | 0.04 | NT-Influence | 0.00 |  |
| 92 | 584 | -2.18 | 0.51 | 0.17 | 0.34 | 6.51 | 0.00 | NT-Influence | 1.37 |  |
| 93 | 1091 | -0.36 | 0.73 | 0.09 | 0.00 | 4.67 | 0.00 | NT-Influence | -0.55 |  |
| 94 | 382 | 1.74 | 0.26 | 0.00 | 0.00 | 1.31 | 0.00 | Core Cosmolo | -0.52 |  |
| 95 | 1588 | 1.87 | 0.25 | 0.00 | 0.13 | 0.06 | 0.00 | Core Cosmolo | 0.76 |  |
| 96 | 415 | -0.51 | 0.24 | 0.00 | 0.00 | 1.45 | 0.00 | NT-Influence | 0.48 |  |
| 97 | 738 | 1.78 | 0.27 | 0.00 | 0.14 | 0.54 | 0.00 | Core Cosmolo | 0.27 |  |
| 98 | 547 | 1.63 | 0.18 | 0.00 | 0.18 | 0.55 | 0.00 | Core Cosmolo | -0.73 |  |
| 99 | 325 | -2.00 | 0.00 | 0.00 | 0.00 | 4.31 | 0.00 | NT-Influence | 0.00 |  |
| 100 | 647 | 1.08 | 0.00 | 0.00 | 0.00 | 0.62 | 0.46 | NT-Influence | 0.00 |  |
| 101 | 736 | 4.01 | 1.63 | 0.00 | 0.00 | 0.54 | 0.00 | Core Cosmolo | 0.54 |  |
| 102 | 554 | -0.18 | 0.36 | 0.00 | 0.00 | 1.44 | 0.00 | NT-Influence | 0.00 |  |
| 103 | 243 | 2.75 | 0.41 | 0.00 | 0.00 | 1.23 | 0.00 | Core Cosmolo | 0.83 |  |
| 104 | 185 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | NT-Influence | 0.00 |  |
| 105 | 357 | -3.76 | 0.00 | 0.84 | 0.28 | 0.00 | 0.00 | NT-Influence | -2.25 |  |
| 106 | 368 | 5.85 | 1.90 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | -0.54 |  |
| 107 | 173 | 3.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 0.00 |  |
| 108 | 227 | -0.27 | 0.44 | 0.00 | 0.00 | 1.32 | 0.00 | NT-Influence | 0.89 |  |
| 109 | 679 | 1.25 | 0.44 | 0.00 | 0.00 | 3.53 | 0.15 | Core Cosmolo | 0.30 | ✅ |
| 110 | 146 | 2.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 0.00 |  |
| 111 | 229 | 2.39 | 0.44 | 0.00 | 0.00 | 0.00 | 0.00 | Core Cosmolo | 0.88 |  |
| 112 | 1149 | -1.87 | 0.09 | 0.26 | 0.17 | 0.70 | 0.00 | NT-Influence | -0.35 |  |
| 113 | 206 | 5.11 | 2.91 | 0.00 | 0.49 | 0.00 | 0.00 | Core Cosmolo | 0.97 |  |
| 114 | 469 | 1.79 | 0.43 | 0.00 | 0.21 | 0.85 | 0.00 | Core Cosmolo | -0.43 | ✅ |
| 115 | 3121 | -0.00 | 0.99 | 0.10 | 0.03 | 1.31 | 0.00 | NT-Influence | 0.96 | ✅ |
| 116 | 410 | -0.12 | 0.00 | 0.00 | 0.00 | 0.24 | 0.00 | NT-Influence | 0.00 |  |
| 117 | 171 | -1.17 | 0.00 | 0.00 | 0.58 | 0.00 | 0.00 | NT-Influence | -1.18 |  |
| 118 | 43 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |  | 0.00 |  |
| 119 | 659 | -1.05 | 0.91 | 0.15 | 0.15 | 1.97 | 0.00 | NT-Influence | 1.22 |  |
| 120 | 855 | -1.23 | 0.00 | 0.12 | 0.12 | 0.82 | 0.00 | NT-Influence | -0.00 |  |
| 121 | 763 | 1.34 | 0.00 | 0.00 | 0.13 | 0.79 | 0.00 | Core Cosmolo | -0.26 |  |
| 122 | 6487 | 1.77 | 1.59 | 0.29 | 0.43 | 0.54 | 0.14 | Core Cosmolo | 1.42 | ✅ |
