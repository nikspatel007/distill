"""Blog pipeline — journal entries → blog posts (weekly, thematic, reading-list)."""

from __future__ import annotations

import contextlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from distill.shared.errors import PipelineReport

from distill.core import _atomic_write

logger = logging.getLogger(__name__)


def _extract_title_from_prose(prose: str) -> str:
    """Extract the first markdown heading from prose, or return a fallback."""
    for line in prose.splitlines():
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    return "Untitled"


def _extract_tags_from_prose(prose: str) -> list[str]:
    """Extract tags from YAML-style frontmatter in prose, if present."""
    if not prose.startswith("---"):
        return []
    end = prose.find("---", 3)
    if end == -1:
        return []
    frontmatter = prose[3:end]
    for line in frontmatter.splitlines():
        if line.strip().startswith("tags:"):
            # Handle inline list: tags: [a, b, c]
            rest = line.split(":", 1)[1].strip()
            if rest.startswith("["):
                return [
                    t.strip().strip('"').strip("'")
                    for t in rest.strip("[]").split(",")
                    if t.strip()
                ]
            # Handle YAML list on subsequent lines
            tags: list[str] = []
            idx = frontmatter.index(line) + len(line)
            for fl in frontmatter[idx:].splitlines():
                fl = fl.strip()
                if fl.startswith("- "):
                    tags.append(fl[2:].strip().strip('"').strip("'"))
                elif fl and not fl.startswith("#"):
                    break
            return tags
    return []


