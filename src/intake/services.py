"""Business logic and I/O services for the intake pipeline.

Contains all functions and classes that perform I/O (disk, subprocess),
orchestration, and non-trivial computation. Imports models from
``distill.intake.models``.
"""

from __future__ import annotations

import json
import logging
import math
import re
import string
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from distill.intake.models import (
    ContentItem,
    ContentSource,
    ContentType,
    DailyIntakeContext,
    FullTextResult,
    IntakeConfig,
    IntakeMemory,
    IntakeState,
    IntakeSynthesisError,
    SeedIdea,
    TopicCluster,
)
from distill.intake.prompts import get_daily_intake_prompt, get_unified_intake_prompt
from distill.llm import LLMError, call_claude, strip_json_fences

logger = logging.getLogger(__name__)


# ===========================================================================
# Seeds  (from seeds.py)
# ===========================================================================

SEEDS_FILENAME = ".distill-seeds.json"


class SeedStore:
    """Manages seed ideas in a simple JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path / SEEDS_FILENAME
        self._seeds: list[SeedIdea] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._seeds = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._seeds = [SeedIdea.model_validate(s) for s in data]
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("Corrupt seeds file at %s, starting fresh", self._path)
            self._seeds = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [s.model_dump(mode="json") for s in self._seeds]
        self._path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def add(self, text: str, tags: list[str] | None = None) -> SeedIdea:
        """Add a new seed idea."""
        seed = SeedIdea(text=text, tags=tags or [])
        self._seeds.append(seed)
        self._save()
        return seed

    def list_unused(self) -> list[SeedIdea]:
        """Return all unused seeds."""
        return [s for s in self._seeds if not s.used]

    def list_all(self) -> list[SeedIdea]:
        """Return all seeds."""
        return list(self._seeds)

    def mark_used(self, seed_id: str, used_in: str) -> None:
        """Mark a seed as consumed by a digest/post."""
        for seed in self._seeds:
            if seed.id == seed_id:
                seed.used = True
                seed.used_in = used_in
                self._save()
                return

    def remove(self, seed_id: str) -> None:
        """Remove a seed by ID."""
        self._seeds = [s for s in self._seeds if s.id != seed_id]
        self._save()

    def to_content_items(self) -> list[ContentItem]:
        """Convert unused seeds to ContentItems for the intake pipeline."""
        items: list[ContentItem] = []
        for seed in self.list_unused():
            item = ContentItem(
                id=f"seed-{seed.id}",
                title=seed.text,
                body=seed.text,
                source=ContentSource.SEEDS,
                source_id=seed.id,
                content_type=ContentType.POST,
                tags=seed.tags,
                published_at=seed.created_at,
                saved_at=seed.created_at,
                metadata={"seed_id": seed.id, "seed_type": "idea"},
            )
            items.append(item)
        return items


# ===========================================================================
# Memory I/O  (from memory.py)
# ===========================================================================

MEMORY_FILENAME = ".intake-memory.json"


def load_intake_memory(output_dir: Path) -> IntakeMemory:
    """Load intake memory from disk."""
    memory_path = output_dir / "intake" / MEMORY_FILENAME
    if not memory_path.exists():
        return IntakeMemory()
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
        return IntakeMemory.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt intake memory at %s, starting fresh", memory_path)
        return IntakeMemory()


def save_intake_memory(memory: IntakeMemory, output_dir: Path) -> None:
    """Save intake memory to disk."""
    memory_path = output_dir / "intake" / MEMORY_FILENAME
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")


# ===========================================================================
# State I/O  (from state.py)
# ===========================================================================

STATE_FILENAME = ".intake-state.json"


def load_intake_state(output_dir: Path) -> IntakeState:
    """Load intake state from disk."""
    state_path = output_dir / "intake" / STATE_FILENAME
    if not state_path.exists():
        return IntakeState()
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return IntakeState.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt intake state at %s, starting fresh", state_path)
        return IntakeState()


def save_intake_state(state: IntakeState, output_dir: Path) -> None:
    """Save intake state to disk."""
    state_path = output_dir / "intake" / STATE_FILENAME
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


# ===========================================================================
# Intelligence  (from intelligence.py)
# ===========================================================================

# Batch size for LLM calls
_BATCH_SIZE = 8

# Structured-output tasks (entity extraction, classification) use Haiku for speed/cost.
# Can be overridden by passing model= to individual functions.
_INTELLIGENCE_MODEL = "claude-haiku-4-5-20251001"


def _call_claude_intelligence(prompt: str, model: str | None = None, timeout: int = 120) -> str:
    """Call Claude CLI with a prompt. Returns stdout or empty string on failure.

    Delegates to the shared :func:`distill.llm.call_claude` and converts
    any :class:`LLMError` into an empty string (callers treat that as a
    soft failure).
    """
    try:
        return call_claude(
            prompt,
            "",
            model=model,
            timeout=timeout,
            label="intelligence",
        )
    except LLMError as exc:
        logger.warning("Claude CLI call failed: %s", exc)
        return ""


def _parse_json_response(text: str) -> Any:
    """Extract JSON from LLM response, handling markdown code fences and preamble text.

    Uses :func:`distill.llm.strip_json_fences` for fence stripping, then
    applies additional heuristics for preamble text that the shared helper
    does not cover.
    """
    text = text.strip()
    if not text:
        return None

    # Use the shared helper to strip markdown code fences (```json ... ```)
    if "```" in text:
        text = strip_json_fences(text)

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: find a JSON array in the response (Claude sometimes adds preamble text)
    bracket_start = text.find("[")
    if bracket_start != -1:
        bracket_end = text.rfind("]")
        if bracket_end > bracket_start:
            candidate = text[bracket_start : bracket_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    # Fallback: find a JSON object in the response
    brace_start = text.find("{")
    if brace_start != -1:
        brace_end = text.rfind("}")
        if brace_end > brace_start:
            candidate = text[brace_start : brace_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    return None


def _build_entity_prompt(items: list[ContentItem]) -> str:
    """Build a prompt for entity extraction from a batch of items."""
    parts: list[str] = []
    for i, item in enumerate(items):
        text = item.title
        if item.body:
            text += "\n" + item.body[:500]
        parts.append(f"[ITEM {i}]\n{text}")

    items_text = "\n\n".join(parts)

    return f"""Extract named entities from each content item below.

