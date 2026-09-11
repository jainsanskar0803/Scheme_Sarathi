"""
Unit tests for the ingestion pipeline.
All tests run against real CSV data — no Supabase connection required.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from scripts.ingest import (
    load_and_clean,
    deduplicate,
    normalise,
    _clean_text,
    _parse_categories,
    _parse_tags,
    _normalise_level,
)

CSV_PATH = Path(__file__).resolve().parents[1] / "updated_data.csv"


# ---------------------------------------------------------------------------
# _clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_strips_zero_width_space(self):
        assert _clean_text("hello​world") == "helloworld"

    def test_strips_zero_width_non_joiner(self):
        assert _clean_text("foo‌bar") == "foobar"

    def test_strips_zero_width_joiner(self):
        assert _clean_text("foo‍bar") == "foobar"

    def test_strips_bom_mid_string(self):
        assert _clean_text("foo﻿bar") == "foobar"

    def test_strips_soft_hyphen(self):
        assert _clean_text("foo­bar") == "foobar"

    def test_collapses_spaces(self):
        assert _clean_text("hello   world") == "hello world"

    def test_strips_leading_trailing(self):
        assert _clean_text("  hello  ") == "hello"

    def test_preserves_angle_brackets(self):
        # These are not HTML — they are literal text in the dataset
        assert "<space>" in _clean_text("Step 1: <space> here")

    def test_empty_string(self):
        assert _clean_text("") == ""


# ---------------------------------------------------------------------------
# _parse_categories
# ---------------------------------------------------------------------------

class TestParseCategories:
    def test_single_category(self):
        assert _parse_categories("Education & Learning") == ["Education & Learning"]

    def test_two_simple_categories(self):
        result = _parse_categories("Education & Learning, Health & Wellness")
        assert result == ["Education & Learning", "Health & Wellness"]

    def test_category_with_internal_comma(self):
        result = _parse_categories("Agriculture,Rural & Environment")
        assert result == ["Agriculture,Rural & Environment"]

    def test_science_it_category_alone(self):
        result = _parse_categories("Science, IT & Communications")
        assert result == ["Science, IT & Communications"]

    def test_science_it_with_other_category(self):
        result = _parse_categories("Business & Entrepreneurship, Science, IT & Communications")
        assert "Science, IT & Communications" in result
        assert "Business & Entrepreneurship" in result
        assert len(result) == 2

    def test_science_it_first(self):
        result = _parse_categories("Science, IT & Communications, Education & Learning")
        assert result[0] == "Science, IT & Communications"
        assert result[1] == "Education & Learning"

    def test_four_categories(self):
        raw = (
            "Education & Learning, Skills & Employment, "
            "Social welfare & Empowerment, Science, IT & Communications, Women and Child"
        )
        result = _parse_categories(raw)
        assert "Science, IT & Communications" in result
        assert len(result) == 5

    def test_banking_category_with_internal_comma(self):
        result = _parse_categories("Banking,Financial Services and Insurance")
        assert result == ["Banking,Financial Services and Insurance"]


# ---------------------------------------------------------------------------
# _parse_tags
# ---------------------------------------------------------------------------

class TestParseTags:
    def test_simple(self):
        assert _parse_tags("SC, Farmer, Subsidy") == ["SC", "Farmer", "Subsidy"]

    def test_strips_whitespace(self):
        assert _parse_tags("  SC ,  Farmer ") == ["SC", "Farmer"]

    def test_empty_string(self):
        assert _parse_tags("") == []

    def test_single_tag(self):
        assert _parse_tags("Widow") == ["Widow"]


# ---------------------------------------------------------------------------
# _normalise_level
# ---------------------------------------------------------------------------

class TestNormaliseLevel:
    def test_state(self):
        assert _normalise_level("State") == "state"

    def test_central(self):
        assert _normalise_level("Central") == "central"

    def test_already_lower(self):
        assert _normalise_level("state") == "state"


# ---------------------------------------------------------------------------
# Integration: full pipeline on real CSV (no Supabase)
# ---------------------------------------------------------------------------

class TestPipelineOnRealCSV:
    @pytest.fixture(scope="class")
    @classmethod
    def raw_rows(cls):
        return load_and_clean(CSV_PATH)

    @pytest.fixture(scope="class")
    @classmethod
    def deduped(cls, raw_rows):
        rows, _ = deduplicate(raw_rows)
        return rows

    @pytest.fixture(scope="class")
    @classmethod
    def schemes(cls, deduped):
        return normalise(deduped)

    def test_loads_expected_row_count(self, raw_rows):
        assert len(raw_rows) == 3400

    def test_no_phantom_empty_column(self, raw_rows):
        assert "" not in raw_rows[0]

    def test_deduplicate_removes_known_duplicates(self, raw_rows):
        _, removed = deduplicate(raw_rows)
        # 'eogu' appears 3x (removes 2), 'vcy' appears 2x (removes 1) = 3 removed
        assert removed == 3

    def test_unique_slug_count_after_dedup(self, deduped):
        slugs = [r["slug"] for r in deduped]
        assert len(slugs) == len(set(slugs))

    def test_all_schemes_validated(self, deduped, schemes):
        # Expect very close to 100% pass rate
        assert len(schemes) >= len(deduped) - 5

    def test_level_values_normalised(self, schemes):
        levels = {s.level for s in schemes}
        assert levels == {"central", "state"}

    def test_no_scheme_has_empty_slug(self, schemes):
        assert all(s.slug for s in schemes)

    def test_no_scheme_has_empty_name(self, schemes):
        assert all(s.scheme_name for s in schemes)

    def test_science_it_category_intact(self, schemes):
        sci = [s for s in schemes if "Science, IT & Communications" in s.scheme_categories]
        assert len(sci) > 0

    def test_categories_are_lists(self, schemes):
        assert all(isinstance(s.scheme_categories, list) for s in schemes)
        assert all(len(s.scheme_categories) >= 1 for s in schemes)

    def test_tags_are_lists(self, schemes):
        assert all(isinstance(s.tags, list) for s in schemes)

    def test_no_zero_width_in_cleaned_text(self, schemes):
        import re
        zws = re.compile(r"[​‌‍­﻿]")
        for s in schemes:
            for field in [s.scheme_name, s.details, s.benefits, s.eligibility_text]:
                assert not zws.search(field), f"ZWS found in slug={s.slug}"