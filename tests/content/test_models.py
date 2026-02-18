"""Tests for content domain models."""

from datetime import UTC, date, datetime

from distill.content.models import (
    ChatMessage,
    ContentRecord,
    ContentStatus,
    ContentType,
    ImageRecord,
    PlatformContent,
)


class TestContentStatus:
    def test_enum_values(self):
        assert ContentStatus.DRAFT == "draft"
        assert ContentStatus.REVIEW == "review"
        assert ContentStatus.READY == "ready"
        assert ContentStatus.PUBLISHED == "published"
        assert ContentStatus.ARCHIVED == "archived"

    def test_all_values(self):
        values = {s.value for s in ContentStatus}
        assert values == {"draft", "review", "ready", "published", "archived"}


class TestContentType:
    def test_enum_values(self):
        assert ContentType.WEEKLY == "weekly"
        assert ContentType.THEMATIC == "thematic"
        assert ContentType.READING_LIST == "reading_list"
        assert ContentType.DIGEST == "digest"
        assert ContentType.DAILY_SOCIAL == "daily_social"
        assert ContentType.SEED == "seed"

    def test_all_values(self):
        values = {t.value for t in ContentType}
        assert values == {"weekly", "thematic", "reading_list", "digest", "daily_social", "seed"}


class TestImageRecord:
    def test_creation(self):
        img = ImageRecord(filename="hero.png", role="hero")
        assert img.filename == "hero.png"
        assert img.role == "hero"

    def test_defaults(self):
        img = ImageRecord(filename="hero.png", role="hero")
        assert img.prompt == ""
        assert img.relative_path == ""

    def test_with_all_fields(self):
        img = ImageRecord(
            filename="banner.png",
            role="social",
            prompt="A futuristic dashboard",
            relative_path="images/banner.png",
        )
        assert img.prompt == "A futuristic dashboard"
        assert img.relative_path == "images/banner.png"


class TestPlatformContent:
    def test_creation(self):
        pc = PlatformContent(platform="ghost", content="Hello world")
        assert pc.platform == "ghost"
        assert pc.content == "Hello world"

    def test_defaults(self):
        pc = PlatformContent(platform="ghost", content="Hello")
        assert pc.published is False
        assert pc.published_at is None
        assert pc.external_id == ""

    def test_with_all_fields(self):
        now = datetime.now(tz=UTC)
        pc = PlatformContent(
            platform="twitter",
            content="Thread content",
            published=True,
            published_at=now,
            external_id="tw-12345",
        )
        assert pc.published is True
        assert pc.published_at == now
        assert pc.external_id == "tw-12345"


class TestChatMessage:
    def test_creation(self):
        msg = ChatMessage(role="user", content="Edit the title", timestamp="2026-02-18T10:00:00Z")
        assert msg.role == "user"
        assert msg.content == "Edit the title"
        assert msg.timestamp == "2026-02-18T10:00:00Z"

    def test_assistant_role(self):
        msg = ChatMessage(
            role="assistant",
            content="Done, updated the title.",
            timestamp="2026-02-18T10:00:01Z",
        )
        assert msg.role == "assistant"


