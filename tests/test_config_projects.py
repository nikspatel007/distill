"""Tests for project config and converter methods in DistillConfig."""

from distill.config import DistillConfig, PostizSectionConfig, ProjectConfig, load_config


class TestProjectConfig:
    def test_project_config_fields(self):
        p = ProjectConfig(name="Distill", description="Content pipeline")
        assert p.name == "Distill"
        assert p.description == "Content pipeline"
        assert p.url == ""
        assert p.tags == []

    def test_project_config_with_url_and_tags(self):
        p = ProjectConfig(
            name="Distill",
            description="Content pipeline",
            url="https://github.com/user/distill",
            tags=["content", "AI"],
        )
        assert p.url == "https://github.com/user/distill"
        assert p.tags == ["content", "AI"]


class TestDistillConfigProjects:
    def test_default_empty_projects(self):
        config = DistillConfig()
        assert config.projects == []

    def test_render_project_context_empty(self):
        config = DistillConfig()
        assert config.render_project_context() == ""

    def test_render_project_context(self):
        config = DistillConfig(
            projects=[
                ProjectConfig(name="MyApp", description="Web application"),
                ProjectConfig(
                    name="Distill",
                    description="Content pipeline",
                    url="https://github.com/user/distill",
                ),
            ]
        )
        rendered = config.render_project_context()

        assert "## Project Context" in rendered
        assert "**MyApp**: Web application" in rendered
        assert "**Distill**: Content pipeline" in rendered
        assert "URL: https://github.com/user/distill" in rendered

    def test_render_project_context_no_url(self):
        config = DistillConfig(
            projects=[
                ProjectConfig(name="Foo", description="Bar"),
            ]
        )
        rendered = config.render_project_context()
        assert "URL:" not in rendered

    def test_projects_from_toml_data(self):
        data = {
            "projects": [
                {
                    "name": "MyApp",
                    "description": "Web application",
                    "url": "https://github.com/user/myapp",
                    "tags": ["web"],
                },
                {
                    "name": "Distill",
                    "description": "Content pipeline",
                },
            ]
        }
        config = DistillConfig.model_validate(data)

        assert len(config.projects) == 2
        assert config.projects[0].name == "MyApp"
        assert config.projects[0].tags == ["web"]
        assert config.projects[1].url == ""

    def test_load_config_from_toml_file(self, tmp_path):
        toml_content = """\
[[projects]]
name = "TestProject"
description = "A test project"
url = "https://example.com"
tags = ["test"]
"""
        toml_path = tmp_path / ".distill.toml"
        toml_path.write_text(toml_content, encoding="utf-8")

        config = load_config(toml_path)
        assert len(config.projects) == 1
        assert config.projects[0].name == "TestProject"
        assert config.projects[0].description == "A test project"
        assert config.projects[0].url == "https://example.com"
        assert config.projects[0].tags == ["test"]


class TestToPostizConfig:
    def test_to_postiz_config_defaults(self):
        config = DistillConfig()
        postiz = config.to_postiz_config()
        assert postiz.url == ""
        assert postiz.api_key == ""
        assert postiz.is_configured is False
        assert postiz.timezone == "America/Chicago"

    def test_to_postiz_config_from_toml(self):
        config = DistillConfig(
            postiz=PostizSectionConfig(
                url="https://postiz.test/api",
                api_key="test-key",
                schedule_enabled=True,
                timezone="America/Chicago",
                weekly_day=1,
                thematic_days=[0, 1, 2, 3, 4, 5, 6],
            )
        )
        postiz = config.to_postiz_config()
        assert postiz.url == "https://postiz.test/api"
        assert postiz.api_key == "test-key"
        assert postiz.is_configured is True
        assert postiz.schedule_enabled is True
        assert postiz.timezone == "America/Chicago"
        assert postiz.weekly_day == 1
        assert postiz.thematic_days == [0, 1, 2, 3, 4, 5, 6]

    def test_to_postiz_config_resolve_post_type(self):
        config = DistillConfig(
            postiz=PostizSectionConfig(
                url="https://postiz.test/api",
                api_key="key",
                schedule_enabled=True,
            )
        )
        postiz = config.to_postiz_config()
        assert postiz.resolve_post_type() == "schedule"

    def test_to_postiz_config_slack_channel(self):
        config = DistillConfig(
            postiz=PostizSectionConfig(
                url="https://postiz.test/api",
                api_key="key",
                slack_channel="distill",
            )
        )
        postiz = config.to_postiz_config()
        assert postiz.slack_channel == "distill"
