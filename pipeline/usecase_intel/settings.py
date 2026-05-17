"""Shared defaults for the usecase intel pipeline."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_USER_AGENT = "UseCaseIntelBot/0.1 (+https://github.com/vibewatch/usecase)"
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 30.0

SOURCES_PATH = Path("data/sources.json")
DISCOVERED_URLS_PATH = Path("data/discovered_urls.jsonl")
FETCH_MANIFEST_PATH = Path("data/fetch_manifest.jsonl")
RAW_CONTENT_ROOT = Path("data/raw_content")
HTTP_CACHE_DIR = Path("data/http_cache")
EXTRACT_JOBS_ROOT = Path("data/extract_jobs")
RECORDS_ROOT = Path("data/records")
MERGED_CASE_STUDIES_PATH = Path("data/case-studies.merged.json")
GENERATED_CASE_STUDIES_PATH = Path("data/case-studies.generated.json")
SQLITE_PATH = Path("data/usecase_intel.sqlite")
SAMPLE_CASE_STUDIES_PATH = Path("data/case-studies.sample.json")

TAXONOMY_PATH = Path("taxonomy.json")
EXTRACTION_SKILL_PATH = Path(".agents/skills/case-study-extraction/SKILL.md")
HOST_STRATEGIES_PATH = REPO_ROOT / "pipeline/usecase_intel/config/host-strategies.json"


def fetch_options(config: object) -> tuple[str, float]:
	if not isinstance(config, dict):
		return DEFAULT_USER_AGENT, DEFAULT_DELAY_SECONDS
	return (
		str(config.get("user_agent") or DEFAULT_USER_AGENT),
		float(config.get("default_delay_seconds") or DEFAULT_DELAY_SECONDS),
	)
