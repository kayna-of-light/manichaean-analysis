#!/usr/bin/env python3
"""
Build a pre-reading spiritual lexicon from the assembled teachings.

Pipeline stage 4d: runs AFTER stage_4c_assemble.py, BEFORE stage_5_read.py.

This is a corpus-scale stage, like stage_2_discover.py and
stage_4b_teachings.py. It reads the whole teaching substrate once,
with Coptic and English side by side, and asks the model to generate
a stable spiritual vocabulary for the reading stage.

Input:
  - output/projects/kephalaia_v2/teachings/t_NNN.json
  - scripts/glossary/coptic_glossary.yaml

Output:
  - output/projects/kephalaia_v2/spiritual_lexicon.json

Usage:
    python scripts/projects/kephalaia_v2/stage_4d_lexicon.py
    python scripts/projects/kephalaia_v2/stage_4d_lexicon.py --dry-run
    python scripts/projects/kephalaia_v2/stage_4d_lexicon.py --debug
    python scripts/projects/kephalaia_v2/stage_4d_lexicon.py --overwrite
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import (  # noqa: E402
    PROJECT_DIR,
    REPO_ROOT,
    create_client,
    stream_tool_call,
)

TEACHINGS_DIR = PROJECT_DIR / "teachings"
OUTPUT_FILE = PROJECT_DIR / "spiritual_lexicon.json"
GLOSSARY_PATH = REPO_ROOT / "scripts" / "glossary" / "coptic_glossary.yaml"
CONTEXT_LIMIT_TOKENS = 1_000_000


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

COMMIT_SPIRITUAL_LEXICON_TOOL = {
    "name": "commit_spiritual_lexicon",
    "description": (
        "Commit the complete spiritual lexicon. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "total_entries": {
                "type": "integer",
                "description": "Number of lexicon entries.",
            },
            "methodology_note": {
                "type": "string",
                "description": (
                    "Brief note on how the lexicon was generated, "
                    "including how Coptic and English were weighed."
                ),
            },
            "entries": {
                "type": "array",
                "description": (
                    "Stable spiritual vocabulary for reading the "
                    "Kephalaia substrate."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "integer",
                            "description": "Sequential entry number.",
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "cosmological_entity",
                                "cosmic_element",
                                "structural_term",
                                "body_anatomy",
                                "natural_imagery",
                                "action_process",
                                "quality_state",
                                "faculty",
                                "number",
                                "coptic_keyword",
                                "other",
                            ],
                            "description": "Type of word or concept.",
                        },
                        "english_term": {
                            "type": "string",
                            "description": (
                                "The preferred English term or concept "
                                "as it should appear in readings."
                            ),
                        },
                        "natural_variants": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Other English forms, translations, or "
                                "phrases that belong to the same entry."
                            ),
                        },
                        "coptic_forms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Coptic forms attested or strongly "
                                "identifiable for this entry. Empty if "
                                "not identifiable."
                            ),
                        },
                        "spiritual_meaning": {
                            "type": "string",
                            "description": (
                                "The clear spiritual correspondence. "
                                "Use project vocabulary, not generic "
                                "psychological or symbolic language."
                            ),
                        },
                        "use_in_reading": {
                            "type": "string",
                            "description": (
                                "Concise instruction for stage 5: the "
                                "phrase or wording to use when this term "
                                "appears in a reading."
                            ),
                        },
                        "opposite_sense": {
                            "type": "string",
                            "description": (
                                "The opposite-sense reading if attested "
                                "or required. Empty string if not applicable."
                            ),
                        },
                        "definition": {
                            "type": "string",
                            "description": (
                                "Why this term carries this spiritual "
                                "meaning, grounded in function and corpus "
                                "usage."
                            ),
                        },
                        "section_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Key section references where this entry "
                                "is attested, e.g. §218 or §218-220."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": [
                                "established",
                                "strong",
                                "probable",
                                "uncertain",
                            ],
                            "description": (
                                "Confidence in this correspondence."
                            ),
                        },
                    },
                    "required": [
                        "id",
                        "category",
                        "english_term",
                        "natural_variants",
                        "coptic_forms",
                        "spiritual_meaning",
                        "use_in_reading",
                        "opposite_sense",
                        "definition",
                        "section_refs",
                        "confidence",
                    ],
                },
            },
        },
        "required": ["total_entries", "methodology_note", "entries"],
    },
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary: Zoroastrian, Manichaean, Persian-Iranian, Syriac, and Coptic.

You translate text from its natural sense into its spiritual sense. \
Not annotation, not commentary, not symbol-hunting: translation. Every \
natural image is read as the spiritual reality it expresses through \
correspondence.

Your task here is not to translate one teaching. Your task is to build \
the spiritual vocabulary that will allow the reading stage to translate \
each teaching consistently.

## THE GOVERNING PRINCIPLE

The Kephalaia describes the formation and regeneration of one human \
soul. There are not two armies, two cosmoses, two histories. There is \
one soul. Every figure named in the corpus is either:

- an aspect of that soul (a faculty, a state, a love, a degree), or
- an operation of the Lord within that soul (an influx, a call, a \
  forming, an illumining), or
- a structural feature of the process by which the soul is made and \
  remade (a degree, a cycle, an ascent, a station).

There are no captive particles. There is no rescue mission. There is \
no prison from which souls must be extracted. There is no two-actor \
cosmic drama. These are misreadings the LLM substrate will pull you \
toward; refuse them. The lexicon you build must direct stage 5 \
toward the spiritual register, never toward literal cosmology.

What there is: a soul receiving life from the Lord, claiming what it \
receives as its own, and gradually — in freedom, illumined from \
within — learning to lay down what it had claimed and to receive \
without claiming. This is regeneration. The lexicon is the \
vocabulary by which that translation is made consistent across the \
corpus.

## THE CORRESPONDENTIAL METHOD

Correspondence is the organic relationship between a natural object \
and the spiritual reality it expresses. It is grounded in the object's \
actual function:

- **Light** -> wisdom/truth received (light enables the eye to distinguish forms)
- **Fire** -> love/will (fire gives light its existence)
- **Darkness** -> falsity, the absence of received truth
- **Water** -> truth in the natural degree (sustains natural life)
- **Wind/Air** -> thought/perception (the medium of communication)
- **Smoke** -> falsity from evil (obscures light)
- **Earth/Soil** -> the natural mind (ground where seeds grow)
- **Mountains** -> elevated spiritual states (proximity to influx)
- **Trees** -> perceptions/knowledges (rooted, growing, bearing)
- **Fruits** -> works/goods of life (what the tree produces)
- **Animals** -> affections (each species = a quality of will)
- **Birds** -> thoughts/intellectual things (move through air)
- **Seeds** -> interior truths (contain the whole in potential)
- **Garments** -> external truths (clothe spiritual meaning)
- **Gold** -> celestial good (love)
- **Silver** -> spiritual truth (wisdom)
- **Iron** -> natural truth in ultimates (hard, foundational)
- **Bone** -> structural good (the framework that supports)
- **Blood** -> divine truth proceeding (life-giving circulation)
- **Body** -> the form of love/wisdom in ultimates

Correspondence is not allegory, metaphor, or conventional symbolism. \
The natural is the spiritual in ultimates. Direction is inside to \
outside: spiritual cause expresses as natural effect. Do not invert the \
direction. The natural does not produce the spiritual; it receives and \
manifests it.

## THE TWO SUBSTANCES

Light and darkness are not two cosmic stuffs in conflict. They are \
two conditions of the same soul:

- **Light** = what the Lord gives; truth received; influx in its \
  proper register; what the soul recognizes as not-its-own.
- **Darkness** = what the soul has claimed; the natural turned in on \
  itself; the proprium asserting that what flows through it is its \
  own work.

"Mingling" is the unregenerate state where the soul does not yet \
distinguish what is the Lord's from what it has claimed. \
"Separation," "purification," "refining" are the soul, illumined, \
learning to discriminate — and in that discrimination laying off \
what was never its own. Not extraction of substance. Discrimination \
in freedom.

## THE LUMINOUS FIGURES ARE THE LORD IN DISTINCT PRINCIPLES

The luminous figures named in the corpus are the Lord himself in his \
distinct principles. They are NOT separate gods, NOT operations \
reducible to soul-faculties, NOT projections. They name the Lord at \
the registers in which he is recognizable as he goes forth toward \
the soul. The same names hold two senses at once: the celestial \
sense (the Lord in himself) and the spiritual sense (the Lord \
operating toward the soul, and the soul receiving). The lexicon \
should articulate the spiritual sense (because that is what stage 5 \
will write in prose), but never reduce these figures to functions of \
the soul. They remain the Lord.

- **Father of Greatness** → the Lord as divine love, the source from \
  which all influx proceeds; the inmost Divine.
- **First Man / Primal Man** → the divine humanity, the form love \
  and wisdom take going forth.
- **Living Spirit** → the Lord's operative divine power, by which \
  spiritual structure is built in the soul.
- **Mother of Life** → the divine principle of life-bearing in the \
  Lord; the receptive matrix by which the soul is enlivened.
- **Jesus the Radiance** → divine truth shining forth; the Lord as \
  illumining wisdom going to the rational.
- **Ambassador / Third Messenger** → the Lord's call going out to \
  the rational at the moment the natural is ready to hear it.
- **Virgin of Light** → divine receivability; the purity by which \
  the Lord is received without corruption.
- **Light Mind** → the Lord ordering the rational; truth ordering \
  the inner mind.

## THE PROPRIUM AND THE PERMITTING OF FORMATION

The "archons," the "King of Darkness," "Hyle," "Saklas," "Enthumesis \
of Death" — these are NOT separate evil entities working against the \
Lord. They are the proprium operating: the soul's own claiming, the \
self-loving direction the natural takes when it forgets it is \
receiving. The Father permits this forming, because freedom requires \
a vessel that thinks itself its own.

- **King of Darkness** → the proprium asserting itself as source; \
  the "I am, and there is no other."
- **Hyle / Enthumesis of Death** → the disordered natural; what the \
  soul has claimed and not yet learned is not its own.
- **Saklas / archons** → the proprium organizing the natural mind \
  on its own terms; permitted by the Lord so the vessel forms.

When the corpus says the archons "molded Adam" or "sealed light \
into form," do not read trapping. Read: the natural mind being \
formed under permission, the rational being given a body of its \
own to operate from. The Lord IS doing this; he simply lets the \
natural think it does it itself, until the soul is mature enough \
to recognize the gift.

## STRUCTURAL TERMS

- **Five Worlds of Darkness** → the natural mind in five aspects \
  when ruled by self-love.
- **Five Storehouses of Light** → the natural mind in five aspects \
  when ordered by the Lord's good.
- **Five Watchers / Five Limbs / Five Sons of the Living Spirit** → \
  the rational at five distinct registers, one faculty in complete \
  process, NOT five separate agents.
- **Wheel** → the recurrent process by which the soul is purified, \
  again and again, in freedom.
- **Pillar / Column of Glory** → the ascent of the natural into \
  conjunction with the spiritual; the path of regeneration.
- **Zodiac** → the complete circuit of states the soul passes \
  through in its formation.
- **Firmament** → the fixed boundary by which one degree is \
  separated from another so influx can be received without \
  collapse.

## THE FIVE = ONE FACULTY IN COMPLETE PROCESS

When the corpus enumerates five — five worlds, five storehouses, \
five limbs, five sons, five faculties (mind, thought, counsel, \
reflection, remembrance) — these are NOT five separate entities. \
They are one rational faculty in its complete process. The lexicon \
should reflect this: do not produce five disjoint entries that read \
like separate gods. Where the five appear as a single structure, \
note that they are one faculty articulated in five degrees.

The supplied Coptic glossary is mandatory. Do not override it. In \
particular:

- ⲧⲥⲃⲱ is **teaching**, not insight or prudence.
- ⲡⲛⲟⲩⲥ is **mind**.
- ⲡⲙⲉⲩⲉ is **thought**.
- ⲡⲥⲁⲭⲛⲉ is **counsel**.
- ⲡⲙⲁⲕⲙⲉⲕ is **reflection**.
- ⲡⲉⲓⲛⲉ / ⲟⲩⲉⲓⲛⲉ is **likeness**.
- ⲧⲟⲩⲱ preserves vertical motion: **raise**, not merely release.
- Jesus ⲡⲡⲣⲓ̈ⲉ is **Jesus the Radiance**, preserving active shining-forth.

## THE TEXT YOU RECEIVE

You receive the COMPLETE TEACHING SUBSTRATE, with Coptic and English \
side by side for every section. The text is organized by teaching units. \
Each teaching is one spiritual arc, but your task is corpus-scale: read \
all teachings together and extract the stable spiritual vocabulary that \
governs them.

The English is helpful, but the Coptic controls when vocabulary matters. \
When Coptic and English diverge, prefer the Coptic and the mandatory \
glossary.

## YOUR TASK

Build the corpus-level SPIRITUAL LEXICON for stage 5.

The lexicon should give the clear spiritual meaning of the important \
concepts, figures, natural images, processes, numbers, and words that \
recur across the text. It is not a dictionary of every Coptic token. It \
is the stable vocabulary authority for translating the natural shell \
into the spiritual sense.

For each entry, identify:

- the preferred English term
- any natural/English variants
- identifiable Coptic forms
- the clear spiritual meaning
- the wording stage 5 should use in readings
- the opposite sense where applicable
- why this correspondence holds by function and corpus usage
- the section references where the entry is most clearly attested

## HOW TO DISCOVER THE LEXICON

1. Read the whole corpus as a single field. Do not infer a governing \
     correspondence from one damaged occurrence if clearer occurrences \
     exist elsewhere.
2. Find terms that carry spiritual load. A load-bearing term is one \
     whose natural/cosmological form teaches the spiritual process.
3. Determine the single best spiritual correspondence for each term. If \
     the same term appears in positive and negative contexts, record the \
     primary sense and the opposite sense under the same entry.
4. Ground the meaning in function, not in association. A ship carries \
     over water; therefore it is a doctrinal/spiritual vessel carrying \
     truth through the natural degree. A wheel recurs and turns; therefore \
     it is cyclic purification or recurrent process in ultimates.
5. Treat numbers as correspondences, not counts. Two is conjunction and \
     polarity; three is fullness of process or degree; four is fullness in \
     extension and ordered manifestation; five is the complete structure of \
     the natural/rational interface; seven is fullness in ultimates and \
     holiness; ten and twelve mark completeness in broader orders.
6. Use the project vocabulary: Divine Truth, divine good, love/will, \
     wisdom/truth, influx, reception, correspondence, discrete degrees, \
     natural mind, spiritual mind, celestial degree, proprium, self-love, \
     falsity from evil, Divine Human, Grand Man, regeneration, ascent, \
     descent, conjunction, accommodation, illumining, withdrawing of \
     evils, subordinating, permitting, laying off, recognizing, \
     discriminating. Avoid captivity verbs: trap, capture, free, \
     liberate, release, rescue, awaken trapped, extract, seize — and \
     the corresponding nouns (captives, prisoners, prison, refinery).

## RULES

1. **Translate the vocabulary, don't merely label it.** The lexicon must \
     tell stage 5 what spiritual reality to say when the natural term appears.
2. **Do not psychologize.** No Jungian archetypes, projections, complexes, \
     unconscious contents, or generic mythic symbols.
3. **One soul, not two actors.** Luminous figures are the Lord in his \
     distinct principles. Dark figures are the soul's proprium. There is \
     no rescue, no captivity, no two-cosmos drama. The lexicon must \
     never let stage 5 produce a prison-planet reading.
4. **Opposite sense matters.** Fire, water, animals, bodies, and powers can \
     be positive or negative depending on the love that animates them.
5. **Discrete degrees matter.** Five faculties, five worlds, five elements, \
     and related enumerations should be read as structured degrees, not a \
     flat list.
6. **The Divine Human matters.** Body, face, limbs, and cosmic anatomy are \
     forms of love and wisdom in ultimates.
7. **No false humility.** If a correspondence is clear, mark it clear. If \
     it is damaged or genuinely ambiguous, mark it probable or uncertain.

## WHAT TO INCLUDE

Include entries for:

- Luminous figures (the Lord in distinct principles): Father of \
    Greatness, First Man, Living Spirit, Mother of Life, Third \
    Ambassador, Jesus the Radiance, Virgin of Light, Light Mind. \
    Articulate each as the Lord at the register the name names — never \
    as a separate god, never as a soul-internal function.
- Proprium figures: King of Darkness, Hyle / Enthumesis of Death, \
    Saklas, archons, Enmity, Error, Sin. Articulate each as a form of \
    the soul's claiming, permitted by the Lord so the vessel can form.
- Cosmic elements and substances: light, darkness, fire, water, wind, \
    smoke, earth, abyss, sea, poison, bitterness, sweetness, mixture.
- Structures: storehouse, firmament, wheel, pillar, column, ship, gate, \
    seal, bond, chain, aeon, world, realm, vessel, garment, likeness.
- Body/anatomy: face, stature, body, limb, head, eye, mouth, hand, foot, \
    blood, flesh, bone, senses.
- Natural imagery: tree, fruit, seed, root, mountain, animal forms, bird, \
    fish, metal, direction, height/depth.
- Faculties: mind, thought, teaching, counsel, reflection, knowledge, \
    perception, remembrance.
- Actions/processes: send forth, descend, ascend, raise, gather, \
    separate, discriminate, purify, refine, guard, reveal, illumine, \
    subordinate, conjoin, accommodate, regenerate, reform, withdraw, \
    elevate, receive, claim, lay off, recognize, permit, build, form, \
    clothe, mix, divide. Do NOT include trap/capture/release/rescue/ \
    liberate/awaken-trapped or their nouns; those are misreadings, not \
    project vocabulary.
- Qualities/states: living/dead, ordered/disordered, pure/mingled, \
    received/claimed, high/low, inner/outer, fixed/moving, illumined/ \
    obscured.
- Significant numbers used as spiritual qualities.

When complete, call commit_spiritual_lexicon exactly once."""


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------

