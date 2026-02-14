"""Tests for project config in DistillConfig."""

from distill.config import DistillConfig, ProjectConfig, load_config


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
