"""Tests for PgvectorStore with fully mocked sqlalchemy/pgvector deps.

These tests exercise the PgvectorStore code paths WITHOUT requiring
sqlalchemy or pgvector to be installed. All module-level names are mocked
so the actual method bodies execute (covering lines 172-375 in store.py).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from distill.intake.models import ContentItem, ContentSource, ContentType
from distill.store import EMBEDDING_DIM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    item_id: str = "item-1",
    title: str = "Test Article",
    body: str = "Article body text.",
    source: ContentSource = ContentSource.RSS,
    content_type: ContentType = ContentType.ARTICLE,
    tags: list[str] | None = None,
    topics: list[str] | None = None,
    published_at: datetime | None = None,
    saved_at: datetime | None = None,
    metadata: dict | None = None,
    url: str = "https://example.com/article",
    excerpt: str = "An excerpt.",
    word_count: int = 100,
    author: str = "Author",
    site_name: str = "Example",
    source_id: str = "src-1",
) -> ContentItem:
    kwargs: dict = {
        "id": item_id,
        "url": url,
        "title": title,
        "body": body,
        "excerpt": excerpt,
        "word_count": word_count,
        "author": author,
        "site_name": site_name,
        "source": source,
        "source_id": source_id,
        "content_type": content_type,
        "tags": tags or [],
        "topics": topics or [],
        "published_at": published_at,
        "metadata": metadata or {},
    }
    if saved_at is not None:
        kwargs["saved_at"] = saved_at
    return ContentItem(**kwargs)


def _make_embedding(dim: int = EMBEDDING_DIM, seed: int = 42) -> list[float]:
    import random

    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


def _mock_row(mapping: dict) -> MagicMock:
    """Create a mock database row with a _mapping attribute."""
    row = MagicMock()
    row._mapping = mapping
    return row


def _build_row_mapping(
    item: ContentItem,
    embedding: list[float] | None = None,
    entities: dict | None = None,
    classification: dict | None = None,
    metadata_json: dict | None = None,
) -> dict:
    return {
        "id": item.id,
        "url": item.url,
        "title": item.title,
        "body": item.body,
        "excerpt": item.excerpt,
        "word_count": item.word_count,
        "author": item.author,
        "site_name": item.site_name,
        "source": item.source.value,
        "source_id": item.source_id,
        "content_type": item.content_type.value,
        "tags": item.tags,
        "topics": item.topics,
        "entities": entities or item.metadata.get("entities", {}),
        "classification": classification or item.metadata.get("classification", {}),
        "published_at": item.published_at,
        "saved_at": item.saved_at,
        "metadata_json": metadata_json
        if metadata_json is not None
        else {k: v for k, v in item.metadata.items() if k not in ("entities", "classification")},
        "embedding": embedding or _make_embedding(),
    }


# ---------------------------------------------------------------------------
# Fixture: PgvectorStore with a mock engine, bypassing __init__
# ---------------------------------------------------------------------------

def _create_pgvector_store_bypassing_init():
    """Create a PgvectorStore without calling __init__.

    Since sqlalchemy/pgvector are not installed, we bypass __init__ and
    manually set the attributes that methods rely on (_engine, _table, _metadata).
    """
    from distill.store import PgvectorStore

    s = object.__new__(PgvectorStore)
    s._engine = MagicMock()
    s._table = MagicMock(name="content_items_table")
    s._metadata = MagicMock()
    return s


@pytest.fixture()
def store():
    """PgvectorStore with mocked internals (no real DB deps needed)."""
    return _create_pgvector_store_bypassing_init()


@pytest.fixture()
def mock_sa():
    """Provide a mock for the `sa` (sqlalchemy) module-level name."""
    mock = MagicMock()
    with patch("distill.store.sa", mock):
        yield mock


def _setup_begin(store):
    """Set up store._engine.begin() as a context manager returning a mock conn."""
    mock_conn = MagicMock()
    store._engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    store._engine.begin.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


def _setup_connect(store):
    """Set up store._engine.connect() as a context manager returning a mock conn."""
    mock_conn = MagicMock()
    store._engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    store._engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


# ===========================================================================
# Test: __init__ (lines 172-201)
# ===========================================================================


class TestPgvectorInitMocked:
    def test_init_raises_when_no_db_deps(self):
        """PgvectorStore.__init__ raises RuntimeError when _HAS_DB is False."""
        with patch("distill.store._HAS_DB", False):
            from distill.store import PgvectorStore

            with pytest.raises(RuntimeError, match="Database dependencies not installed"):
                PgvectorStore("postgresql://localhost/testdb")

    def test_init_creates_engine_and_table(self):
        """PgvectorStore.__init__ calls create_engine, MetaData, Table, create_all."""
        import distill.store as store_mod

        mock_engine = MagicMock()
        mock_metadata = MagicMock()
        mock_table = MagicMock()

        with (
            patch.object(store_mod, "_HAS_DB", True),
            patch.object(store_mod, "create_engine", create=True, new=MagicMock(return_value=mock_engine)),
            patch.object(store_mod, "MetaData", create=True, new=MagicMock(return_value=mock_metadata)),
            patch.object(store_mod, "Table", create=True, new=MagicMock(return_value=mock_table)),
            patch.object(store_mod, "Column", create=True, new=MagicMock()),
            patch.object(store_mod, "String", create=True, new=MagicMock()),
            patch.object(store_mod, "Text", create=True, new=MagicMock()),
            patch.object(store_mod, "Integer", create=True, new=MagicMock()),
            patch.object(store_mod, "DateTime", create=True, new=MagicMock()),
            patch.object(store_mod, "ARRAY", create=True, new=MagicMock()),
            patch.object(store_mod, "JSONB", create=True, new=MagicMock()),
            patch.object(store_mod, "Vector", create=True, new=MagicMock()),
        ):
            s = store_mod.PgvectorStore("postgresql://host/db")

        assert s._engine is mock_engine
        mock_metadata.create_all.assert_called_once_with(mock_engine)


# ===========================================================================
# Test: upsert (lines 205-214)
# ===========================================================================


class TestPgvectorUpsertMocked:
    def test_upsert_inserts_new_item(self, store, mock_sa):
        item = _make_item("new-item")
        embedding = _make_embedding(seed=1)

        mock_conn = _setup_begin(store)
        mock_conn.execute.return_value.fetchone.return_value = None  # not found

        store.upsert(item, embedding)

        # Two calls: SELECT check + INSERT
        assert mock_conn.execute.call_count == 2

    def test_upsert_updates_existing_item(self, store, mock_sa):
        item = _make_item("existing-item")
        embedding = _make_embedding(seed=2)

        mock_conn = _setup_begin(store)
        mock_conn.execute.return_value.fetchone.return_value = MagicMock()  # found

        store.upsert(item, embedding)

        # Two calls: SELECT check + UPDATE
        assert mock_conn.execute.call_count == 2


# ===========================================================================
# Test: upsert_many (lines 218-219)
# ===========================================================================


class TestPgvectorUpsertManyMocked:
    def test_upsert_many_delegates_to_upsert(self, store):
        items = [
            (_make_item(f"id-{i}"), _make_embedding(seed=i))
            for i in range(3)
        ]

        with patch.object(store, "upsert") as mock_upsert:
            store.upsert_many(items)
            assert mock_upsert.call_count == 3

    def test_upsert_many_empty(self, store):
        with patch.object(store, "upsert") as mock_upsert:
            store.upsert_many([])
            mock_upsert.assert_not_called()


# ===========================================================================
# Test: get (lines 223-227)
# ===========================================================================


class TestPgvectorGetMocked:
    def test_get_existing(self, store, mock_sa):
        item = _make_item("found-item", title="Found")
        mock_row = _mock_row(_build_row_mapping(item))

        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchone.return_value = mock_row

        result = store.get("found-item")

        assert result is not None
        assert result.id == "found-item"
        assert result.title == "Found"

    def test_get_nonexistent(self, store, mock_sa):
        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchone.return_value = None

        assert store.get("no-such-id") is None


# ===========================================================================
# Test: find_similar (lines 236-246)
# ===========================================================================


class TestPgvectorFindSimilarMocked:
    def test_find_similar_returns_items(self, store, mock_sa):
        item_a = _make_item("a", title="Alpha")
        item_b = _make_item("b", title="Beta")
        rows = [
            _mock_row(_build_row_mapping(item_a)),
            _mock_row(_build_row_mapping(item_b)),
        ]

        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = rows

        results = store.find_similar(_make_embedding(seed=10), k=5)

        assert len(results) == 2
        assert results[0].id == "a"

    def test_find_similar_with_exclude_ids(self, store, mock_sa):
        item_b = _make_item("b", title="Beta")
        rows = [_mock_row(_build_row_mapping(item_b))]

        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = rows

        results = store.find_similar(
            _make_embedding(seed=10), k=5, exclude_ids=["a"]
        )

        assert len(results) == 1
        assert results[0].id == "b"

    def test_find_similar_empty(self, store, mock_sa):
        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = []

        results = store.find_similar(_make_embedding(seed=10), k=3)
        assert results == []


# ===========================================================================
# Test: find_by_entity (lines 251-258)
# ===========================================================================


class TestPgvectorFindByEntityMocked:
    def test_find_by_entity(self, store, mock_sa):
        item = _make_item("e-1", title="Entity Match")
        rows = [_mock_row(_build_row_mapping(item, entities={"tech": ["Python"]}))]

        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = rows

        results = store.find_by_entity("Python")
        assert len(results) == 1
        assert results[0].id == "e-1"

    def test_find_by_entity_no_match(self, store, mock_sa):
        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = []

        results = store.find_by_entity("NonExistent")
        assert results == []


# ===========================================================================
# Test: find_by_date_range (lines 262-268)
# ===========================================================================


class TestPgvectorFindByDateRangeMocked:
    def test_find_by_date_range(self, store, mock_sa):
        pub = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)
        item = _make_item("feb-item", published_at=pub)
        rows = [_mock_row(_build_row_mapping(item))]

        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = rows

        results = store.find_by_date_range(date(2026, 2, 1), date(2026, 2, 28))
        assert len(results) == 1
        assert results[0].id == "feb-item"

    def test_find_by_date_range_no_match(self, store, mock_sa):
        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = []

        results = store.find_by_date_range(date(2025, 1, 1), date(2025, 1, 31))
        assert results == []


# ===========================================================================
# Test: find_by_source (lines 272-276)
# ===========================================================================


class TestPgvectorFindBySourceMocked:
    def test_find_by_source(self, store, mock_sa):
        item = _make_item("rss-1", source=ContentSource.RSS)
        rows = [_mock_row(_build_row_mapping(item))]

        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = rows

        results = store.find_by_source(ContentSource.RSS)
        assert len(results) == 1
        assert results[0].source == ContentSource.RSS

    def test_find_by_source_no_match(self, store, mock_sa):
        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = []

        results = store.find_by_source(ContentSource.GMAIL)
        assert results == []


# ===========================================================================
# Test: find_by_tags (lines 280-284)
# ===========================================================================


class TestPgvectorFindByTagsMocked:
    def test_find_by_tags(self, store, mock_sa):
        item = _make_item("tagged", tags=["python", "AI"])
        rows = [_mock_row(_build_row_mapping(item))]

        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = rows

        results = store.find_by_tags(["python"])
        assert len(results) == 1
        assert results[0].id == "tagged"

    def test_find_by_tags_no_match(self, store, mock_sa):
        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.fetchall.return_value = []

        results = store.find_by_tags(["nope"])
        assert results == []


# ===========================================================================
# Test: count (lines 288-290)
# ===========================================================================


class TestPgvectorCountMocked:
    def test_count(self, store, mock_sa):
        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.scalar.return_value = 42

        assert store.count() == 42

    def test_count_none_returns_zero(self, store, mock_sa):
        mock_conn = _setup_connect(store)
        mock_conn.execute.return_value.scalar.return_value = None

        assert store.count() == 0


# ===========================================================================
# Test: delete (lines 294-296)
# ===========================================================================


class TestPgvectorDeleteMocked:
    def test_delete_existing(self, store):
        mock_conn = _setup_begin(store)
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_conn.execute.return_value = mock_result

        assert store.delete("item-to-delete") is True

    def test_delete_nonexistent(self, store):
        mock_conn = _setup_begin(store)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_conn.execute.return_value = mock_result

        assert store.delete("nonexistent") is False


# ===========================================================================
# Test: _item_to_row (line 299+)
# ===========================================================================


class TestItemToRowMocked:
    def test_basic_conversion(self, store):
        item = _make_item(
            "conv-1",
            title="Conversion",
            source=ContentSource.SESSION,
            tags=["python"],
            topics=["coding"],
            metadata={"extra": "val"},
        )
        embedding = _make_embedding(seed=5)

        row = store._item_to_row(item, embedding)

        assert row["id"] == "conv-1"
        assert row["title"] == "Conversion"
        assert row["source"] == "session"
        assert row["content_type"] == "article"
        assert row["tags"] == ["python"]
        assert row["topics"] == ["coding"]
        assert row["embedding"] is embedding
        assert row["entities"] == {}
        assert row["classification"] == {}
        assert row["metadata_json"] == {"extra": "val"}

    def test_entities_and_classification_extracted(self, store):
        entities = {"technologies": ["Python", "Rust"]}
        classification = {"category": "tech"}
        item = _make_item(
            "conv-2",
            metadata={
                "entities": entities,
                "classification": classification,
                "other": "val",
            },
        )
        embedding = _make_embedding(seed=6)

        row = store._item_to_row(item, embedding)

        assert row["entities"] == entities
        assert row["classification"] == classification
        assert row["metadata_json"] == {"other": "val"}
        assert "entities" not in row["metadata_json"]
        assert "classification" not in row["metadata_json"]


# ===========================================================================
# Test: _row_to_item (lines 326-333)
# ===========================================================================


class TestRowToItemMocked:
    def test_full_conversion(self, store):
        mapping = {
            "id": "row-1",
            "url": "https://example.com",
            "title": "Row Title",
            "body": "Row body",
            "excerpt": "Row excerpt",
            "word_count": 500,
            "author": "Jane",
            "site_name": "Blog",
            "source": "rss",
            "source_id": "rss-123",
            "content_type": "article",
            "tags": ["python"],
            "topics": ["ml"],
            "entities": {"technologies": ["Python"]},
            "classification": {"category": "tech"},
            "published_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
            "saved_at": datetime(2026, 2, 2, tzinfo=timezone.utc),
            "metadata_json": {"extra": "data"},
            "embedding": _make_embedding(),
        }
        row = _mock_row(mapping)

        result = store._row_to_item(row)

        assert result.id == "row-1"
        assert result.url == "https://example.com"
        assert result.title == "Row Title"
        assert result.source == ContentSource.RSS
        assert result.metadata["entities"] == {"technologies": ["Python"]}
        assert result.metadata["classification"] == {"category": "tech"}
        assert result.metadata["extra"] == "data"

    def test_missing_optional_fields(self, store):
        mapping = {
            "id": "row-minimal",
            "source": "gmail",
        }
        row = _mock_row(mapping)

        result = store._row_to_item(row)

        assert result.id == "row-minimal"
        assert result.url == ""
        assert result.title == ""
        assert result.body == ""
        assert result.word_count == 0
        assert result.tags == []
        assert result.topics == []
        assert result.content_type == ContentType.ARTICLE

    def test_none_metadata_json(self, store):
        mapping = {
            "id": "row-none-meta",
            "source": "rss",
            "metadata_json": None,
        }
        row = _mock_row(mapping)

        result = store._row_to_item(row)
        assert result.metadata == {}

    def test_none_tags_topics(self, store):
        mapping = {
            "id": "row-none-lists",
            "source": "rss",
            "tags": None,
            "topics": None,
        }
        row = _mock_row(mapping)

        result = store._row_to_item(row)
        assert result.tags == []
        assert result.topics == []

    def test_none_content_type_defaults_article(self, store):
        mapping = {
            "id": "row-no-type",
            "source": "rss",
            "content_type": None,
        }
        row = _mock_row(mapping)

        result = store._row_to_item(row)
        assert result.content_type == ContentType.ARTICLE

    def test_none_saved_at_uses_now(self, store):
        mapping = {
            "id": "row-no-saved",
            "source": "rss",
            "saved_at": None,
        }
        row = _mock_row(mapping)

        before = datetime.now()
        result = store._row_to_item(row)
        after = datetime.now()

        assert before <= result.saved_at <= after


# ===========================================================================
# Test: create_store (lines 370-375)
# ===========================================================================


class TestCreateStoreMocked:
    def test_pgvector_success_returns_pgvector(self, tmp_path):
        """When _HAS_DB and PgvectorStore succeeds, returns PgvectorStore."""
        mock_store = MagicMock()

        with (
            patch("distill.store._HAS_DB", True),
            patch("distill.store.PgvectorStore", return_value=mock_store),
        ):
            from distill.store import create_store

            result = create_store(
                database_url="postgresql://localhost/testdb",
                fallback_dir=tmp_path,
            )

        assert result is mock_store

    def test_pgvector_failure_falls_back_to_json(self, tmp_path):
        """When PgvectorStore raises, create_store falls back to JsonStore."""
        from distill.store import JsonStore

        with (
            patch("distill.store._HAS_DB", True),
            patch(
                "distill.store.PgvectorStore",
                side_effect=Exception("Connection refused"),
            ),
        ):
            from distill.store import create_store

            result = create_store(
                database_url="postgresql://localhost/nonexistent",
                fallback_dir=tmp_path,
            )

        assert isinstance(result, JsonStore)

    def test_no_url_returns_json_store(self, tmp_path):
        from distill.store import JsonStore, create_store

        result = create_store(database_url=None, fallback_dir=tmp_path)
        assert isinstance(result, JsonStore)

    def test_no_fallback_dir_uses_cwd(self):
        from distill.store import JsonStore, create_store

        result = create_store(database_url=None, fallback_dir=None)
        assert isinstance(result, JsonStore)


# ===========================================================================
# Test: roundtrip _item_to_row -> _row_to_item
# ===========================================================================


class TestRoundtripMocked:
    def test_roundtrip_preserves_data(self, store):
        item = _make_item(
            "rt-1",
            title="Roundtrip Test",
            body="Testing round-trip conversion.",
            source=ContentSource.SUBSTACK,
            content_type=ContentType.NEWSLETTER,
            tags=["testing", "roundtrip"],
            topics=["quality"],
            published_at=datetime(2026, 2, 7, 14, 30, 0, tzinfo=timezone.utc),
            metadata={
                "entities": {"people": ["Alice"]},
                "classification": {"type": "tutorial"},
                "reading_time": 5,
            },
            url="https://sub.example.com/p/test",
            excerpt="A test excerpt",
            word_count=1234,
            author="Tester",
            site_name="Test Blog",
            source_id="sub-rt-1",
        )
        embedding = _make_embedding(seed=99)

        row_dict = store._item_to_row(item, embedding)
        mock_row = _mock_row(row_dict)
        result = store._row_to_item(mock_row)

        assert result.id == item.id
        assert result.url == item.url
        assert result.title == item.title
        assert result.body == item.body
        assert result.source == item.source
        assert result.content_type == item.content_type
        assert result.tags == item.tags
        assert result.topics == item.topics
        assert result.published_at == item.published_at
        assert result.metadata["entities"] == {"people": ["Alice"]}
        assert result.metadata["classification"] == {"type": "tutorial"}
        assert result.metadata["reading_time"] == 5
