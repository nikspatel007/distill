"""Tests for tests_pass KPI measurer."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from distill.measurers.base import KPIResult
from distill.measurers.tests_pass import TestsPassMeasurer


class TestTestsPassMeasurer:
    def test_kpi_name(self) -> None:
        assert TestsPassMeasurer.KPI_NAME == "tests_pass"

    def test_target_is_100(self) -> None:
        assert TestsPassMeasurer.TARGET == 100.0

    def test_parse_all_passed(self) -> None:
        measurer = TestsPassMeasurer()
        result = measurer._parse_results("459 passed", "", 0)
        assert result.value == 100.0
        assert result.details["passed"] == 459
        assert result.details["failed"] == 0

    def test_parse_some_failed(self) -> None:
        measurer = TestsPassMeasurer()
        result = measurer._parse_results("450 passed, 9 failed, 1 error", "", 1)
        assert result.details["passed"] == 450
        assert result.details["failed"] == 9
        assert result.details["errors"] == 1
        assert result.details["total"] == 460
        expected_value = round(450 / 460 * 100, 1)
        assert result.value == expected_value

    def test_parse_no_output(self) -> None:
        measurer = TestsPassMeasurer()
        result = measurer._parse_results("", "", 1)
        assert result.value == 0.0
        assert result.details["total"] == 0

    def test_parse_errors_only(self) -> None:
        measurer = TestsPassMeasurer()
        result = measurer._parse_results("3 error", "", 2)
        assert result.details["errors"] == 3
        assert result.details["total"] == 3
        assert result.value == 0.0

    @patch("distill.measurers.tests_pass.subprocess.run")
    def test_measure_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="100 passed\n",
            stderr="",
            returncode=0,
        )
        result = TestsPassMeasurer().measure()
        assert isinstance(result, KPIResult)
        assert result.value == 100.0

    @patch("distill.measurers.tests_pass.subprocess.run")
    def test_measure_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)
        result = TestsPassMeasurer().measure()
        assert result.value == 0.0
        assert "timed out" in result.details["error"]

    @patch("distill.measurers.tests_pass.subprocess.run")
    def test_measure_exception(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = OSError("no such file")
        result = TestsPassMeasurer().measure()
        assert result.value == 0.0
        assert "no such file" in result.details["error"]

    def test_custom_project_root(self) -> None:
        from pathlib import Path

        measurer = TestsPassMeasurer(project_root=Path("/tmp/fake"))
        assert measurer.project_root == Path("/tmp/fake")