def generate_blog_posts(
    output_dir: Path,
    *,
    post_type: str = "all",
    target_week: str | None = None,
    target_theme: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    include_diagrams: bool = True,
    model: str | None = None,
    target_word_count: int = 1200,
    platforms: list[str] | None = None,
    ghost_config: Any | None = None,
    report: PipelineReport | None = None,
    postiz_limit: int | None = None,
    auto_publish: bool = False,
) -> list[Path]:
    """Generate blog posts from existing journal entries.

    Reads journal markdown files and working memory, then synthesizes
    weekly synthesis posts and/or thematic deep-dives.

    Args:
        output_dir: Root output directory (contains journal/ and blog/).
        post_type: "weekly", "thematic", or "all".
        target_week: Specific week like "2026-W06" (weekly only).
        target_theme: Specific theme slug (thematic only).
        force: Bypass state check and regenerate.
        dry_run: Print context without calling LLM.
        include_diagrams: Whether to include Mermaid diagrams.
        model: Optional Claude model override.
        target_word_count: Target word count for posts.
        platforms: List of platform names to publish to. Defaults to ["obsidian"].
        ghost_config: Optional GhostConfig for live Ghost CMS publishing.
        postiz_limit: Max number of posts to push to Postiz per run. None = unlimited.
        auto_publish: If True, publish to Ghost/Postiz during generation (legacy).
            If False (default), skip external API calls — content is saved to
            ContentStore for review and manual publishing via Studio.

    Returns:
        List of written blog post file paths.
    """
    from distill.blog import (
        BlogConfig,
        BlogState,
        BlogSynthesizer,
        JournalReader,
        Platform,
        load_blog_memory,
        load_blog_state,
        save_blog_memory,
        save_blog_state,
    )
    from distill.blog.publishers import create_publisher
    from distill.content import ContentStore
    from distill.journal import load_memory
    from distill.memory import load_unified_memory, save_unified_memory
    from distill.shared.config import load_config
    from distill.shared.editorial import EditorialStore
    from distill.trends import detect_trends, render_trends_for_prompt

    if platforms is None:
        platforms = ["obsidian"]

    # skip_api gates external publishing — content goes to ContentStore instead
    skip_api = not auto_publish

    # Load project context and editorial store
    distill_config = load_config()

    # Load Postiz config from TOML (with env var overlay) once for all publisher calls
    postiz_config = None
    if "postiz" in platforms:
        postiz_config = distill_config.to_postiz_config()
    project_context = distill_config.render_project_context()
    editorial_store = EditorialStore(output_dir)

    config = BlogConfig(
        target_word_count=target_word_count,
        include_diagrams=include_diagrams,
        model=model,
    )
    reader = JournalReader()
    synthesizer = BlogSynthesizer(config)

    # 1. Read all journal entries
    journal_dir = output_dir / "journal"
    entries = reader.read_all(journal_dir)
    if not entries:
        return []

    # 1b. Read intake digests for context enrichment
    intake_dir = output_dir / "intake"
    intake_digests = reader.read_intake_digests(intake_dir)

    # 2. Load working memory, blog state, and blog memory
    memory = load_memory(output_dir)
    state = load_blog_state(output_dir) if not force else BlogState()
    blog_memory = load_blog_memory(output_dir)
    unified = load_unified_memory(output_dir)

    # Inject trends
    trends = detect_trends(unified)
    if trends:
        unified.inject_trends(render_trends_for_prompt(trends))

    # Load knowledge graph context if available
    graph_context = ""
    try:
        from distill.graph.query import GraphQuery
        from distill.graph.store import GraphStore

        graph_store = GraphStore(path=output_dir)
        if graph_store.node_count() > 0:
            gq = GraphQuery(graph_store)
            graph_data = gq.gather_context_data(max_hours=336.0, max_sessions=10)
            if graph_data.get("sessions"):
                from distill.graph.prompts import _format_user_prompt

                graph_context = "\n\n## Knowledge Graph Context\n" + _format_user_prompt(graph_data)

            # Append structural insights for blog context
            from distill.graph.insights import (
                GraphInsights,
                format_insights_for_prompt,
            )

            gi = GraphInsights(graph_store)
            daily = gi.generate_daily_insights(lookback_hours=336.0)
            insights_section = format_insights_for_prompt(daily)
            if insights_section:
                graph_context += "\n\n" + insights_section

            # Persist insights back into the graph (feedback loop)
            gi.persist_insights(daily)
            graph_store.save()
    except Exception:
        pass  # graph is optional

    # Initialize content store (additive — alongside existing state files)
    content_store = ContentStore(output_dir)

    written: list[Path] = []
    # Shared mutable counter for Postiz rate-limiting across all post types
    postiz_counter = [0]  # list so inner functions can mutate

    # 3. Weekly posts
    if post_type in ("weekly", "all"):
        written.extend(
            _generate_weekly_posts(
                entries=entries,
                memory=memory,
                state=state,
                config=config,
                synthesizer=synthesizer,
                output_dir=output_dir,
                target_week=target_week,
                force=force,
                dry_run=dry_run,
                platforms=platforms,
                blog_memory=blog_memory,
                ghost_config=ghost_config,
                postiz_config=postiz_config,
                intake_digests=intake_digests,
                project_context=project_context,
                editorial_store=editorial_store,
                postiz_limit=postiz_limit,
                postiz_counter=postiz_counter,
                graph_context=graph_context,
                content_store=content_store,
                skip_api=skip_api,
            )
        )

    # 4. Thematic posts
    if post_type in ("thematic", "all"):
        written.extend(
            _generate_thematic_posts(
                entries=entries,
                memory=memory,
                state=state,
                config=config,
                synthesizer=synthesizer,
                output_dir=output_dir,
                target_theme=target_theme,
                force=force,
                dry_run=dry_run,
                platforms=platforms,
                blog_memory=blog_memory,
                ghost_config=ghost_config,
                postiz_config=postiz_config,
                intake_digests=intake_digests,
                project_context=project_context,
                editorial_store=editorial_store,
                postiz_limit=postiz_limit,
                postiz_counter=postiz_counter,
                graph_context=graph_context,
                content_store=content_store,
                skip_api=skip_api,
            )
        )

    # 5. Reading list posts
    if post_type in ("reading-list", "all"):
        written.extend(
            _generate_reading_list_posts(
                entries=entries,
                unified=unified,
                state=state,
                config=config,
                synthesizer=synthesizer,
                output_dir=output_dir,
                force=force,
                dry_run=dry_run,
                platforms=platforms,
                blog_memory=blog_memory,
                ghost_config=ghost_config,
                postiz_config=postiz_config,
                postiz_limit=postiz_limit,
                postiz_counter=postiz_counter,
                content_store=content_store,
                skip_api=skip_api,
            )
        )

    # 6. Save state, blog memory, unified memory, and regenerate indexes
    if not dry_run:
        save_blog_state(state, output_dir)
        save_blog_memory(blog_memory, output_dir)
        save_unified_memory(unified, output_dir)
        # Generate index for each file publisher
        for platform_name in platforms:
            try:
                p = Platform(platform_name)
                publisher = create_publisher(
                    p,
                    synthesizer=synthesizer,
                    ghost_config=ghost_config,
                    postiz_config=postiz_config,
                    skip_api=skip_api,
                )
                if not publisher.requires_llm:
                    idx_content = publisher.format_index(output_dir, state)
                    if idx_content:
                        idx_path = publisher.index_path(output_dir)
                        _atomic_write(idx_path, idx_content)
            except (ValueError, Exception):
                pass

    return written


