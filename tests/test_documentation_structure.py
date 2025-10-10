from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
STARLIGHT_DIR = ROOT / "docs" / "starlight"
DOCS_DIR = STARLIGHT_DIR / "src" / "content" / "docs"
ADR_DIR = ROOT / "docs" / "adrs"
ADR_INDEX = ADR_DIR / "index.json"
REQUIRED_FRONTMATTER_KEYS = {"title", "description", "template"}


def _extract_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path} is missing YAML frontmatter"
    closing = text.find("\n---", 3)
    assert closing != -1, f"{path} frontmatter not terminated"
    frontmatter_text = text[4:closing]
    parsed = yaml.safe_load(frontmatter_text) or {}
    assert isinstance(parsed, dict), f"{path} frontmatter must be a mapping"
    return parsed


def test_starlight_workspace_scaffold() -> None:
    assert (STARLIGHT_DIR / "package.json").is_file()
    assert (STARLIGHT_DIR / "astro.config.mjs").is_file()
    assert (STARLIGHT_DIR / "tsconfig.json").is_file()
    package_json = json.loads((STARLIGHT_DIR / "package.json").read_text(encoding="utf-8"))
    for script in ("build", "check", "lint", "format", "format:write"):
        assert script in package_json["scripts"], f"Missing npm script: {script}"
    assert "@astrojs/starlight" in (STARLIGHT_DIR / "astro.config.mjs").read_text(encoding="utf-8")


def test_diataxis_directories_populated() -> None:
    for section in ("tutorials", "how-to", "reference", "explanations"):
        section_dir = DOCS_DIR / section
        assert section_dir.is_dir(), f"Missing Diátaxis directory: {section}"
        files = sorted(section_dir.glob("*.mdx"))
        assert files, f"Diátaxis directory {section} must contain at least one page"


@pytest.mark.parametrize("doc_path", sorted(DOCS_DIR.rglob("*.mdx")))
def test_docs_have_frontmatter(doc_path: Path) -> None:
    frontmatter = _extract_frontmatter(doc_path)
    missing = REQUIRED_FRONTMATTER_KEYS - set(frontmatter)
    assert not missing, f"{doc_path} missing frontmatter keys: {sorted(missing)}"
    template = frontmatter["template"]
    assert template in {
        "doc",
        "splash",
    }, f"Unsupported template {template} in {doc_path}"
    description = frontmatter["description"]
    assert isinstance(description, str) and description.strip(), f"{doc_path} needs a description"
    if "tags" in frontmatter:
        assert isinstance(frontmatter["tags"], list), f"{doc_path} tags must be a list"


def test_adr_index_matches_files() -> None:
    assert ADR_INDEX.is_file(), "ADR index missing"
    index = json.loads(ADR_INDEX.read_text(encoding="utf-8"))
    entries = index.get("adrs", [])
    assert entries, "ADR index must list at least one decision"
    expected_filenames: set[str] = set()
    ids_seen: set[str] = set()
    for entry in entries:
        adr_id = entry["id"]
        slug = entry["slug"]
        expected_filenames.add(f"{adr_id}-{slug}.md")
        assert adr_id not in ids_seen, f"Duplicate ADR id {adr_id}"
        ids_seen.add(adr_id)
        adr_path = ADR_DIR / f"{adr_id}-{slug}.md"
        assert adr_path.is_file(), f"Missing ADR file for {adr_id}"
        frontmatter = _extract_frontmatter(adr_path)
        for key in ("id", "title", "status", "decision_date"):
            assert key in frontmatter, f"ADR {adr_id} missing {key}"
        assert frontmatter["id"] == adr_id
        assert frontmatter["title"] == entry["title"]
        assert frontmatter["status"] == entry["status"]
        decision_date = frontmatter["decision_date"]
        if not isinstance(decision_date, str):
            decision_date = decision_date.isoformat()
        assert decision_date == entry["decision_date"]
        assert frontmatter["status"] in {"Accepted", "Proposed", "Superseded"}
    actual_filenames = {path.name for path in ADR_DIR.glob("ADR-*.md")}
    assert actual_filenames == expected_filenames, "ADR index out of sync with files"