Return ONLY valid JSON — an array of objects, one per item, in the same order.
Each object must have these fields:
- projects: list of project/product names mentioned
- technologies: list of technologies, frameworks, languages
- people: list of people mentioned
- concepts: list of abstract concepts or topics
- organizations: list of companies or organizations

Example: [{{"projects": ["distill"], "technologies": ["python", \
"pgvector"], "people": [], "concepts": ["content pipeline"], \
"organizations": ["Anthropic"]}}]

Content items:

{items_text}"""


def _build_classification_prompt(items: list[ContentItem]) -> str:
    """Build a prompt for content classification."""
    parts: list[str] = []
    for i, item in enumerate(items):
        text = item.title
        if item.body:
            text += "\n" + item.body[:300]
        parts.append(f"[ITEM {i}]\n{text}")

    items_text = "\n\n".join(parts)

    return f"""Classify each content item below.

Return ONLY valid JSON — an array of objects, one per item, in the same order.
Each object must have:
- category: one of "tutorial", "opinion", "news", "reference", \
"session-log", "announcement", "discussion"
- sentiment: one of "positive", "negative", "neutral", "mixed"
- relevance: integer 1-5 (how relevant to a software engineer's daily work)

Example: [{{"category": "tutorial", "sentiment": "positive", "relevance": 4}}]

Content items:

{items_text}"""


def _build_topic_prompt(items: list[ContentItem], existing_topics: list[str]) -> str:
    """Build a prompt for topic extraction across items."""
    titles = [item.title for item in items if item.title][:30]
    titles_text = "\n".join(f"- {t}" for t in titles)

    existing = ", ".join(existing_topics) if existing_topics else "(none)"

    return f"""Identify the main topics/themes across these content items.

Existing topics: {existing}

Content titles:
{titles_text}

Return ONLY valid JSON — a flat array of topic strings (3-8 topics).
Merge similar topics. Prefer existing topic names when they still apply.
Example: ["AI agents", "developer tools", "testing patterns"]"""


def extract_entities(
    items: list[ContentItem],
    *,
    model: str | None = None,
    timeout: int = 120,
) -> list[ContentItem]:
    """Extract named entities from content items via LLM.

    Populates item.metadata["entities"] with projects, technologies,
    people, concepts, and organizations.

    Args:
        items: Content items to process (modified in place).
        model: Optional Claude model override.
        timeout: LLM timeout in seconds.

    Returns:
        The same list with entities populated.
    """
    failed_empty = 0
    failed_parse = 0
    succeeded = 0

    for batch_start in range(0, len(items), _BATCH_SIZE):
        batch = items[batch_start : batch_start + _BATCH_SIZE]
        prompt = _build_entity_prompt(batch)
        response = _call_claude_intelligence(
            prompt, model=model or _INTELLIGENCE_MODEL, timeout=timeout
        )

        if not response:
            failed_empty += 1
            continue

        parsed = _parse_json_response(response)
        if not isinstance(parsed, list):
            failed_parse += 1
            logger.debug(
                "Entity extraction non-list response (batch %d): %.200s",
                batch_start,
                response,
            )
            continue

        succeeded += 1
        for i, item in enumerate(batch):
            if i < len(parsed) and isinstance(parsed[i], dict):
                entities = parsed[i]
                item.metadata["entities"] = entities
                # Also populate topics from concepts
                concepts = entities.get("concepts", [])
                if concepts and not item.topics:
                    item.topics = concepts[:5]

    total = failed_empty + failed_parse + succeeded
    if failed_empty or failed_parse:
        logger.warning(
            "Entity extraction: %d/%d batches succeeded, %d empty responses, %d parse failures",
            succeeded,
            total,
            failed_empty,
            failed_parse,
        )

    return items


def classify_items(
    items: list[ContentItem],
    *,
    model: str | None = None,
    timeout: int = 120,
) -> list[ContentItem]:
    """Classify content items by type via LLM.

    Sets item.metadata["classification"] with category, sentiment,
    and relevance.

    Args:
        items: Content items to process (modified in place).
        model: Optional Claude model override.
        timeout: LLM timeout in seconds.

    Returns:
        The same list with classification populated.
    """
    failed_empty = 0
    failed_parse = 0
    succeeded = 0

    for batch_start in range(0, len(items), _BATCH_SIZE):
        batch = items[batch_start : batch_start + _BATCH_SIZE]
        prompt = _build_classification_prompt(batch)
        response = _call_claude_intelligence(
            prompt, model=model or _INTELLIGENCE_MODEL, timeout=timeout
        )

        if not response:
            failed_empty += 1
            continue

        parsed = _parse_json_response(response)
        if not isinstance(parsed, list):
            failed_parse += 1
            logger.debug(
                "Classification non-list response (batch %d): %.200s",
                batch_start,
                response,
            )
            continue

        succeeded += 1
        for i, item in enumerate(batch):
            if i < len(parsed) and isinstance(parsed[i], dict):
                item.metadata["classification"] = parsed[i]

    total = failed_empty + failed_parse + succeeded
    if failed_empty or failed_parse:
        logger.warning(
            "Classification: %d/%d batches succeeded, %d empty responses, %d parse failures",
            succeeded,
            total,
            failed_empty,
            failed_parse,
        )

    return items


def extract_topics(
    items: list[ContentItem],
    existing_topics: list[str] | None = None,
    *,
    model: str | None = None,
    timeout: int = 120,
) -> list[str]:
    """Identify emergent topics across a batch of items.

    Args:
        items: Content items to analyze.
        existing_topics: Previously known topics for continuity.
        model: Optional Claude model override.
        timeout: LLM timeout in seconds.

    Returns:
        New/updated topic list.
    """
    if not items:
        return existing_topics or []

    prompt = _build_topic_prompt(items, existing_topics or [])
    response = _call_claude_intelligence(
        prompt, model=model or _INTELLIGENCE_MODEL, timeout=timeout
    )

    if not response:
        return existing_topics or []

    parsed = _parse_json_response(response)
    if isinstance(parsed, list) and all(isinstance(t, str) for t in parsed):
        return parsed

    return existing_topics or []


# ===========================================================================
# Tagging  (from tagging.py)
# ===========================================================================

# Built-in English stopword list
STOPWORDS: frozenset[str] = frozenset(
    {
        # Articles & determiners
        "the",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "some",
        "any",
        "each",
        "every",
        "all",
        "both",
        "few",
        "more",
        "most",
        "other",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        # Pronouns
        "i",
        "me",
        "my",
        "myself",
        "we",
        "our",
        "ours",
        "ourselves",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "he",
        "him",
        "his",
        "himself",
        "she",
        "her",
        "hers",
        "herself",
        "it",
        "its",
        "itself",
        "they",
        "them",
        "their",
        "theirs",
        "themselves",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        # Prepositions
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "about",
        "against",
        "between",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "to",
        "from",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "into",
        "upon",
        "without",
        "within",
        "along",
        "across",
        "around",
        # Conjunctions
        "and",
        "but",
        "or",
        "if",
        "while",
        "because",
        "as",
        "until",
        "although",
        "since",
        "unless",
        "so",
        "yet",
        "than",
        "when",
        "where",
        "how",
        "why",
        # Verbs (auxiliary / very common)
        "be",
        "is",
        "am",
        "are",
        "was",
        "were",
        "been",
        "being",
        "have",
        "has",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "can",
        "could",
        "need",
        "dare",
        "get",
        "got",
        "gets",
        "getting",
        "make",
        "made",
        "makes",
        "let",
        "say",
        "said",
        "says",
        "go",
        "goes",
        "went",
        "gone",
        "going",
        "come",
        "came",
        "take",
        "took",
        "taken",
        "know",
        "knew",
        "known",
        "see",
        "saw",
        "seen",
        "think",
        "use",
        "used",
        "using",
        "uses",
        "want",
        "also",
        "well",
        "just",
        "now",
        "way",
        "like",
        "look",
        "give",
        "find",
        "tell",
        "work",
        "seem",
        "feel",
        "try",
        "leave",
        "call",
        "keep",
        "put",
        "show",
        "turn",
        "begin",
        "help",
        "run",
        "move",
        "live",
        "set",
        # Adverbs & misc
        "here",
        "there",
        "very",
        "really",
        "still",
        "already",
        "even",
        "much",
        "many",
        "too",
        "quite",
        "rather",
        "enough",
        "ever",
        "never",
        "always",
        "often",
        "sometimes",
        "usually",
        "however",
        "therefore",
        "instead",
        "perhaps",
        "though",
        "actually",
        "especially",
        "basically",
        "simply",
        "almost",
        "else",
        "probably",
        "certainly",
        "indeed",
        "anyway",
        # Generic web/content filler
        "new",
        "first",
        "last",
        "long",
        "great",
        "good",
        "right",
        "old",
        "big",
        "high",
        "small",
        "large",
        "next",
        "early",
        "young",
        "important",
        "different",
        "able",
        "best",
        "better",
        "sure",
        "free",
        "true",
        "real",
        "full",
        "back",
        "part",
        "read",
        "post",
        "blog",
        "article",
        "page",
        "site",
        "link",
        "click",
        "share",
        "comments",
        "comment",
        "reply",
        "subscribe",
        "newsletter",
        "via",
        "one",
        "two",
        "three",
        "don",
        "doesn",
        "didn",
        "won",
        "isn",
        "aren",
        "wasn",
        "weren",
        "hasn",
        "haven",
        "hadn",
        "couldn",
        "shouldn",
        "wouldn",
        "thing",
        "things",
        "people",
        "time",
        "year",
        "years",
        "day",
        "days",
        "lot",
        "end",
        "case",
        "point",
        "number",
        "world",
        "something",
        "nothing",
        "everything",
        "anything",
    }
)

# Characters to strip from word boundaries
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)

# Minimum word length after normalization
_MIN_WORD_LEN = 3

# Title words receive this multiplier to their frequency score
_TITLE_WEIGHT = 3


def _tokenize_tags(text: str) -> list[str]:
    """Split text into lowercase tokens, stripping punctuation.

    Returns only tokens with length >= ``_MIN_WORD_LEN`` that are not
    purely numeric and not in the stopword list.
    """
    # Replace common non-breaking/special whitespace with regular space
    text = re.sub(r"[\u00a0\u2003\u2002\t\r\n]+", " ", text)
    raw_tokens = text.lower().split()

    result: list[str] = []
    for raw in raw_tokens:
        word = raw.translate(_PUNCT_TABLE)
        if len(word) < _MIN_WORD_LEN:
            continue
        if word.isdigit():
            continue
        if word in STOPWORDS:
            continue
        result.append(word)
    return result


def extract_tags(title: str, body: str, max_tags: int = 5) -> list[str]:
    """Extract the most relevant keywords from title and body text.

    Title words are weighted higher than body words.  Tags are returned
    in descending order of relevance (frequency * position weight).

    Args:
        title: The content title.
        body: The content body text.
        max_tags: Maximum number of tags to return.

    Returns:
        A list of lowercase keyword strings, sorted by relevance.
    """
    if not title and not body:
        return []

    title_tokens = _tokenize_tags(title)
    body_tokens = _tokenize_tags(body)

    # Count weighted frequencies
    freq: Counter[str] = Counter()
    for token in title_tokens:
        freq[token] += _TITLE_WEIGHT
    for token in body_tokens:
        freq[token] += 1

    if not freq:
        return []

    # Return the top-N most common keywords
    return [tag for tag, _count in freq.most_common(max_tags)]


def enrich_tags(items: list[ContentItem]) -> list[ContentItem]:
    """Populate tags for content items that have none.

    Iterates over *items* and, for each one whose ``tags`` list is
    empty, calls :func:`extract_tags` on its title and body to fill
    in auto-generated tags.  Items that already have tags are left
    untouched.

    The list is modified in place **and** returned for convenience.

    Args:
        items: Content items to enrich.

    Returns:
        The same list with tags populated where they were missing.
    """
    for item in items:
        if not item.tags:
            item.tags = extract_tags(item.title, item.body)
    return items


# ===========================================================================
# Full-text extraction  (from fulltext.py)
# ===========================================================================

_USER_AGENT = "Distill/1.0 (+https://github.com/distill; content pipeline)"

# Delay between consecutive HTTP requests (seconds)
_REQUEST_DELAY = 0.5

# Try to import trafilatura at module level so it can be mocked in tests.
try:
    import trafilatura as _trafilatura
except ImportError:
    _trafilatura: Any = None  # type: ignore[no-redef]


def _trafilatura_available() -> bool:
    """Check whether trafilatura is installed."""
    return _trafilatura is not None


def fetch_full_text(url: str, timeout: int = 15) -> FullTextResult:
    """Fetch a URL and extract its article text and metadata.

    Uses ``urllib.request`` for HTTP fetching and ``trafilatura`` for
    content extraction. Returns a :class:`FullTextResult` that is always
    safe to inspect (``success=False`` on any error).

    Args:
        url: The article URL to fetch.
        timeout: HTTP request timeout in seconds.

    Returns:
        Extraction result with body, author, title, and word count.
    """
    if not url:
        return FullTextResult(error="Empty URL")

    if not _trafilatura_available():
        return FullTextResult(error="trafilatura is not installed")

    try:
        request = Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            html = response.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError) as exc:
        logger.debug("Failed to fetch %s: %s", url, exc)
        return FullTextResult(error=f"Fetch failed: {exc}")
    except Exception as exc:
        logger.debug("Unexpected error fetching %s: %s", url, exc)
        return FullTextResult(error=f"Fetch failed: {exc}")

    try:
        extracted = _trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
    except Exception as exc:
        logger.debug("Extraction failed for %s: %s", url, exc)
        return FullTextResult(error=f"Extraction failed: {exc}")

    if not extracted:
        return FullTextResult(error="No content extracted")

    # Extract metadata separately
    metadata = _trafilatura.extract_metadata(html)
    author = ""
    title = ""
    if metadata:
        author = metadata.author or ""
        title = metadata.title or ""

    word_count = len(extracted.split())
    return FullTextResult(
        body=extracted,
        author=author,
        title=title,
        word_count=word_count,
        success=True,
    )


def enrich_items(
    items: list[ContentItem],
    min_word_threshold: int = 100,
    max_concurrent: int = 10,
) -> list[ContentItem]:
    """Enrich content items that have short bodies by fetching full text.

    Items whose ``word_count`` is already >= *min_word_threshold* are
    returned unchanged. For the rest, the original URL is fetched and
    the body (and optionally author) are populated from the extracted
    article.

    A small delay is inserted between HTTP requests to respect rate
    limits.

    Args:
        items: Content items to potentially enrich.
        min_word_threshold: Minimum word count below which full-text
            fetching is attempted.
        max_concurrent: Maximum number of items to enrich in a single
            call (acts as a budget cap, not parallelism).

    Returns:
        The same list of items, with short-body items enriched in place.
    """
    if not _trafilatura_available():
        logger.warning("trafilatura is not installed — skipping full-text enrichment")
        return items

    enriched_count = 0
    for item in items:
        if enriched_count >= max_concurrent:
            logger.info("Reached max enrichment budget (%d); stopping", max_concurrent)
            break

        if item.word_count >= min_word_threshold:
            continue

        if not item.url:
            continue

        # Rate limiting: pause between requests
        if enriched_count > 0:
            time.sleep(_REQUEST_DELAY)

        result = fetch_full_text(item.url)
        if not result.success:
            logger.debug("Could not enrich '%s': %s", item.title or item.url, result.error)
            continue

        item.body = result.body
        item.word_count = result.word_count

        # Populate author from page metadata when item has none
        if not item.author and result.author:
            item.author = result.author

        # Populate title from page metadata when item has none
        if not item.title and result.title:
            item.title = result.title

        enriched_count += 1
        logger.debug("Enriched '%s' — %d words", item.title or item.url, result.word_count)

    if enriched_count:
        logger.info("Enriched %d/%d items with full text", enriched_count, len(items))

    return items


# ===========================================================================
# Archive  (from archive.py)
# ===========================================================================


def archive_items(
    items: list[ContentItem],
    output_dir: Path,
    target_date: date | None = None,
) -> Path:
    """Save raw content items as a daily JSON archive.

    Args:
        items: Content items to archive.
        output_dir: Root output directory.
        target_date: Date for the archive file. Defaults to today.

    Returns:
        Path to the written archive file.
    """
    if target_date is None:
        target_date = date.today()

    archive_dir = output_dir / "intake" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    archive_path = archive_dir / f"{target_date.isoformat()}.json"

    # Serialize items — use Pydantic's dict export for clean JSON
    data = {
        "date": target_date.isoformat(),
        "item_count": len(items),
        "items": [item.model_dump(mode="json") for item in items],
    }

    archive_path.write_text(
        json.dumps(data, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Archived %d items to %s", len(items), archive_path)
    return archive_path


def build_daily_index(
    items: list[ContentItem],
    output_dir: Path,
    target_date: date | None = None,
) -> Path:
    """Build a browseable Obsidian index of all items for the day.

    Creates a markdown file listing every article with title, source,
    author, excerpt, and link — useful for browsing what was ingested.

    Args:
        items: Content items to index.
        output_dir: Root output directory.
        target_date: Date for the index file.

    Returns:
        Path to the written index file.
    """
    if target_date is None:
        target_date = date.today()

    index_dir = output_dir / "intake" / "raw"
    index_dir.mkdir(parents=True, exist_ok=True)

    index_path = index_dir / f"raw-{target_date.isoformat()}.md"

    # Group items by site
    by_site: dict[str, list[ContentItem]] = {}
    for item in items:
        key = item.site_name or item.source.value
        by_site.setdefault(key, []).append(item)

    # Sort sites by item count descending
    sorted_sites = sorted(by_site.items(), key=lambda kv: len(kv[1]), reverse=True)

    lines: list[str] = [
        "---",
        f"date: {target_date.isoformat()}",
        "type: intake-raw-index",
        f"items: {len(items)}",
        f"sources: {len(sorted_sites)}",
        "---",
        f"# Raw Feed Items — {target_date.strftime('%B %d, %Y')}",
        "",
        f"**{len(items)} items** from **{len(sorted_sites)} sources**",
        "",
    ]

    for site_name, site_items in sorted_sites:
        lines.append(f"## {site_name} ({len(site_items)})")
        lines.append("")

        for item in site_items:
            title = item.title or "(untitled)"
            if item.url:
                lines.append(f"### [{title}]({item.url})")
            else:
                lines.append(f"### {title}")

            meta: list[str] = []
            if item.author:
                meta.append(f"by {item.author}")
            if item.published_at:
                meta.append(item.published_at.strftime("%Y-%m-%d %H:%M"))
            if item.word_count:
                meta.append(f"{item.word_count} words")
            if meta:
                lines.append(f"*{' | '.join(meta)}*")

            if item.tags:
                lines.append(f"Tags: {', '.join(item.tags[:8])}")

            excerpt = item.excerpt or (
                item.body[:300] + "..." if item.body and len(item.body) > 300 else item.body
            )
            if excerpt:
                lines.append("")
                lines.append(f"> {excerpt.strip()[:500]}")

            lines.append("")

    index_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Built raw index with %d items at %s", len(items), index_path)
    return index_path


# ===========================================================================
# Clustering  (from clustering.py)
# ===========================================================================

# ── stopwords ────────────────────────────────────────────────────────

_CLUSTER_STOPWORDS: set[str] = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "d",
    "did",
    "didn",
    "do",
    "does",
    "doesn",
    "doing",
    "don",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "get",
    "got",
    "had",
    "has",
    "hasn",
    "have",
    "haven",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "isn",
    "it",
    "its",
    "itself",
    "just",
    "ll",
    "m",
    "me",
    "might",
    "more",
    "most",
    "my",
    "myself",
    "need",
    "no",
    "nor",
    "not",
    "now",
    "o",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "re",
    "s",
    "same",
    "she",
    "should",
    "shouldn",
    "so",
    "some",
    "such",
    "t",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "ve",
    "very",
    "was",
    "wasn",
    "we",
    "were",
    "weren",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "won",
    "would",
    "wouldn",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "also",
    "new",
    "one",
    "two",
    "use",
    "used",
    "using",
    "like",
    "make",
    "many",
    "much",
    "well",
    "way",
    "even",
    "still",
    "may",
    "take",
    "come",
    "see",
    "know",
    "want",
    "look",
    "first",
    "go",
    "back",
    "think",
    "say",
    "said",
}

# Characters to strip from tokens (everything that isn't a letter or digit).
_CLUSTER_STRIP_TABLE = str.maketrans("", "", string.punctuation + "\u2019\u2018\u201c\u201d")


# ── tokenisation helpers ─────────────────────────────────────────────


def _tokenize_cluster(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove stopwords."""
    tokens: list[str] = []
    for raw in text.lower().split():
        word = raw.translate(_CLUSTER_STRIP_TABLE)
        if len(word) >= 2 and word not in _CLUSTER_STOPWORDS and not word.isdigit():
            tokens.append(word)
    return tokens


def _item_text(item: ContentItem) -> str:
    """Combine title and excerpt (or body snippet) into a single string."""
    parts: list[str] = []
    if item.title:
        parts.append(item.title)
    if item.excerpt:
        parts.append(item.excerpt)
    elif item.body:
        parts.append(item.body[:500])
    for tag in item.tags:
        parts.append(tag)
    return " ".join(parts)


# ── TF-IDF ───────────────────────────────────────────────────────────


def _build_tfidf(
    docs: list[list[str]],
) -> tuple[list[str], list[dict[str, float]]]:
    """Build TF-IDF vectors for a list of tokenised documents.

    Returns:
        vocab: ordered list of terms.
        vectors: list of dicts mapping term -> tfidf weight.
    """
    n_docs = len(docs)
    if n_docs == 0:
        return [], []

    # Document frequency
    df: Counter[str] = Counter()
    for doc in docs:
        df.update(set(doc))

    vocab = sorted(df.keys())

    # IDF: log(N / df_t)  —  add-one smoothing to avoid division by zero
    idf: dict[str, float] = {}
    for term in vocab:
        idf[term] = math.log((n_docs + 1) / (df[term] + 1)) + 1.0

    vectors: list[dict[str, float]] = []
    for doc in docs:
        tf: Counter[str] = Counter(doc)
        total = len(doc) if doc else 1
        vec: dict[str, float] = {}
        for term, count in tf.items():
            if term in idf:
                vec[term] = (count / total) * idf[term]
        vectors.append(vec)

    return vocab, vectors


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors (dicts)."""
    # Only iterate over the smaller dict for efficiency
    if len(a) > len(b):
        a, b = b, a

    dot = 0.0
    for term, w in a.items():
        if term in b:
            dot += w * b[term]

    if dot == 0.0:
        return 0.0

    norm_a = math.sqrt(sum(w * w for w in a.values()))
    norm_b = math.sqrt(sum(w * w for w in b.values()))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


# ── clustering ───────────────────────────────────────────────────────


def _merge_vectors(va: dict[str, float], vb: dict[str, float]) -> dict[str, float]:
    """Average two sparse vectors (used after merging clusters)."""
    merged: dict[str, float] = dict(va)
    for term, w in vb.items():
        merged[term] = (merged.get(term, 0.0) + w) / 2.0
    # Normalise values that were already in va but not vb
    for term in va:
        if term not in vb:
            merged[term] = va[term] / 2.0
    return merged


def _top_keywords(vector: dict[str, float], n: int = 5) -> list[str]:
    """Return the top-n terms by weight from a sparse vector."""
    return [term for term, _ in sorted(vector.items(), key=lambda kv: kv[1], reverse=True)[:n]]


def _make_label(keywords: list[str]) -> str:
    """Generate a short human-readable label from keywords."""
    if not keywords:
        return "General"
    # Capitalise and join the top 3 keywords
    top = [kw.capitalize() for kw in keywords[:3]]
    return " / ".join(top)


def cluster_items(
    items: list[ContentItem],
    max_clusters: int = 8,
    min_cluster_size: int = 2,
    similarity_threshold: float = 0.15,
) -> list[TopicCluster]:
    """Group content items by topic similarity using TF-IDF.

    Uses a greedy agglomerative approach: repeatedly merge the most
    similar pair of clusters until the similarity drops below the
    threshold or only ``max_clusters`` remain.

    Items that end up in clusters smaller than ``min_cluster_size``
    are collected into an "Other" catch-all cluster.

    Args:
        items: Content items to cluster.
        max_clusters: Maximum number of topic clusters to produce.
        min_cluster_size: Minimum items per cluster (smaller ones
            get merged into "Other").
        similarity_threshold: Minimum cosine similarity for merging.

    Returns:
        List of ``TopicCluster`` instances, sorted by size descending.
    """
    if not items:
        return []

    # 1. Tokenise all items
    docs = [_tokenize_cluster(_item_text(item)) for item in items]

    # 2. Build TF-IDF vectors
    _vocab, vectors = _build_tfidf(docs)

    # 3. Initialise: each item is its own cluster
    #    cluster_indices[i] = list of original indices in that cluster
    cluster_indices: list[list[int]] = [[i] for i in range(len(items))]
    cluster_vectors: list[dict[str, float]] = [dict(v) for v in vectors]

    # 4. Greedy agglomerative merging
    while len(cluster_indices) > 1:
        best_sim = -1.0
        best_i = -1
        best_j = -1

        for i in range(len(cluster_indices)):
            for j in range(i + 1, len(cluster_indices)):
                sim = _cosine_similarity(cluster_vectors[i], cluster_vectors[j])
                if sim > best_sim:
                    best_sim = sim
                    best_i = i
                    best_j = j

        # Stop if the best pair isn't similar enough
        if best_sim < similarity_threshold:
            break

        # Stop if we've reached max_clusters and similarity is marginal
        if len(cluster_indices) <= max_clusters and best_sim < similarity_threshold:
            break

        # Merge j into i
        cluster_indices[best_i].extend(cluster_indices[best_j])
        cluster_vectors[best_i] = _merge_vectors(cluster_vectors[best_i], cluster_vectors[best_j])

        # Remove j
        cluster_indices.pop(best_j)
        cluster_vectors.pop(best_j)

    # 5. Build TopicCluster objects; collect small clusters into "Other"
    result: list[TopicCluster] = []
    other_items: list[ContentItem] = []

    for idx_list, vec in zip(cluster_indices, cluster_vectors, strict=True):
        cluster_items_list = [items[i] for i in idx_list]
        if len(cluster_items_list) < min_cluster_size:
            other_items.extend(cluster_items_list)
        else:
            keywords = _top_keywords(vec)
            result.append(
                TopicCluster(
                    label=_make_label(keywords),
                    items=cluster_items_list,
                    keywords=keywords,
                )
            )

    # Add "Other" cluster if there are leftover items
    if other_items:
        result.append(
            TopicCluster(
                label="Other",
                items=other_items,
                keywords=[],
            )
        )

    # Sort by cluster size descending (Other goes last if tied)
    result.sort(key=lambda c: (-len(c.items), c.label == "Other"))

    return result


# ── rendering ────────────────────────────────────────────────────────


def render_clustered_context(
    clusters: list[TopicCluster],
    max_items_per_cluster: int = 8,
) -> str:
    """Render clusters into a formatted string for the LLM prompt.

    Each cluster is rendered as a section with a heading, followed by
    the items within it.  Items are capped at ``max_items_per_cluster``
    per cluster to keep the prompt within context limits.

    Args:
        clusters: Topic clusters to render.
        max_items_per_cluster: Maximum items to include per cluster.

    Returns:
        Formatted string organised by topic.
    """
    if not clusters:
        return ""

    sections: list[str] = []

    for cluster in clusters:
        lines: list[str] = []
        keyword_str = ", ".join(cluster.keywords) if cluster.keywords else "mixed topics"
        lines.append(f"## {cluster.label}")
        lines.append(f"*Keywords: {keyword_str}*")
        lines.append("")

        display_items = cluster.items[:max_items_per_cluster]
        for item in display_items:
            title = item.title or "(untitled)"
            lines.append(f"### {title}")

            meta_parts: list[str] = []
            if item.site_name:
                meta_parts.append(item.site_name)
            if item.author:
                meta_parts.append(f"by {item.author}")
            if item.url:
                meta_parts.append(item.url)
            if meta_parts:
                lines.append(f"*{' | '.join(meta_parts)}*")

            body = item.excerpt or item.body or ""
            if len(body) > 1500:
                body = body[:1500] + "\n\n[... truncated]"
            if body:
                lines.append("")
                lines.append(body)

            lines.append("")

        remaining = len(cluster.items) - len(display_items)
        if remaining > 0:
            lines.append(f"*... and {remaining} more item(s) in this topic.*")
            lines.append("")

        sections.append("\n".join(lines))

    return "\n---\n\n".join(sections)


# ===========================================================================
# Context assembly  (from context.py)
# ===========================================================================


def _render_item(item: ContentItem) -> str:
    """Render a single item for LLM prompt."""
    header = f"## {item.title}" if item.title else "## (untitled)"
    meta_parts: list[str] = []
    if item.site_name:
        meta_parts.append(item.site_name)
    if item.author:
        meta_parts.append(f"by {item.author}")
    if item.url:
        meta_parts.append(item.url)
    meta_line = " | ".join(meta_parts)

    body = item.body or item.excerpt or "(no content)"
    if len(body) > 2000:
        body = body[:2000] + "\n\n[... truncated]"

    return f"{header}\n*{meta_line}*\n\n{body}"


def _render_session_section(sessions: list[ContentItem]) -> str:
    """Render sessions into a 'What You Built' section."""
    if not sessions:
        return ""

    parts: list[str] = ["# What You Built Today\n"]
    for item in sessions:
        project = item.metadata.get("project", "")
        duration = item.metadata.get("duration_minutes", "")
        tools = item.metadata.get("tools_used", [])
        tool_names = [t["name"] for t in tools if isinstance(t, dict)] if tools else []

        header = f"## {item.title}"
        meta: list[str] = []
        if project:
            meta.append(f"Project: {project}")
        if duration:
            meta.append(f"Duration: {duration}min")
        if tool_names:
            meta.append(f"Tools: {', '.join(tool_names[:5])}")

        body = item.body or "(no narrative)"
        if len(body) > 1500:
            body = body[:1500] + "\n\n[... truncated]"

        meta_line = " | ".join(meta) if meta else ""
        parts.append(f"{header}\n*{meta_line}*\n\n{body}")

    return "\n\n---\n\n".join(parts)


def _render_seed_section(seeds: list[ContentItem]) -> str:
    """Render seeds into a 'What You're Thinking About' section."""
    if not seeds:
        return ""

    parts: list[str] = ["# What You're Thinking About\n"]
    for item in seeds:
        tag_str = f" [{', '.join(item.tags)}]" if item.tags else ""
        parts.append(f"- {item.title}{tag_str}")

    return "\n".join(parts)


def _render_content_section(items: list[ContentItem]) -> str:
    """Render external content into a 'What You Read' section."""
    if not items:
        return ""

    sorted_items = sorted(items, key=lambda i: i.published_at or datetime.min, reverse=True)
    prompt_items = sorted_items[:50]

    parts: list[str] = ["# What You Read Today\n"]
    for item in prompt_items:
        parts.append(_render_item(item))

    return "\n\n---\n\n".join(parts)


def prepare_daily_context(
    items: list[ContentItem],
    target_date: date | None = None,
    clustered_text: str = "",
) -> DailyIntakeContext:
    """Assemble context for daily intake synthesis.

    Args:
        items: Content items to include.
        target_date: The date for this digest. Defaults to today.
        clustered_text: Pre-rendered topic-clustered context from the
            clustering module.  When provided, this replaces the flat
            article list in ``combined_text`` for better thematic
            grouping in the LLM prompt.

    Returns:
        Fully assembled DailyIntakeContext.
    """
    if target_date is None:
        target_date = date.today()

    total_word_count = sum(i.word_count for i in items)

    # Partition items by source type
    session_items: list[ContentItem] = []
    seed_items: list[ContentItem] = []
    content_items: list[ContentItem] = []

    for item in items:
        if item.source == ContentSource.SESSION:
            session_items.append(item)
        elif item.source == ContentSource.SEEDS:
            seed_items.append(item)
        else:
            content_items.append(item)

    # Aggregate projects and tools from session metadata
    projects: list[str] = []
    tools: list[str] = []
    seen_projects: set[str] = set()
    seen_tools: set[str] = set()

    for item in session_items:
        project = item.metadata.get("project")
        if isinstance(project, str) and project and project not in seen_projects:
            projects.append(project)
            seen_projects.add(project)
        item_tools = item.metadata.get("tools_used", [])
        if isinstance(item_tools, list):
            for t in item_tools:
                if isinstance(t, dict):
                    name = t.get("name", "")
                    if name and name not in seen_tools:
                        tools.append(name)
                        seen_tools.add(name)

    # Collect unique sources and sites
    sources: list[str] = []
    sites: list[str] = []
    tags: list[str] = []
    seen_sources: set[str] = set()
    seen_sites: set[str] = set()
    seen_tags: set[str] = set()

    for item in items:
        src = item.source.value
        if src not in seen_sources:
            sources.append(src)
            seen_sources.add(src)
        if item.site_name and item.site_name not in seen_sites:
            sites.append(item.site_name)
            seen_sites.add(item.site_name)
        for tag in item.tags:
            if tag not in seen_tags:
                tags.append(tag)
                seen_tags.add(tag)

    # Build combined text for LLM prompt
    if clustered_text and not session_items and not seed_items:
        # Use topic-clustered context only when no sessions/seeds
        combined_text = clustered_text
    else:
        # Build unified context with sections
        sections: list[str] = []

        if session_items:
            sections.append(_render_session_section(session_items))

        if seed_items:
            sections.append(_render_seed_section(seed_items))

        if content_items:
            if clustered_text:
                sections.append(f"# What You Read Today\n\n{clustered_text}")
            else:
                sections.append(_render_content_section(content_items))

        combined_text = "\n\n" + "\n\n".join(sections) if sections else ""

    return DailyIntakeContext(
        date=target_date,
        items=items,
        total_items=len(items),
        total_word_count=total_word_count,
        sources=sources,
        sites=sites,
        all_tags=tags,
        combined_text=combined_text,
        session_items=session_items,
        seed_items=seed_items,
        content_items=content_items,
        projects_worked_on=projects,
        tools_used_today=tools,
    )


# ===========================================================================
# Synthesizer  (from synthesizer.py)
# ===========================================================================


class IntakeSynthesizer:
    """Synthesizes intake content via Claude CLI."""

    def __init__(self, config: IntakeConfig) -> None:
        self._config = config

    def synthesize_daily(self, context: DailyIntakeContext, memory_context: str = "") -> str:
        """Transform daily intake context into a research digest.

        Uses the unified prompt when sessions or seeds are present,
        falling back to the standard reading-only prompt otherwise.

        Args:
            context: The assembled daily intake context.
            memory_context: Rendered working memory for continuity.

        Returns:
            Synthesized prose as markdown.
        """
        if context.has_sessions or context.has_seeds:
            system_prompt = get_unified_intake_prompt(
                target_word_count=self._config.target_word_count,
                memory_context=memory_context,
                has_sessions=context.has_sessions,
                has_seeds=context.has_seeds,
                user_name=self._config.user_name,
                user_role=self._config.user_role,
            )
        else:
            system_prompt = get_daily_intake_prompt(
                target_word_count=self._config.target_word_count,
                memory_context=memory_context,
                user_name=self._config.user_name,
                user_role=self._config.user_role,
            )
        user_prompt = context.combined_text
        return self._call_claude(system_prompt, user_prompt, f"intake {context.date.isoformat()}")

    def _call_claude(self, system_prompt: str, user_prompt: str, label: str) -> str:
        """Call Claude CLI with prompt piped via stdin.

        Delegates to the shared call_claude() and translates LLMError
        to IntakeSynthesisError.
        """
        try:
            return call_claude(
                system_prompt,
                user_prompt,
                model=self._config.model,
                timeout=self._config.claude_timeout,
                label=label,
            )
        except LLMError as exc:
            raise IntakeSynthesisError(str(exc)) from exc