def _generate_blog_images(
    prose: str,
    output_dir: Path,
    slug: str,
) -> Path | None:
    """Generate images for a blog post.

    Returns the hero image path for use as Ghost feature image,
    or None if image generation is not configured or fails.
    """
    try:
        from distill.intake.images import extract_image_prompts
        from distill.shared.images import ImageGenerator

        generator = ImageGenerator()
        if not generator.is_configured():
            return None

        prompts = extract_image_prompts(prose)
        if not prompts:
            return None

        images_dir = output_dir / "blog" / "images"
        paths: dict[int, str] = {}
        hero_path: Path | None = None

        for idx, prompt in enumerate(prompts):
            suffix = "hero" if prompt.role == "hero" else str(idx)
            filename = f"{slug}-{suffix}.png"
            aspect = "16:9" if prompt.role == "hero" else "3:2"

            result = generator.generate(
                prompt.prompt,
                output_path=images_dir / filename,
                aspect_ratio=aspect,
                mood=getattr(prompt, "mood", None),
            )
            if result:
                paths[idx] = f"images/{filename}"
                if prompt.role == "hero":
                    hero_path = result

        return hero_path
    except Exception:
        logger.warning("Blog image generation failed for %s", slug, exc_info=True)
        return None


def _generate_weekly_posts(
    *,
    entries: list[Any],
    memory: Any,
    state: Any,
    config: Any,
    synthesizer: Any,
    output_dir: Path,
    target_week: str | None,
    force: bool,
    dry_run: bool,
    platforms: list[str],
    blog_memory: Any,
    ghost_config: Any | None = None,
    postiz_config: Any | None = None,
    intake_digests: list[Any] | None = None,
    project_context: str = "",
    editorial_store: Any | None = None,
    postiz_limit: int | None = None,
    postiz_counter: list[int] | None = None,
    graph_context: str = "",
    content_store: Any | None = None,
    skip_api: bool = False,
) -> list[Path]:
    """Generate weekly synthesis blog posts."""
    from distill.blog import BlogPostRecord, Platform, clean_diagrams, prepare_weekly_context
    from distill.blog.publishers import create_publisher

    written: list[Path] = []

    # Group entries by ISO week
    weeks: dict[tuple[int, int], list[Any]] = {}
    for entry in entries:
        iso = entry.date.isocalendar()
        key = (iso.year, iso.week)
        weeks.setdefault(key, []).append(entry)

    # Filter to target week if specified
    if target_week:
        parts = target_week.split("-W")
        if len(parts) == 2:
            try:
                tw_year, tw_week = int(parts[0]), int(parts[1])
                weeks = {k: v for k, v in weeks.items() if k == (tw_year, tw_week)}
            except ValueError:
                pass

    for (year, week), week_entries in sorted(weeks.items()):
        if len(week_entries) < 2:
            continue

        slug = f"weekly-{year}-W{week:02d}"
        if not force and state.is_generated(slug):
            continue

        context = prepare_weekly_context(
            week_entries, year, week, memory, intake_digests=intake_digests
        )
        context.project_context = project_context
        if graph_context:
            context.working_memory += graph_context
        if editorial_store is not None:
            context.editorial_notes = editorial_store.render_for_prompt(
                target=f"week:{year}-W{week:02d}"
            )

        if dry_run:
            print(f"[DRY RUN] Would generate: {slug}")
            print(f"  Entries: {len(week_entries)}, Sessions: {context.total_sessions}")
            print(f"  Projects: {', '.join(context.projects)}")
            print("---")
            continue

        memory_text = blog_memory.render_for_prompt()
        prose = synthesizer.synthesize_weekly(context, blog_memory=memory_text)
        if config.include_diagrams:
            prose = clean_diagrams(prose)

        # Generate images for the blog post
        feature_image_path = _generate_blog_images(prose, output_dir, slug)

        # Extract blog memory from canonical prose
        try:
            title = f"Week {year}-W{week:02d}"
            summary = synthesizer.extract_blog_memory(prose, slug, title, "weekly")
            blog_memory.add_post(summary)
        except Exception:
            logger.warning("Blog memory extraction failed for %s", slug)

        # Two-phase publishing: content publishers first, then social
        # Phase 1: File + CMS publishers (captures Ghost URL for social linking)
        ghost_post_url: str | None = None
        ghost_feature_image_url: str | None = None
        out_path: Path | None = None
        for platform_name in platforms:
            if platform_name == "postiz":
                continue  # handled in phase 2
            if not force and blog_memory.is_published_to(slug, platform_name):
                logger.debug("Already published %s to %s, skipping", slug, platform_name)
                continue
            try:
                p = Platform(platform_name)
                publisher = create_publisher(
                    p,
                    synthesizer=synthesizer,
                    ghost_config=ghost_config,
                    postiz_config=postiz_config,
                    skip_api=skip_api,
                )
                kwargs: dict = {}
                if platform_name == "ghost" and feature_image_path:
                    kwargs["feature_image_path"] = feature_image_path
                content = publisher.format_weekly(context, prose, **kwargs)
                out_path = publisher.weekly_output_path(output_dir, year, week)
                _atomic_write(out_path, content)
                written.append(out_path)
                blog_memory.mark_published(slug, platform_name)
                # Capture Ghost URL for social publishers
                if platform_name == "ghost":
                    ghost_post_url = getattr(publisher, "last_post_url", None)
                    ghost_feature_image_url = getattr(publisher, "last_feature_image_url", None)
            except Exception:
                logger.warning("Failed to publish %s to %s", slug, platform_name, exc_info=True)

        # Phase 2: Social publishers (Postiz) — with blog URL + image
        postiz_publisher = None
        if "postiz" in platforms:
            if not force and blog_memory.is_published_to(slug, "postiz"):
                logger.debug("Already published %s to postiz, skipping", slug)
            elif postiz_limit is not None and postiz_counter and postiz_counter[0] >= postiz_limit:
                logger.info("Postiz limit reached (%d), skipping %s", postiz_limit, slug)
            else:
                try:
                    postiz_publisher = create_publisher(
                        Platform("postiz"),
                        synthesizer=synthesizer,
                        postiz_config=postiz_config,
                        skip_api=skip_api,
                    )
                    content = postiz_publisher.format_weekly(
                        context,
                        prose,
                        blog_url=ghost_post_url,
                        feature_image_url=ghost_feature_image_url,
                    )
                    out_path = postiz_publisher.weekly_output_path(output_dir, year, week)
                    _atomic_write(out_path, content)
                    written.append(out_path)
                    blog_memory.mark_published(slug, "postiz")
                    if postiz_counter is not None:
                        postiz_counter[0] += 1
                except Exception:
                    logger.warning("Failed to publish %s to postiz", slug, exc_info=True)

        state.mark_generated(
            BlogPostRecord(
                slug=slug,
                post_type="weekly",
                generated_at=datetime.now(),
                source_dates=[e.date for e in week_entries],
                file_path=str(out_path) if written else "",
            )
        )

        # Upsert to ContentStore (additive, non-blocking)
        if content_store is not None and written:
            try:
                from distill.content import ContentRecord, ContentStatus, ContentType, ImageRecord

                _source_dates = [e.date for e in week_entries]
                _title = _extract_title_from_prose(prose)
                _tags = _extract_tags_from_prose(prose)
                _file_path = str(out_path.relative_to(output_dir)) if out_path else ""
                content_store.upsert(
                    ContentRecord(
                        slug=slug,
                        content_type=ContentType.WEEKLY,
                        title=_title,
                        body=prose,
                        status=ContentStatus.DRAFT,
                        created_at=datetime.now(tz=UTC),
                        source_dates=_source_dates,
                        tags=_tags,
                        file_path=_file_path,
                    )
                )
                # Attach hero image if generated
                if feature_image_path is not None:
                    content_store.add_image(
                        slug,
                        ImageRecord(
                            filename=feature_image_path.name,
                            role="hero",
                            prompt="",
                            relative_path=str(feature_image_path.relative_to(output_dir)),
                        ),
                    )
                # Save per-platform adapted content from Postiz publisher
                if postiz_publisher is not None:
                    from distill.content import PlatformContent

                    for plat, adapted in getattr(
                        postiz_publisher, "last_platform_content", {}
                    ).items():
                        with contextlib.suppress(Exception):
                            content_store.save_platform_content(
                                slug,
                                plat,
                                PlatformContent(platform=plat, content=adapted, published=False),
                            )
            except Exception:
                logger.debug("ContentStore upsert failed for %s", slug, exc_info=True)

    return written