class TestContentRecord:
    def test_minimal_creation(self):
        now = datetime.now(tz=UTC)
        record = ContentRecord(
            slug="weekly-2026-w07",
            content_type=ContentType.WEEKLY,
            title="Week 7 Recap",
            body="Content body here",
            created_at=now,
        )
        assert record.slug == "weekly-2026-w07"
        assert record.content_type == ContentType.WEEKLY
        assert record.title == "Week 7 Recap"
        assert record.body == "Content body here"
        assert record.created_at == now

    def test_defaults(self):
        now = datetime.now(tz=UTC)
        record = ContentRecord(
            slug="test",
            content_type=ContentType.DIGEST,
            title="Test",
            body="Body",
            created_at=now,
        )
        assert record.status == ContentStatus.DRAFT
        assert record.source_dates == []
        assert record.tags == []
        assert record.images == []
        assert record.platforms == {}
        assert record.chat_history == []
        assert record.metadata == {}
        assert record.file_path == ""

    def test_with_images(self):
        now = datetime.now(tz=UTC)
        images = [
            ImageRecord(filename="hero.png", role="hero"),
            ImageRecord(filename="inline.png", role="inline", prompt="A chart"),
        ]
        record = ContentRecord(
            slug="thematic-agents",
            content_type=ContentType.THEMATIC,
            title="Multi-Agent Patterns",
            body="Deep dive into agents",
            created_at=now,
            images=images,
        )
        assert len(record.images) == 2
        assert record.images[0].filename == "hero.png"
        assert record.images[1].prompt == "A chart"

    def test_with_source_dates(self):
        now = datetime.now(tz=UTC)
        record = ContentRecord(
            slug="weekly-2026-w07",
            content_type=ContentType.WEEKLY,
            title="Week 7",
            body="Body",
            created_at=now,
            source_dates=[date(2026, 2, 10), date(2026, 2, 11)],
        )
        assert len(record.source_dates) == 2
        assert record.source_dates[0] == date(2026, 2, 10)

    def test_with_platforms(self):
        now = datetime.now(tz=UTC)
        record = ContentRecord(
            slug="test",
            content_type=ContentType.WEEKLY,
            title="Test",
            body="Body",
            created_at=now,
            platforms={
                "ghost": PlatformContent(platform="ghost", content="Ghost version"),
                "twitter": PlatformContent(platform="twitter", content="Tweet thread"),
            },
        )
        assert len(record.platforms) == 2
        assert record.platforms["ghost"].content == "Ghost version"

    def test_with_chat_history(self):
        now = datetime.now(tz=UTC)
        record = ContentRecord(
            slug="test",
            content_type=ContentType.SEED,
            title="Test",
            body="Body",
            created_at=now,
            chat_history=[
                ChatMessage(
                    role="user",
                    content="Make it shorter",
                    timestamp="2026-02-18T10:00:00Z",
                ),
                ChatMessage(
                    role="assistant",
                    content="Done",
                    timestamp="2026-02-18T10:00:01Z",
                ),
            ],
        )
        assert len(record.chat_history) == 2
        assert record.chat_history[0].role == "user"

    def test_with_metadata(self):
        now = datetime.now(tz=UTC)
        record = ContentRecord(
            slug="test",
            content_type=ContentType.DAILY_SOCIAL,
            title="Test",
            body="Body",
            created_at=now,
            metadata={"word_count": 500, "theme": "agents"},
        )
        assert record.metadata["word_count"] == 500
        assert record.metadata["theme"] == "agents"

    def test_serialization_roundtrip(self):
        now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=UTC)
        record = ContentRecord(
            slug="weekly-2026-w07",
            content_type=ContentType.WEEKLY,
            title="Week 7 Recap",
            body="Full body content",
            status=ContentStatus.REVIEW,
            created_at=now,
            source_dates=[date(2026, 2, 10), date(2026, 2, 11)],
            tags=["agents", "llm"],
            images=[ImageRecord(filename="hero.png", role="hero", prompt="Dashboard")],
            platforms={
                "ghost": PlatformContent(
                    platform="ghost",
                    content="Ghost version",
                    published=True,
                    published_at=now,
                    external_id="gh-123",
                ),
            },
            chat_history=[
                ChatMessage(role="user", content="Looks good", timestamp="2026-02-18T12:00:00Z"),
            ],
            metadata={"draft_count": 2},
            file_path="blog/weekly-2026-w07.md",
        )

        data = record.model_dump(mode="json")
        restored = ContentRecord.model_validate(data)

        assert restored.slug == record.slug
        assert restored.content_type == record.content_type
        assert restored.title == record.title
        assert restored.body == record.body
        assert restored.status == record.status
        assert restored.created_at == record.created_at
        assert restored.source_dates == record.source_dates
        assert restored.tags == record.tags
        assert len(restored.images) == 1
        assert restored.images[0].filename == "hero.png"
        assert restored.platforms["ghost"].published is True
        assert restored.platforms["ghost"].external_id == "gh-123"
        assert len(restored.chat_history) == 1
        assert restored.metadata["draft_count"] == 2
        assert restored.file_path == "blog/weekly-2026-w07.md"