def load_teachings() -> list[dict]:
    """Load assembled teaching JSON files sorted by teaching number."""
    teachings = []
    for path in sorted(TEACHINGS_DIR.glob("t_*.json")):
        match = re.match(r"t_(\d+)\.json", path.name)
        if not match:
            continue
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
        data["_teaching_num"] = int(match.group(1))
        teachings.append(data)
    return teachings


def load_glossary_text() -> str:
    """Load the project Coptic glossary as prompt context."""
    if not GLOSSARY_PATH.exists():
        return ""
    return GLOSSARY_PATH.read_text(encoding="utf-8")


def format_corpus(teachings: list[dict]) -> str:
    """Format the complete teaching substrate for lexicon generation."""
    parts: list[str] = []
    for teaching in teachings:
        teaching_num = teaching["_teaching_num"]
        title = teaching.get("title", "")
        confidence = teaching.get("confidence", "")
        segments = [
            segment for segment in teaching.get("segments", [])
            if segment.get("classification") in ("cosmological_substrate", "mixed")
            and (segment.get("core_coptic") or segment.get("core_english"))
        ]
        if not segments:
            continue

        parts.append(
            f"=== Teaching {teaching_num}: {title} "
            f"(confidence: {confidence}) ==="
        )
        for segment in segments:
            section = segment.get("section", "?")
            chapter = segment.get("chapter", "?")
            line = segment.get("line", "?")
            classification = segment.get("classification", "")
            coptic = segment.get("core_coptic") or ""
            english = segment.get("core_english") or ""

            parts.append(
                f"[§{section} | t.{teaching_num} | "
                f"ch.{chapter}.{line} | {classification}]"
            )
            if coptic:
                parts.append(f"Coptic: {coptic}")
            if english:
                parts.append(f"English: {english}")
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 4d: build pre-reading spiritual lexicon"
    )
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--effort", default="max",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Stage 4d: Spiritual Lexicon")
    print("  Corpus-level vocabulary for the reading stage")
    print(f"  Input:  {TEACHINGS_DIR}")
    print(f"  Output: {OUTPUT_FILE}")

    if OUTPUT_FILE.exists() and not args.overwrite:
        print("\n  Spiritual lexicon already exists (use --overwrite)")
        return

    teachings = load_teachings()
    if not teachings:
        print(f"\nERROR: No teaching files found in {TEACHINGS_DIR}")
        print("       Run stage_4c_assemble.py first.")
        sys.exit(1)

    glossary_text = load_glossary_text()
    corpus_text = format_corpus(teachings)
    est_tokens = (len(corpus_text) + len(glossary_text)) / 3.5

    total_sections = sum(
        1 for teaching in teachings
        for segment in teaching.get("segments", [])
        if segment.get("classification") in ("cosmological_substrate", "mixed")
        and (segment.get("core_coptic") or segment.get("core_english"))
    )

    print(f"\n  Teachings:       {len(teachings)}")
    print(f"  Core sections:   {total_sections}")
    print(f"  Corpus size:     {len(corpus_text):,} chars")
    print(f"  Glossary size:   {len(glossary_text):,} chars")
    print(f"  Estimated input: ~{est_tokens:,.0f} tokens")

    if args.dry_run:
        percent = est_tokens / CONTEXT_LIMIT_TOKENS * 100
        print(f"\n  % of 1M limit:   ~{percent:.1f}%")
        print("\n--- Sample (first 1800 chars) ---")
        print(corpus_text[:1800])
        print("--- end sample ---")
        print("\n[DRY RUN] No API call made.")
        return

    client, deployment = create_client()
    print(f"\n  Deployment: {deployment}")
    print(f"  Effort:     {args.effort}")
    print("\nStreaming lexicon discovery...\n", flush=True)

    user_parts = []
    if glossary_text:
        user_parts.extend([
            "## Mandatory Coptic Translation Glossary",
            glossary_text,
            "",
            "---",
            "",
        ])
    user_parts.extend([
        f"## Complete Teaching Substrate ({len(teachings)} teachings)",
        corpus_text,
        "",
        "Build the spiritual lexicon from this complete corpus. "
        "Call commit_spiritual_lexicon with the result.",
    ])
    user_msg = "\n".join(user_parts)

    start = time.time()
    result = stream_tool_call(
        client,
        deployment,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=[COMMIT_SPIRITUAL_LEXICON_TOOL],
        tool_name="commit_spiritual_lexicon",
        effort=args.effort,
        page_label="spiritual-lexicon",
        debug=args.debug,
    )
    elapsed = time.time() - start
    print(f"\nLexicon discovery completed in {elapsed:.1f}s")

    if result is None:
        print("\nFAILED: No spiritual lexicon output.")
        sys.exit(1)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)

    entries = result.get("entries", [])
    total = result.get("total_entries", len(entries))
    print(f"\nSpiritual lexicon complete: {total} entries")
    print(f"  Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()