def _generate_thematic_posts(
    *,
    entries: list[Any],
    memory: Any,
    state: Any,
    config: Any,
    synthesizer: Any,
    output_dir: Path,
    target_theme: str | None,
    force: bool,
    dry_run: bool,
    platforms: list[str],
    blog_memory: Any,
    ghost_config: Any | None = None,
    postiz_config: Any | None = None,
    intake_digests: list[Any] | None = None,
    project_context: str = "",
    editorial_store: Any | None = None,
    postiz_limit: int | None = None,
    postiz_counter: list[int] | None = None,
    graph_context: str = "",
    content_store: Any | None = None,
    skip_api: bool = False,
) -> list[Path]:
    """Generate thematic deep-dive blog posts."""
    from distill.blog import (
        THEMES,
        BlogPostRecord,
        Platform,
        clean_diagrams,
        detect_series_candidates,
        gather_evidence,
        get_ready_themes,
        prepare_thematic_context,
        themes_from_seeds,
    )
    from distill.blog.publishers import create_publisher
    from distill.intake import SeedStore
    from distill.memory import load_unified_memory

    written: list[Path] = []

    # Load seed ideas and generate dynamic themes from them
    seed_store = SeedStore(output_dir)
    unused_seeds = seed_store.list_unused()
    seed_themes = themes_from_seeds(unused_seeds)
    # Map seed slug -> seed text for passing as angle
    seed_angles: dict[str, str] = {f"seed-{s.id}": s.text for s in unused_seeds}

    if target_theme:
        # Generate a specific theme (check both static and seed themes)
        all_themes = THEMES + seed_themes
        theme_def = next((t for t in all_themes if t.slug == target_theme), None)
        if theme_def is None:
            return []
        evidence = gather_evidence(theme_def, entries)
        if not evidence:
            return []
        themes_to_generate = [(theme_def, evidence)]
    else:
        # Find all ready themes (static + seed-derived + series)
        themes_to_generate = get_ready_themes(entries, state)

        for seed_theme in seed_themes:
            if state.is_generated(seed_theme.slug):
                continue
            evidence = gather_evidence(seed_theme, entries)
            if len({e.date for e in evidence}) >= seed_theme.min_evidence_days:
                themes_to_generate.append((seed_theme, evidence))

        # Series detection from UnifiedMemory threads/entities
        with contextlib.suppress(Exception):
            unified_mem = load_unified_memory(output_dir)
            series_candidates = detect_series_candidates(entries, unified_mem, state)
            for series_theme in series_candidates:
                evidence = gather_evidence(series_theme, entries)
                if len({e.date for e in evidence}) >= series_theme.min_evidence_days:
                    themes_to_generate.append((series_theme, evidence))

        # Prioritize by evidence strength (unique days desc), cap total
        themes_to_generate.sort(key=lambda te: len({e.date for e in te[1]}), reverse=True)
        max_posts = getattr(config, "max_thematic_posts", 2) if config else 2
        if len(themes_to_generate) > max_posts:
            logger.info(
                "Capping thematic posts: %d candidates -> %d",
                len(themes_to_generate),
                max_posts,
            )
            themes_to_generate = themes_to_generate[:max_posts]

    for theme, evidence in themes_to_generate:
        if not force and state.is_generated(theme.slug):
            continue

        context = prepare_thematic_context(
            theme,
            evidence,
            memory,
            intake_digests=intake_digests,
            seed_angle=seed_angles.get(theme.slug, ""),
        )
        context.project_context = project_context
        if graph_context:
            context.combined_evidence += graph_context
        if editorial_store is not None:
            context.editorial_notes = editorial_store.render_for_prompt(
                target=f"theme:{theme.slug}"
            )

        if dry_run:
            print(f"[DRY RUN] Would generate: {theme.slug}")
            print(f"  Evidence: {len(evidence)} entries")
            print(f"  Date range: {context.date_range[0]} to {context.date_range[1]}")
            print("---")
            continue

        memory_text = blog_memory.render_for_prompt()
        prose = synthesizer.synthesize_thematic(context, blog_memory=memory_text)
        if config.include_diagrams:
            prose = clean_diagrams(prose)

        # Generate images for the blog post
        feature_image_path = _generate_blog_images(prose, output_dir, theme.slug)

        # Extract blog memory
        try:
            summary = synthesizer.extract_blog_memory(prose, theme.slug, theme.title, "thematic")
            blog_memory.add_post(summary)
        except Exception:
            logger.warning("Blog memory extraction failed for %s", theme.slug)

        # Two-phase publishing: content publishers first, then social
        # Phase 1: File + CMS publishers
        ghost_post_url: str | None = None
        ghost_feature_image_url: str | None = None
        out_path: Path | None = None
        for platform_name in platforms:
            if platform_name == "postiz":
                continue  # handled in phase 2
            if not force and blog_memory.is_published_to(theme.slug, platform_name):
                logger.debug("Already published %s to %s, skipping", theme.slug, platform_name)
                continue
            try:
                p = Platform(platform_name)
                publisher = create_publisher(
                    p,
                    synthesizer=synthesizer,
                    ghost_config=ghost_config,
                    postiz_config=postiz_config,
                    skip_api=skip_api,
                )
                kwargs_t: dict = {}
                if platform_name == "ghost" and feature_image_path:
                    kwargs_t["feature_image_path"] = feature_image_path
                content = publisher.format_thematic(context, prose, **kwargs_t)
                out_path = publisher.thematic_output_path(output_dir, theme.slug)
                _atomic_write(out_path, content)
                written.append(out_path)
                blog_memory.mark_published(theme.slug, platform_name)
                if platform_name == "ghost":
                    ghost_post_url = getattr(publisher, "last_post_url", None)
                    ghost_feature_image_url = getattr(publisher, "last_feature_image_url", None)
            except Exception:
                logger.warning(
                    "Failed to publish %s to %s", theme.slug, platform_name, exc_info=True
                )

        # Phase 2: Social publishers (Postiz) — with blog URL + image
        postiz_publisher = None
        if "postiz" in platforms:
            if not force and blog_memory.is_published_to(theme.slug, "postiz"):
                logger.debug("Already published %s to postiz, skipping", theme.slug)
            elif postiz_limit is not None and postiz_counter and postiz_counter[0] >= postiz_limit:
                logger.info("Postiz limit reached (%d), skipping %s", postiz_limit, theme.slug)
            else:
                try:
                    postiz_publisher = create_publisher(
                        Platform("postiz"),
                        synthesizer=synthesizer,
                        postiz_config=postiz_config,
                        skip_api=skip_api,
                    )
                    content = postiz_publisher.format_thematic(
                        context,
                        prose,
                        blog_url=ghost_post_url,
                        feature_image_url=ghost_feature_image_url,
                    )
                    out_path = postiz_publisher.thematic_output_path(output_dir, theme.slug)
                    _atomic_write(out_path, content)
                    written.append(out_path)
                    blog_memory.mark_published(theme.slug, "postiz")
                    if postiz_counter is not None:
                        postiz_counter[0] += 1
                except Exception:
                    logger.warning("Failed to publish %s to postiz", theme.slug, exc_info=True)

        state.mark_generated(
            BlogPostRecord(
                slug=theme.slug,
                post_type="thematic",
                generated_at=datetime.now(),
                source_dates=[e.date for e in evidence],
                file_path=str(out_path) if written else "",
            )
        )

        # Upsert to ContentStore (additive, non-blocking)
        if content_store is not None and written:
            try:
                from distill.content import ContentRecord, ContentStatus, ContentType, ImageRecord

                _source_dates = [e.date for e in evidence]
                _title = _extract_title_from_prose(prose)
                _tags = _extract_tags_from_prose(prose)
                _file_path = str(out_path.relative_to(output_dir)) if out_path else ""
                content_store.upsert(
                    ContentRecord(
                        slug=theme.slug,
                        content_type=ContentType.THEMATIC,
                        title=_title,
                        body=prose,
                        status=ContentStatus.DRAFT,
                        created_at=datetime.now(tz=UTC),
                        source_dates=_source_dates,
                        tags=_tags,
                        file_path=_file_path,
                    )
                )
                # Attach hero image if generated
                if feature_image_path is not None:
                    content_store.add_image(
                        theme.slug,
                        ImageRecord(
                            filename=feature_image_path.name,
                            role="hero",
                            prompt="",
                            relative_path=str(feature_image_path.relative_to(output_dir)),
                        ),
                    )
                # Save per-platform adapted content from Postiz publisher
                if postiz_publisher is not None:
                    from distill.content import PlatformContent

                    for plat, adapted in getattr(
                        postiz_publisher, "last_platform_content", {}
                    ).items():
                        with contextlib.suppress(Exception):
                            content_store.save_platform_content(
                                theme.slug,
                                plat,
                                PlatformContent(platform=plat, content=adapted, published=False),
                            )
            except Exception:
                logger.debug("ContentStore upsert failed for %s", theme.slug, exc_info=True)

        # Mark seed as used if this was a seed-driven theme
        if theme.slug in seed_angles and not dry_run:
            seed_id = theme.slug.removeprefix("seed-")
            seed_store.mark_used(seed_id, f"blog-{theme.slug}")

    return written


