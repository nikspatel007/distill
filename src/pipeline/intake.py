"""Intake pipeline — external content → daily digests."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from distill.errors import PipelineReport
    from distill.integrations.ghost import GhostConfig

from distill.core import _atomic_write

logger = logging.getLogger(__name__)


def generate_images(
    prose: str,
    output_dir: Path,
    date: str,
    generator: Any = None,
) -> tuple[list, dict[int, str]]:
    """Generate images for an intake digest.

    Returns (prompts, paths) where paths maps prompt index to relative image path.
    Returns ([], {}) if not configured or on failure.
    """
    from distill.images import ImageGenerator

    if generator is None:
        generator = ImageGenerator()

    if not generator.is_configured():
        return [], {}

    from distill.intake.images import extract_image_prompts

    prompts = extract_image_prompts(prose)
    if not prompts:
        return [], {}

    images_dir = output_dir / "intake" / "images"
    paths: dict[int, str] = {}

    for idx, prompt in enumerate(prompts):
        suffix = "hero" if prompt.role == "hero" else str(idx)
        filename = f"{date}-{suffix}.png"
        aspect = "16:9" if prompt.role == "hero" else "3:2"

        result = generator.generate(
            prompt.prompt,
            output_path=images_dir / filename,
            aspect_ratio=aspect,
            mood=getattr(prompt, "mood", None),
        )
        if result:
            paths[idx] = f"images/{filename}"

    return prompts, paths


def generate_intake(
    output_dir: Path,
    *,
    feed_urls: list[str] | None = None,
    feeds_file: str | None = None,
    opml_file: str | None = None,
    sources: list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
    model: str | None = None,
    target_word_count: int = 800,
    publishers: list[str] | None = None,
    ghost_config: GhostConfig | None = None,
    browser_history: bool = False,
    substack_blogs: list[str] | None = None,
    twitter_export: str | None = None,
    linkedin_export: str | None = None,
    reddit_user: str | None = None,
    youtube_api_key: str | None = None,
    gmail_credentials: str | None = None,
    include_sessions: bool = False,
    session_dirs: list[str] | None = None,
    global_sessions: bool = False,
    report: PipelineReport | None = None,
) -> list[Path]:
    """Ingest content from configured sources and synthesize a daily digest.

    Args:
        output_dir: Root output directory (contains intake/).
        feed_urls: Explicit list of RSS feed URLs.
        feeds_file: Path to a newline-delimited feeds file.
        opml_file: Path to an OPML file with feed URLs.
        sources: List of source names to ingest (e.g. ["rss"]). None = all configured.
        force: Bypass state check and re-process.
        dry_run: Preview context without calling LLM.
        model: Optional Claude model override.
        target_word_count: Target word count for the digest.
        publishers: List of publisher names. Defaults to ["obsidian"].

    Returns:
        List of written output file paths.
    """
    from distill.intake.config import (
        BrowserIntakeConfig,
        GmailIntakeConfig,
        IntakeConfig,
        LinkedInIntakeConfig,
        RedditIntakeConfig,
        RSSConfig,
        SessionIntakeConfig,
        SubstackIntakeConfig,
        TwitterIntakeConfig,
        YouTubeIntakeConfig,
    )
    from distill.intake.context import prepare_daily_context
    from distill.intake.memory import load_intake_memory, save_intake_memory
    from distill.intake.models import ContentItem, ContentSource
    from distill.intake.parsers import create_parser, get_configured_parsers
    from distill.intake.publishers import create_intake_publisher
    from distill.intake.state import (
        IntakeRecord,
        IntakeState,
        load_intake_state,
        save_intake_state,
    )
    from distill.intake.synthesizer import IntakeSynthesizer

    if publishers is None:
        publishers = ["obsidian"]

    # Build config with all source-specific settings
    # Merge explicit feed_urls with rss_feeds from .distill.toml
    from distill.config import load_config as _load_distill_config

    _distill_cfg = _load_distill_config()
    _all_feeds = list(feed_urls or [])
    for f in _distill_cfg.intake.rss_feeds:
        if f and f not in _all_feeds:
            _all_feeds.append(f)

    rss_config = RSSConfig(
        feeds=_all_feeds,
        feeds_file=feeds_file or "",
        opml_file=opml_file or "",
    )
    browser_config = BrowserIntakeConfig() if browser_history else BrowserIntakeConfig(browsers=[])
    substack_config = SubstackIntakeConfig(blog_urls=substack_blogs or [])
    twitter_config = TwitterIntakeConfig(export_path=twitter_export or "")
    linkedin_config = LinkedInIntakeConfig(export_path=linkedin_export or "")
    reddit_config = RedditIntakeConfig.from_env()
    if reddit_user:
        reddit_config.username = reddit_user
    youtube_config = YouTubeIntakeConfig.from_env()
    if youtube_api_key:
        youtube_config.api_key = youtube_api_key
    gmail_config = GmailIntakeConfig(credentials_file=gmail_credentials or "")
    session_config = SessionIntakeConfig(
        session_dirs=session_dirs or [],
        include_global=global_sessions,
    )
    if not include_sessions:
        # Disable session parsing by clearing sources
        session_config = SessionIntakeConfig(sources=[])

    config = IntakeConfig(
        rss=rss_config,
        browser=browser_config,
        substack=substack_config,
        twitter=twitter_config,
        linkedin=linkedin_config,
        reddit=reddit_config,
        youtube=youtube_config,
        gmail=gmail_config,
        session=session_config,
        model=model,
        target_word_count=target_word_count,
        user_name=_distill_cfg.user.name,
        user_role=_distill_cfg.user.role,
    )

    # Determine which sources to run
    if sources is not None:
        source_list = [ContentSource(s) for s in sources]
    else:
        # Auto-detect all configured sources
        configured = get_configured_parsers(config)
        source_list = [p.source for p in configured] if configured else [ContentSource.RSS]

    # Load state
    state = load_intake_state(output_dir) if not force else IntakeState()

    # Fan-in: collect from all configured sources
    all_items: list[ContentItem] = []
    for source in source_list:
        try:
            parser = create_parser(source, config=config)
        except ValueError:
            logger.info("No parser available for %s, skipping", source.value)
            continue
        if not parser.is_configured:
            logger.info("Skipping %s (not configured)", source.value)
            continue

        # When forcing, use epoch to bypass recency filter entirely
        since = state.last_run if not force else datetime(2000, 1, 1, tzinfo=UTC)
        items = parser.parse(since=since)
        # Filter already-processed items
        new_items = [i for i in items if not state.is_processed(i.id)]
        all_items.extend(new_items)
        logger.info("Got %d new items from %s", len(new_items), source.value)

    if not all_items:
        logger.info("No new content items to process")
        return []

    # Enrich items: full-text extraction for short articles, then auto-tag
    from distill.intake.fulltext import enrich_items as enrich_fulltext
    from distill.intake.tagging import enrich_tags

    enrich_fulltext(all_items, min_word_threshold=100, max_concurrent=20)
    logger.info("Full-text enrichment complete")

    enrich_tags(all_items)
    logger.info("Auto-tagging complete")

    # Intelligence: entity extraction + classification (LLM-based)
    from distill.intake.intelligence import classify_items, extract_entities

    extract_entities(all_items, model=model)
    logger.info("Entity extraction complete")

    classify_items(all_items, model=model)
    logger.info("Classification complete")

    # Embed and store items for similarity search (optional)
    from distill.embeddings import is_available as embeddings_available
    from distill.store import create_store

    if embeddings_available():
        try:
            from distill.embeddings import embed_items as _embed_items

            store = create_store(fallback_dir=output_dir)
            embedded = _embed_items(all_items)
            store.upsert_many(embedded)
            logger.info("Embedded and stored %d items", len(embedded))
        except Exception:
            logger.warning("Content store update failed, continuing", exc_info=True)
    else:
        logger.debug("Embeddings not available, skipping content store")

    # Load seed ideas and merge into items
    from distill.intake.seeds import SeedStore

    seed_store = SeedStore(output_dir)
    seed_items = seed_store.to_content_items()
    if seed_items:
        all_items.extend(seed_items)
        logger.info("Added %d seed ideas to intake", len(seed_items))

    # Archive raw items after enrichment
    from distill.intake.archive import archive_items, build_daily_index

    archive_path = archive_items(all_items, output_dir)
    index_path = build_daily_index(all_items, output_dir)
    logger.info("Archived %d items", len(all_items))

    # Cluster items by topic for better LLM context
    from distill.intake.clustering import cluster_items, render_clustered_context

    clusters = cluster_items(all_items, max_clusters=8, min_cluster_size=2)
    if clusters:
        clustered_text = render_clustered_context(clusters, max_items_per_cluster=8)
        logger.info("Clustered %d items into %d topics", len(all_items), len(clusters))
    else:
        clustered_text = ""

    # Build context
    context = prepare_daily_context(all_items, clustered_text=clustered_text)

    if dry_run:
        print(f"[DRY RUN] Would synthesize intake digest for {context.date}")
        print(f"  Items: {context.total_items}")
        print(f"  Sources: {', '.join(context.sources)}")
        print(f"  Sites: {', '.join(context.sites[:10])}")
        print(f"  Word count: {context.total_word_count}")
        print("---")
        print(context.combined_text[:2000])
        return []

    # Load both legacy and unified memory
    from distill.memory import (
        DailyEntry as UnifiedDailyEntry,
    )
    from distill.memory import (
        load_unified_memory,
        save_unified_memory,
    )
    from distill.trends import detect_trends, render_trends_for_prompt

    memory = load_intake_memory(output_dir)

    unified = load_unified_memory(output_dir)

    # Inject trends
    intake_trends = detect_trends(unified)
    if intake_trends:
        unified.inject_trends(render_trends_for_prompt(intake_trends))

    # Use unified memory for prompt context
    unified_text = unified.render_for_prompt(focus="intake")
    memory_text = unified_text if unified_text else memory.render_for_prompt()

    synthesizer = IntakeSynthesizer(config)
    prose = synthesizer.synthesize_daily(context, memory_context=memory_text)

    # Generate images (optional — no-op if GOOGLE_AI_API_KEY not set)
    from distill.intake.images import insert_images_into_prose

    image_prompts, image_paths = generate_images(prose, output_dir, context.date)
    if image_paths:
        prose = insert_images_into_prose(prose, image_prompts, image_paths)

    # Fan-out: publish to each enabled target
    written: list[Path] = [archive_path, index_path]
    for pub_name in publishers:
        try:
            publisher = create_intake_publisher(
                pub_name, ghost_config=ghost_config, output_dir=output_dir
            )
            content = publisher.format_daily(context, prose)
            out_path = publisher.daily_output_path(output_dir, context.date)
            _atomic_write(out_path, content)
            written.append(out_path)
        except Exception:
            logger.warning("Failed to publish intake to %s", pub_name, exc_info=True)
            if report:
                report.add_error(
                    "intake",
                    str(pub_name),
                    source=pub_name,
                    error_type="publish_error",
                )

    # Mark items as processed and save state
    for item in all_items:
        state.mark_processed(
            IntakeRecord(
                item_id=item.id,
                url=item.url,
                title=item.title,
                source=item.source.value,
            )
        )
    state.last_run = datetime.now(tz=UTC)
    state.prune(keep_days=30)
    save_intake_state(state, output_dir)

    # Update legacy memory
    from distill.intake.memory import DailyIntakeEntry

    memory.add_entry(
        DailyIntakeEntry(
            date=context.date,
            themes=list(context.all_tags[:5]),
            key_items=[i.title for i in all_items[:10] if i.title],
            item_count=len(all_items),
        )
    )
    memory.prune(keep_days=30)
    save_intake_memory(memory, output_dir)

    # Update unified memory
    unified.add_entry(
        UnifiedDailyEntry(
            date=context.date,
            reads=[i.title for i in all_items[:10] if i.title],
            themes=list(context.all_tags[:5]),
        )
    )
    # Track entities from extraction results
    for item in all_items:
        entities_data = item.metadata.get("entities", {})
        if isinstance(entities_data, dict):
            for entity_type, entity_list in entities_data.items():
                if isinstance(entity_list, list):
                    for entity_name in entity_list:
                        if isinstance(entity_name, str):
                            unified.track_entity(
                                entity_name,
                                entity_type,
                                context.date,
                                context=item.title or "",
                            )
    unified.prune(keep_days=30)
    save_unified_memory(unified, output_dir)

    # Mark consumed seeds as used
    for seed_item in seed_items:
        seed_id = seed_item.metadata.get("seed_id")
        if isinstance(seed_id, str):
            seed_store.mark_used(seed_id, f"intake-{context.date.isoformat()}")

    return written
