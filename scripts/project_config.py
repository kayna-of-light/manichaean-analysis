#!/usr/bin/env python3
"""Project configuration system for the Manichaean Analysis pipeline.

Each project (book) has a YAML config file at scripts/projects/<name>/config.yaml
that defines source files, metadata, and pipeline settings. This module provides
a unified way to load configs and resolve output paths.

Directory layout:
    output/
    ├── texts/                              # Phase 0 (OCR→markdown, shared)
    └── projects/
        ├── kephalaia/
        │   ├── cleaned/chapters/           # Phase 1 (LLM clean)
        │   ├── core/chapters/              # Phase 2 (core extraction)
        │   ├── restored/chapters/           # Phase 5 (spiritual reading + restoration)
        │   └── analysis/                   # Analysis outputs
        └── shabuhragan/
            └── ...

Usage:
    from project_config import load_project, list_projects

    cfg = load_project("kephalaia")
    print(cfg.paths.cleaned_chapters)  # -> .../output/projects/kephalaia/cleaned/chapters
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = Path(__file__).resolve().parent / "projects"
OUTPUT_ROOT = REPO_ROOT / "output"
DATA_DIR = REPO_ROOT / "data"
TEXTS_DIR = OUTPUT_ROOT / "texts"
SECRETS_PATH = REPO_ROOT / "secrets" / "azure_openai.env"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved paths for a project's pipeline stages."""

    project_dir: Path          # output/projects/<name>
    cleaned: Path              # output/projects/<name>/cleaned
    cleaned_chapters: Path     # output/projects/<name>/cleaned/chapters
    core: Path                 # output/projects/<name>/core
    core_chapters: Path        # output/projects/<name>/core/chapters
    core_data: Path            # output/projects/<name>/core/core_data.json
    core_assembled: Path       # output/projects/<name>/core/restored_core.md
    restored: Path              # output/projects/<name>/restored
    restored_chapters: Path
    restored_assembled: Path
    analysis: Path             # output/projects/<name>/analysis
    analysis_chapters: Path    # output/projects/<name>/analysis/chapters

    def ensure_dirs(self) -> None:
        """Create all output directories if they don't exist."""
        for p in (
            self.cleaned_chapters,
            self.core_chapters,
            self.restored_chapters,
            self.analysis,
            self.analysis_chapters,
        ):
            p.mkdir(parents=True, exist_ok=True)


@dataclass
class ProjectConfig:
    """Full configuration for a project (loaded from config.yaml)."""

    name: str
    display_name: str
    source_text: str                    # filename in output/texts/
    source_pdf: str                     # filename in data/
    source_ocr_json: str                # filename in data/
    language: str                       # original script language
    translation_language: str           # language of the translation
    has_original_text: bool             # whether original script is interleaved
    translator: str
    edition: str
    chapter_pattern: str                # e.g. "ch_{num:03d}.json"
    assembled_filename: str             # e.g. "restored_kephalaia.md"
    clean_script: str | None            # relative path to book-specific clean script
    # Pipeline settings
    document_type: str = "composite_text"     # "composite_text" or "fragment_collection"
    include_original_text: bool = False       # include original language text in pipeline
    extra: dict[str, Any] = field(default_factory=dict)

    # Resolved paths (set after loading)
    paths: ProjectPaths = field(init=False)

    def __post_init__(self) -> None:
        project_dir = OUTPUT_ROOT / "projects" / self.name
        self.paths = ProjectPaths(
            project_dir=project_dir,
            cleaned=project_dir / "cleaned",
            cleaned_chapters=project_dir / "cleaned" / "chapters",
            core=project_dir / "core",
            core_chapters=project_dir / "core" / "chapters",
            core_data=project_dir / "core" / "core_data.json",
            core_assembled=project_dir / "core" / "restored_core.md",
            restored=project_dir / "restored",
            restored_chapters=project_dir / "restored" / "chapters",
            restored_assembled=(
                project_dir / "restored" / self.assembled_filename
            ),
            analysis=project_dir / "analysis",
            analysis_chapters=project_dir / "analysis" / "chapters",
        )

    @property
    def source_text_path(self) -> Path:
        return TEXTS_DIR / self.source_text

    @property
    def source_pdf_path(self) -> Path:
        return DATA_DIR / self.source_pdf

    @property
    def source_ocr_json_path(self) -> Path:
        return DATA_DIR / self.source_ocr_json

    def chapter_filename(self, num: int) -> str:
        """Return the chapter filename for a given number, e.g. 'ch_038.json'."""
        return self.chapter_pattern.format(num=num)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_project(name: str) -> ProjectConfig:
    """Load a project config by name (directory under scripts/projects/)."""
    config_path = PROJECTS_DIR / name / "config.yaml"
    if not config_path.exists():
        available = list_projects()
        print(f"ERROR: Project '{name}' not found at {config_path}")
        if available:
            print(f"  Available projects: {', '.join(available)}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    pipeline = raw.get("pipeline", {})

    return ProjectConfig(
        name=raw["name"],
        display_name=raw["display_name"],
        source_text=raw["source"]["text_file"],
        source_pdf=raw["source"]["pdf_file"],
        source_ocr_json=raw["source"]["ocr_json"],
        language=raw.get("metadata", {}).get("language", "unknown"),
        translation_language=raw.get("metadata", {}).get(
            "translation_language", "english"
        ),
        has_original_text=raw.get("metadata", {}).get("has_original_text", False),
        translator=raw.get("metadata", {}).get("translator", "unknown"),
        edition=raw.get("metadata", {}).get("edition", ""),
        chapter_pattern=raw.get("chapter_pattern", "ch_{num:03d}.json"),
        assembled_filename=raw.get(
            "assembled_filename", f"restored_{raw['name']}.md"
        ),
        clean_script=raw.get("clean_script"),
        document_type=pipeline.get("document_type", "composite_text"),
        include_original_text=pipeline.get("include_original_text", False),
        extra=raw.get("extra", {}),
    )


def list_projects() -> list[str]:
    """List all available project names (directories with config.yaml)."""
    if not PROJECTS_DIR.exists():
        return []
    return sorted(
        d.name
        for d in PROJECTS_DIR.iterdir()
        if d.is_dir() and (d / "config.yaml").exists()
    )


def get_default_project() -> str:
    """Return the default project name (first available, or 'kephalaia')."""
    projects = list_projects()
    return projects[0] if projects else "kephalaia"
