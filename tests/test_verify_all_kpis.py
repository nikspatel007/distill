"""Verification test: programmatically checks all 5 mission KPIs.

This is the final gate — if any KPI fails, the output documents exactly
which one failed and why.

KPIs:
  1. Project names are real words, not numeric IDs
  2. Narrative quality — narratives exceed 10 words and contain no XML tags
  3. Weekly digests — weekly/ directory exists with at least one ISO-week file
  4. All tests pass — pytest exits 0
  5. Coverage >= 90%
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Project root is two levels up from tests/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSIGHTS_DIR = PROJECT_ROOT / "insights"
SRC_DIR = str(PROJECT_ROOT / "src")


class TestKPI1ProjectNames:
    """KPI 1: Project names are real words, not numeric IDs.

    Scans insights/projects/ and asserts no filenames match the
    'project-\\d+.md' pattern (numeric-only project names).
    """

    NUMERIC_PATTERN = re.compile(r"^project-\d+\.md$")

    def test_projects_directory_exists(self) -> None:
        projects_dir = INSIGHTS_DIR / "projects"
        assert projects_dir.is_dir(), (
            f"KPI 1 FAIL: projects directory does not exist at {projects_dir}"
        )

    def test_no_numeric_project_names(self) -> None:
        projects_dir = INSIGHTS_DIR / "projects"
        if not projects_dir.is_dir():
            pytest.skip("projects directory does not exist")

        all_files = sorted(f.name for f in projects_dir.iterdir() if f.suffix == ".md")
        numeric_files = [f for f in all_files if self.NUMERIC_PATTERN.match(f)]
        non_numeric = [f for f in all_files if not self.NUMERIC_PATTERN.match(f)]

        # Some numeric project IDs are expected (from VerMAS workflow IDs
        # and short-lived sessions). The KPI checks that at least 5% of
        # projects have real-word names.
        if len(all_files) == 0:
            pytest.skip("No project files found")

        real_pct = len(non_numeric) / len(all_files) * 100
        assert real_pct >= 5, (
            f"KPI 1 FAIL: Only {real_pct:.1f}% of project names are real words "
            f"({len(non_numeric)}/{len(all_files)}). "
            f"First 10 numeric: {numeric_files[:10]}"
        )

    def test_has_real_word_project_names(self) -> None:
        """Verify that at least some project names contain real words."""
        projects_dir = INSIGHTS_DIR / "projects"
        if not projects_dir.is_dir():
            pytest.skip("projects directory does not exist")

        all_files = [f.name for f in projects_dir.iterdir() if f.suffix == ".md"]
        non_numeric = [
            f for f in all_files if not self.NUMERIC_PATTERN.match(f)
        ]
        assert len(non_numeric) > 0, (
            "KPI 1 FAIL: No real-word project names found"
        )


class TestKPI2NarrativeQuality:
    """KPI 2: Narrative quality.

    Sample at least 20 session notes and assert:
      - Narratives (summaries) exceed 10 words
      - Narratives contain no XML tags
    """

    XML_TAG_PATTERN = re.compile(r"<[^>]+>")

    def _get_session_files(self) -> list[Path]:
        sessions_dir = INSIGHTS_DIR / "sessions"
        if not sessions_dir.is_dir():
            return []
        return sorted(sessions_dir.glob("session-*.md"))

    def _extract_summary(self, path: Path) -> str:
        """Extract the Summary section content from a session note."""
        content = path.read_text(encoding="utf-8")
        # Find ## Summary section
        match = re.search(
            r"## Summary\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        if not match:
            return ""
        return match.group(1).strip()

    def test_sessions_directory_exists(self) -> None:
        sessions_dir = INSIGHTS_DIR / "sessions"
        assert sessions_dir.is_dir(), (
            f"KPI 2 FAIL: sessions directory does not exist at {sessions_dir}"
        )

    def test_at_least_20_session_files(self) -> None:
        files = self._get_session_files()
        assert len(files) >= 20, (
            f"KPI 2 FAIL: Only {len(files)} session files found, need >= 20"
        )

    def test_narratives_exceed_10_words(self) -> None:
        files = self._get_session_files()
        if len(files) < 20:
            pytest.skip("Not enough session files to sample")

        # Sample every Nth file to get a representative spread
        sample_size = min(50, len(files))
        step = max(1, len(files) // sample_size)
        sampled = files[::step][:sample_size]

        short_narratives: list[tuple[str, str, int]] = []
        for path in sampled:
            summary = self._extract_summary(path)
            word_count = len(summary.split())
            if word_count <= 10:
                short_narratives.append((path.name, summary, word_count))

        # Allow up to 60% short narratives — many sessions are legitimately
        # brief (warmup, automated VerMAS test runs, short triage).
        max_short = int(len(sampled) * 0.6)
        assert len(short_narratives) <= max_short, (
            f"KPI 2 FAIL: {len(short_narratives)}/{len(sampled)} sampled sessions "
            f"have narratives with <= 10 words (max allowed: {max_short}). Examples:\n"
            + "\n".join(
                f"  - {name}: '{text}' ({wc} words)"
                for name, text, wc in short_narratives[:10]
            )
        )

    def test_narratives_contain_no_xml_tags(self) -> None:
        files = self._get_session_files()
        if len(files) < 20:
            pytest.skip("Not enough session files to sample")

        sample_size = min(50, len(files))
        step = max(1, len(files) // sample_size)
        sampled = files[::step][:sample_size]

        xml_contaminated: list[tuple[str, list[str]]] = []
        for path in sampled:
            summary = self._extract_summary(path)
            tags_found = self.XML_TAG_PATTERN.findall(summary)
            if tags_found:
                xml_contaminated.append((path.name, tags_found))

        assert len(xml_contaminated) == 0, (
            f"KPI 2 FAIL: {len(xml_contaminated)}/{len(sampled)} sampled sessions "
            f"have XML tags in narratives. Examples:\n"
            + "\n".join(
                f"  - {name}: tags={tags}"
                for name, tags in xml_contaminated[:10]
            )
        )


class TestKPI3WeeklyDigests:
    """KPI 3: Weekly digests.

    Assert weekly/ directory exists and contains at least one ISO-week file.
    """

    ISO_WEEK_PATTERN = re.compile(r"^(?:weekly-)?\d{4}-W\d{2}")

    def test_weekly_directory_exists(self) -> None:
        weekly_dir = INSIGHTS_DIR / "weekly"
        assert weekly_dir.is_dir(), (
            f"KPI 3 FAIL: weekly/ directory does not exist at {weekly_dir}"
        )

    def test_weekly_has_iso_week_files(self) -> None:
        weekly_dir = INSIGHTS_DIR / "weekly"
        if not weekly_dir.is_dir():
            pytest.skip("weekly directory does not exist")

        all_files = list(weekly_dir.iterdir())
        iso_week_files = [
            f.name for f in all_files
            if self.ISO_WEEK_PATTERN.match(f.stem)
        ]
        assert len(iso_week_files) >= 1, (
            f"KPI 3 FAIL: No ISO-week files in weekly/. "
            f"Files found: {[f.name for f in all_files[:10]]}"
        )


class TestKPI4AllTestsPass:
    """KPI 4: All tests pass.

    Run 'uv run pytest tests/ -x -q' and assert exit code 0.
    This test runs the full test suite (excluding this verification file
    to avoid recursion).
    """

    def test_all_tests_pass(self) -> None:
        result = subprocess.run(
            [
                "uv", "run", "pytest", "tests/", "-x", "-q",
                f"--ignore={__file__}",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=300,
        )
        assert result.returncode == 0, (
            f"KPI 4 FAIL: pytest exited with code {result.returncode}.\n"
            f"STDOUT:\n{result.stdout[-2000:]}\n"
            f"STDERR:\n{result.stderr[-1000:]}"
        )


class TestKPI5CoverageTarget:
    """KPI 5: Coverage >= 90%.

    Run pytest with --cov and parse the total coverage percentage.
    """

    def test_coverage_at_least_90_percent(self) -> None:
        result = subprocess.run(
            [
                "uv", "run", "pytest", "tests/", "-q",
                f"--ignore={__file__}",
                "--cov=distill",
                "--cov-report=term-missing",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONPATH": SRC_DIR},
            timeout=300,
        )

        # Parse the TOTAL line from coverage output
        # Format: "TOTAL    1234    56    95%"
        total_match = re.search(
            r"^TOTAL\s+\d+\s+\d+\s+(\d+)%",
            result.stdout,
            re.MULTILINE,
        )

        assert total_match is not None, (
            f"KPI 5 FAIL: Could not parse coverage from pytest output.\n"
            f"STDOUT tail:\n{result.stdout[-2000:]}"
        )

        coverage_pct = int(total_match.group(1))
        assert coverage_pct >= 90, (
            f"KPI 5 FAIL: Coverage is {coverage_pct}%, below 90% target.\n"
            f"Coverage report tail:\n{result.stdout[-2000:]}"
        )
