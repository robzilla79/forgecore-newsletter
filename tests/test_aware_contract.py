"""Tests for the Aware format contract in issue_contract.py.

Run with: python -m pytest tests/test_aware_contract.py -v

Each fixture is in tests/fixtures/. The tests verify:
- valid Aware prose issue passes normalize_issue_text (mocking require_fresh_context)
- issue with ## CTA fails with forbidden header error
- issue with ## Sources fails with forbidden header error
- issue with no URL fails
- issue with old ForgeCore AI footer fails
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def run_contract(text: str) -> str:
    """Run normalize_issue_text with fresh context mocked out."""
    from issue_contract import normalize_issue_text
    fake_path = Path("/tmp/2026-05-20-test.md")
    with patch("issue_contract.require_fresh_context", return_value=("brief", "raw")):
        with patch("issue_contract.list_issue_files", return_value=[]):
            return normalize_issue_text(text, issue_path=fake_path)


class TestAwareValidIssue:
    def test_valid_issue_passes(self):
        text = load_fixture("aware_valid.md")
        result = run_contract(text)
        assert "Aware by Em" in result
        assert result.strip().startswith("#")


class TestForbiddenHeaders:
    def test_cta_header_fails(self):
        text = load_fixture("aware_with_cta_header.md")
        with pytest.raises(ValueError, match="forbidden structural headers"):
            run_contract(text)

    def test_sources_header_fails(self):
        text = load_fixture("aware_with_sources_header.md")
        with pytest.raises(ValueError, match="forbidden structural headers"):
            run_contract(text)


class TestUrlRequirement:
    def test_no_url_fails(self):
        text = load_fixture("aware_no_url.md")
        with pytest.raises(ValueError, match="source URL"):
            run_contract(text)


class TestFooterRequirement:
    def test_wrong_footer_fails(self):
        text = load_fixture("aware_wrong_footer.md")
        with pytest.raises(ValueError, match="ForgeCore"):
            run_contract(text)