def _generate_reading_list_posts(
    *,
    entries: list[Any],
    unified: Any,
    state: Any,
    config: Any,
    synthesizer: Any,
    output_dir: Path,
    force: bool,
    dry_run: bool,
    platforms: list[str],
    blog_memory: Any,
    ghost_config: Any | None = None,
    postiz_config: Any | None = None,
    postiz_limit: int | None = None,
    postiz_counter: list[int] | None = None,
    content_store: Any | None = None,
    skip_api: bool = False,
) -> list[Path]:
    """Generate reading list posts from intake content store."""
    from distill.blog import (
        BlogPostRecord,
        Platform,
        prepare_reading_list_context,
        render_reading_list_prompt,
    )
    from distill.blog.publishers import create_publisher
    from distill.shared.store import create_store

    written: list[Path] = []

    # Group entries by ISO week
    weeks: set[tuple[int, int]] = set()
    for entry in entries:
        iso = entry.date.isocalendar()
        weeks.add((iso.year, iso.week))

    store = create_store(fallback_dir=output_dir)

    for year, week in sorted(weeks):
        slug = f"reading-list-{year}-W{week:02d}"
        if not force and state.is_generated(slug):
            continue

        context = prepare_reading_list_context(output_dir, year, week, unified, store)
        if context is None:
            continue

        if dry_run:
            print(f"[DRY RUN] Would generate: {slug}")
            print(f"  Items: {len(context.items)} / {context.total_items_read} total")
            print("---")
            continue

        # Build prompt and synthesize
        prompt_text = render_reading_list_prompt(context)
        from distill.blog import BlogPostType, get_blog_prompt

        system_prompt = get_blog_prompt(
            BlogPostType.READING_LIST,
            word_count=config.target_word_count,
        )
        prose = synthesizer.synthesize_raw(system_prompt, prompt_text)

        # Publish
        out_path: Path | None = None
        for platform_name in platforms:
            # Dedup: skip if already published to this platform
            if not force and blog_memory.is_published_to(slug, platform_name):
                logger.debug("Already published %s to %s, skipping", slug, platform_name)
                continue

            # Rate-limit Postiz pushes
            if platform_name == "postiz" and postiz_limit is not None:
                current = postiz_counter[0] if postiz_counter else 0
                if current >= postiz_limit:
                    logger.info("Postiz limit reached (%d), skipping %s", postiz_limit, slug)
                    continue

            try:
                p = Platform(platform_name)
                publisher = create_publisher(
                    p,
                    synthesizer=synthesizer,
                    ghost_config=ghost_config,
                    postiz_config=postiz_config,
                    skip_api=skip_api,
                )
                out_path = publisher.weekly_output_path(output_dir, year, week)
                # Use reading-list subdirectory
                out_path = out_path.parent.parent / "reading-list" / out_path.name
                _atomic_write(out_path, prose)
                written.append(out_path)
                blog_memory.mark_published(slug, platform_name)
                if platform_name == "postiz" and postiz_counter is not None:
                    postiz_counter[0] += 1
            except Exception:
                logger.warning("Failed to publish reading list to %s", platform_name, exc_info=True)

        state.mark_generated(
            BlogPostRecord(
                slug=slug,
                post_type="reading-list",
                generated_at=datetime.now(),
                source_dates=[context.week_start],
                file_path=str(written[-1]) if written else "",
            )
        )

        # Upsert to ContentStore (additive, non-blocking)
        if content_store is not None and written:
            try:
                from distill.content import ContentRecord, ContentStatus, ContentType

                _title = _extract_title_from_prose(prose)
                _tags = _extract_tags_from_prose(prose)
                _file_path = str(out_path.relative_to(output_dir)) if out_path else ""
                content_store.upsert(
                    ContentRecord(
                        slug=slug,
                        content_type=ContentType.READING_LIST,
                        title=_title,
                        body=prose,
                        status=ContentStatus.DRAFT,
                        created_at=datetime.now(tz=UTC),
                        source_dates=[context.week_start],
                        tags=_tags,
                        file_path=_file_path,
                    )
                )
            except Exception:
                logger.debug("ContentStore upsert failed for %s", slug, exc_info=True)

    return written
