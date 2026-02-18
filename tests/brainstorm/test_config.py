"""Tests for BrainstormConfig model and DistillConfig integration."""

from distill.brainstorm.config import BrainstormConfig


def test_default_config():
    cfg = BrainstormConfig()
    assert cfg.pillars == []
    assert cfg.followed_people == []
    assert cfg.manual_links == []
    assert cfg.arxiv_categories == ["cs.AI", "cs.SE", "cs.MA"]
    assert cfg.hacker_news is True
    assert cfg.hn_min_points == 50


def test_is_configured_empty():
    cfg = BrainstormConfig()
    assert cfg.is_configured is False


def test_is_configured_with_pillars():
    cfg = BrainstormConfig(pillars=["Multi-agent systems"])
    assert cfg.is_configured is True


def test_distill_config_has_brainstorm():
    from distill.config import DistillConfig

    dc = DistillConfig()
    assert hasattr(dc, "brainstorm")
    assert isinstance(dc.brainstorm, BrainstormConfig)
