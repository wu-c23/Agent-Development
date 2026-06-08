"""Tests for fastapi_demo.py — pure helper functions and data-processing logic.

Strategy
--------
fastapi_demo.py contains ~60 standalone utility functions alongside FastAPI
endpoints.  The endpoints call `load_records()` which reads from the filesystem,
so they are tested via *mock_server.py* instead (see test_trend_explorer_api.py).

Here we test the **pure / almost-pure functions** only:
  * ID generation        — generate_uid, record_uid
  * Trend analysis       — trend_direction_from_change, heat_score_normalized,
                            tag_stage, calc_change, first_last_values
  * Data processing      — clean_text, to_int, to_float, normalize_tags,
                            normalize_record, unique_values, tail, to_k
  * Tag/period helpers   — tag_group, period_from_item, is_monthly_ticket_record,
                            month_token_from_item, sum_tag_scores
  * Context & dashboard  — build_context, build_hot_tags, build_platform_compare,
                            build_rising_works, build_monthly_coverage,
                            empty_dashboard, build_summary, resolve_genres
  * Response helpers     — envelope, migration_reason, canonical_list_key

No filesystem or network I/O is required.  Functions that would call
``load_records()`` are tested by passing synthetic data directly.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

import pytest

# Import the module once so all tests share the same reference.
# conftest.py already inserts Trend Explorer/trend-api-spec into sys.path.
import fastapi_demo as td


# ===================================================================
# generate_uid & record_uid
# ===================================================================


class TestGenerateUid:
    def test_returns_64_char_hex(self):
        uid = td.generate_uid("qidian:123", "诡秘之主")
        assert isinstance(uid, str)
        assert len(uid) == 64
        int(uid, 16)  # raises ValueError if not hex

    def test_deterministic(self):
        uid1 = td.generate_uid("qidian:123", "诡秘之主")
        uid2 = td.generate_uid("qidian:123", "诡秘之主")
        assert uid1 == uid2

    def test_different_inputs_differ(self):
        uid1 = td.generate_uid("qidian:123", "诡秘之主")
        uid2 = td.generate_uid("qidian:456", "凡人修仙传")
        assert uid1 != uid2

    def test_title_whitespace_is_stripped(self):
        uid1 = td.generate_uid("a", "  hello  ")
        uid2 = td.generate_uid("a", "hello")
        assert uid1 == uid2

    def test_empty_title(self):
        uid = td.generate_uid("a", "")
        assert len(uid) == 64


class TestRecordUid:
    def test_uses_detail_url_as_platform_id(self):
        item = {
            "platform": "qidian",
            "title": "诡秘之主",
            "detailUrl": "https://qidian.com/book/101",
        }
        expected = td.generate_uid("https://qidian.com/book/101", "诡秘之主")
        assert td.record_uid(item) == expected

    def test_falls_back_to_platform_title(self):
        item = {"platform": "qidian", "title": "诡秘之主"}
        expected = td.generate_uid("qidian:诡秘之主", "诡秘之主")
        assert td.record_uid(item) == expected

    def test_defaults_when_missing_fields(self):
        item: dict = {}
        uid = td.record_uid(item)
        assert len(uid) == 64


# ===================================================================
# trend_direction_from_change
# ===================================================================


class TestTrendDirectionFromChange:
    def test_rising_when_change_ge_5(self):
        assert td.trend_direction_from_change(5) == "rising"
        assert td.trend_direction_from_change(100) == "rising"

    def test_declining_when_change_le_neg5(self):
        assert td.trend_direction_from_change(-5) == "declining"
        assert td.trend_direction_from_change(-100) == "declining"

    def test_stable_when_between_neg5_and_5(self):
        assert td.trend_direction_from_change(0) == "stable"
        assert td.trend_direction_from_change(4) == "stable"
        assert td.trend_direction_from_change(-4) == "stable"
        assert td.trend_direction_from_change(4.9) == "stable"
        assert td.trend_direction_from_change(-4.9) == "stable"


# ===================================================================
# heat_score_normalized
# ===================================================================


class TestHeatScoreNormalized:
    def test_normal_cases(self):
        assert td.heat_score_normalized(50, 100) == 0.5
        assert td.heat_score_normalized(0, 100) == 0.0

    def test_clamps_to_1(self):
        assert td.heat_score_normalized(200, 100) == 1.0

    def test_clamps_to_0(self):
        assert td.heat_score_normalized(-10, 100) == 0.0

    def test_zero_max_heat(self):
        assert td.heat_score_normalized(50, 0) == 0.0
        assert td.heat_score_normalized(0, 0) == 0.0

    def test_rounds_to_4_decimals(self):
        result = td.heat_score_normalized(1, 3)
        assert isinstance(result, float)
        assert result == pytest.approx(0.3333, abs=1e-4)

    def test_float_inputs(self):
        assert td.heat_score_normalized(25.0, 100.0) == 0.25
        assert td.heat_score_normalized(33.33, 100.0) == pytest.approx(0.3333, abs=1e-4)


# ===================================================================
# clean_text
# ===================================================================


class TestCleanText:
    def test_trims_whitespace(self):
        assert td.clean_text("  hello  ") == "hello"

    def test_collapses_internal_spaces(self):
        assert td.clean_text("a   b   c") == "a b c"

    def test_none_returns_none(self):
        assert td.clean_text(None) is None

    def test_empty_string_returns_none(self):
        assert td.clean_text("") is None

    def test_blank_string_returns_none(self):
        assert td.clean_text("   ") is None

    def test_preserves_chinese(self):
        assert td.clean_text("  诡秘之主  ") == "诡秘之主"

    def test_non_string_input(self):
        assert td.clean_text(123) == "123"
        assert td.clean_text(0.5) == "0.5"
        assert td.clean_text(True) == "True"


# ===================================================================
# to_int / to_float
# ===================================================================


class TestToInt:
    def test_string_integer(self):
        assert td.to_int("42", 0) == 42

    def test_string_float(self):
        assert td.to_int("3.14", 0) == 3

    def test_none_uses_default(self):
        assert td.to_int(None, -1) == -1

    def test_non_numeric_uses_default(self):
        assert td.to_int("abc", -1) == -1

    def test_whitespace_handling(self):
        assert td.to_int("  99  ", 0) == 99

    def test_negative_string(self):
        assert td.to_int("-7", 0) == -7


class TestToFloat:
    def test_string_float(self):
        assert td.to_float("3.14", 0.0) == 3.14

    def test_string_integer(self):
        assert td.to_float("42", 0.0) == 42.0

    def test_none_uses_default(self):
        assert td.to_float(None, 1.5) == 1.5

    def test_non_numeric_uses_default(self):
        assert td.to_float("abc", 1.5) == 1.5

    def test_whitespace_handling(self):
        assert td.to_float("  2.5  ", 0.0) == 2.5

    def test_scientific_notation(self):
        assert td.to_float("1e-3", 0.0) == 0.001


# ===================================================================
# normalize_tags
# ===================================================================


class TestNormalizeTags:
    def test_adds_category_as_first_tag(self):
        tags = td.normalize_tags(["后宫", "爽文"], "玄幻")
        assert tags[0] == "玄幻"
        assert "后宫" in tags
        assert "爽文" in tags

    def test_deduplicates(self):
        tags = td.normalize_tags(["爽文", "爽文"], "玄幻")
        assert tags == ["玄幻", "爽文"]

    def test_excluded_tags_removed(self):
        tags = td.normalize_tags(["爽文", "VIP", "连载中"], "玄幻")
        assert "VIP" not in tags
        assert "连载中" not in tags
        assert "爽文" in tags

    def test_splits_on_slash(self):
        tags = td.normalize_tags(["热血/战斗", "悬疑"], None)
        assert "热血" in tags
        assert "战斗" in tags
        assert "悬疑" in tags

    def test_splits_on_pipe(self):
        tags = td.normalize_tags(["A|B|C"], None)
        assert "A" in tags
        assert "B" in tags
        assert "C" in tags

    def test_none_values_skipped(self):
        tags = td.normalize_tags(["tag", None], None)
        assert "tag" in tags
        assert len(tags) == 1

    def test_category_none(self):
        tags = td.normalize_tags(["后宫", "爽文"], None)
        assert "后宫" in tags
        assert "爽文" in tags
        assert len(tags) == 2

    def test_empty_input(self):
        tags = td.normalize_tags([], "玄幻")
        assert tags == ["玄幻"]  # category still added

    def test_non_list_value(self):
        tags = td.normalize_tags("后宫/爽文", "玄幻")
        assert "后宫" in tags
        assert "爽文" in tags
        assert "玄幻" in tags


# ===================================================================
# normalize_record
# ===================================================================


class TestNormalizeRecord:
    def test_sets_defaults_for_empty_dict(self):
        item: dict = {}
        td.normalize_record(item)
        assert item["title"] == "未知作品"
        assert item["platform"] == "未知平台"
        assert item["listType"] == "未知榜单"
        assert item["category"] is None
        assert item["summary"] is None
        assert item["author"] is None
        assert item["detailUrl"] is None
        assert item["rank"] == 0
        assert item["rankChange"] == 0
        assert item["heatScore"] == 0.0
        assert item["tags"] == []

    def test_sets_captured_at_to_iso_string(self):
        item: dict = {}
        td.normalize_record(item)
        # Should be ISO format like "2026-06-07T..."
        assert isinstance(item["capturedAt"], str)
        assert "T" in item["capturedAt"]
        assert item["capturedAt"].endswith("Z")

    def test_normalizes_numeric_fields(self):
        item = {
            "title": " 诡秘之主 ",
            "platform": " qidian ",
            "listType": " 月票榜 ",
            "category": " 玄幻 ",
            "rank": "5",
            "rankChange": "-2",
            "heatScore": "9500.5",
            "tags": [" 克苏鲁 ", " 蒸汽朋克 "],
            "capturedAt": "2026-06-01T12:00:00Z",
        }
        td.normalize_record(item)
        assert item["title"] == "诡秘之主"
        assert item["platform"] == "qidian"
        assert item["listType"] == "月票榜"
        assert item["category"] == "玄幻"
        assert item["rank"] == 5
        assert item["rankChange"] == -2
        assert item["heatScore"] == 9500.5
        assert "克苏鲁" in item["tags"]
        assert "蒸汽朋克" in item["tags"]
        assert "玄幻" in item["tags"]  # category added by normalize_tags

    def test_invalid_numeric_falls_back(self):
        item = {"rank": "abc", "rankChange": None, "heatScore": "invalid"}
        td.normalize_record(item)
        assert item["rank"] == 0
        assert item["rankChange"] == 0
        assert item["heatScore"] == 0.0

    def test_preserves_valid_existing_captured_at(self):
        item = {"capturedAt": "2026-05-15T10:30:00Z"}
        td.normalize_record(item)
        assert item["capturedAt"] == "2026-05-15T10:30:00Z"


# ===================================================================
# unique_values
# ===================================================================


class TestUniqueValues:
    def test_deduplicates(self):
        assert td.unique_values(["a", "b", "a", "c"]) == ["a", "b", "c"]

    def test_preserves_order(self):
        assert td.unique_values(["c", "a", "b", "a"]) == ["c", "a", "b"]

    def test_removes_none_and_empty(self):
        assert td.unique_values(["a", None, "", "b"]) == ["a", "b"]

    def test_empty_input(self):
        assert td.unique_values([]) == []


# ===================================================================
# calc_change
# ===================================================================


class TestCalcChange:
    def test_positive_change(self):
        assert td.calc_change(100, 150) == 50.0

    def test_negative_change(self):
        assert td.calc_change(100, 0) == -99.0  # clamped

    def test_no_change(self):
        assert td.calc_change(100, 100) == 0.0

    def test_zero_first_returns_zero(self):
        assert td.calc_change(0, 100) == 0

    def test_clamps_to_99(self):
        assert td.calc_change(1, 1000) == 99.0

    def test_clamps_to_neg99(self):
        assert td.calc_change(100, 0.5) == -99.0

    def test_float_precision(self):
        assert td.calc_change(200, 250) == 25.0
        assert td.calc_change(200, 210) == 5.0
        assert td.calc_change(200, 190) == -5.0


# ===================================================================
# first_last_values
# ===================================================================


class TestFirstLastValues:
    def test_normal_case(self):
        first, last = td.first_last_values([0, 0, 10, 20, 30])
        assert first == 10
        assert last == 30

    def test_all_zero(self):
        assert td.first_last_values([0, 0, 0]) == (0, 0)

    def test_single_non_zero(self):
        assert td.first_last_values([0, 5, 0]) == (5, 5)

    def test_empty_list(self):
        assert td.first_last_values([]) == (0, 0)


# ===================================================================
# tag_group
# ===================================================================


class TestTagGroup:
    def test_题材_category(self):
        assert td.tag_group("玄幻") == "题材"
        assert td.tag_group("仙侠") == "题材"
        assert td.tag_group("都市") == "题材"
        assert td.tag_group("悬疑") == "题材"
        assert td.tag_group("废土") == "题材"
        assert td.tag_group("规则怪谈") == "题材"

    def test_情绪价值_category(self):
        assert td.tag_group("热血") == "情绪价值"
        assert td.tag_group("高燃") == "情绪价值"
        assert td.tag_group("治愈") == "情绪价值"
        assert td.tag_group("爽文") == "情绪价值"

    def test_元素机制_category(self):
        assert td.tag_group("剑道") == "元素机制"
        assert td.tag_group("权谋") == "元素机制"
        assert td.tag_group("副本") == "元素机制"
        assert td.tag_group("系统") == "元素机制"
        assert td.tag_group("金手指") == "元素机制"

    def test_叙事人设_category(self):
        assert td.tag_group("群像") == "叙事人设"
        assert td.tag_group("家族") == "叙事人设"
        assert td.tag_group("宗族") == "叙事人设"
        assert td.tag_group("成长") == "叙事人设"
        assert td.tag_group("少年") == "叙事人设"

    def test_default_to_细标签(self):
        assert td.tag_group("未知标签") == "细标签"
        assert td.tag_group("") == "细标签"


# ===================================================================
# tag_stage
# ===================================================================


class TestTagStage:
    def test_rising_when_change_ge_12(self):
        assert td.tag_stage(12) == "rising"
        assert td.tag_stage(50) == "rising"

    def test_cooling_when_negative(self):
        assert td.tag_stage(-1) == "cooling"
        assert td.tag_stage(-100) == "cooling"

    def test_stable_when_0_to_11(self):
        assert td.tag_stage(0) == "stable"
        assert td.tag_stage(11) == "stable"
        assert td.tag_stage(5) == "stable"


# ===================================================================
# sum_tag_scores
# ===================================================================


class TestSumTagScores:
    def test_sum_scores_without_period(self):
        container = {"克苏鲁": 100.0, "蒸汽朋克": 50.0, "玄幻": 200.0}
        total = td.sum_tag_scores(container, ["克苏鲁", "蒸汽"])
        assert total == 150.0

    def test_sum_scores_with_period(self):
        container = {
            "克苏鲁": {"2026-01": 10.0, "2026-02": 20.0},
            "蒸汽朋克": {"2026-01": 5.0},
        }
        total = td.sum_tag_scores(container, ["克苏鲁", "蒸汽"], "2026-01")
        assert total == 15.0

    def test_empty_container(self):
        assert td.sum_tag_scores({}, ["tag"], None) == 0.0

    def test_no_match(self):
        container = {"a": 10.0, "b": 20.0}
        assert td.sum_tag_scores(container, ["z"], None) == 0.0


# ===================================================================
# period_from_item / is_monthly_ticket_record / month_token_from_item
# ===================================================================


class TestPeriodFromItem:
    def test_month_param_format(self):
        item = {"listType": "月票 month=202605", "sourceUrl": ""}
        key, label = td.period_from_item(item)
        assert key == "2026-05"
        assert label == "05月"

    def test_chinese_date_format(self):
        item = {"listType": "2026年5月月票榜", "sourceUrl": ""}
        key, label = td.period_from_item(item)
        assert key == "2026-05"
        assert label == "05月"

    def test_falls_back_to_captured_at(self):
        item = {"listType": "畅销榜", "sourceUrl": "", "capturedAt": "2026-06-07T12:00:00Z"}
        key, label = td.period_from_item(item)
        assert key == "2026-06"
        assert label == "06月"

    def test_falls_back_to_current(self):
        item = {"listType": "未知榜单", "sourceUrl": ""}
        key, label = td.period_from_item(item)
        assert key == "current"
        assert label == "当前"


class TestIsMonthlyTicketRecord:
    def test_month_param(self):
        item = {"listType": "月票 month=202605", "sourceUrl": ""}
        assert td.is_monthly_ticket_record(item) is True

    def test_monthly_ticket_keyword(self):
        item = {"listType": "monthly-ticket", "sourceUrl": "month=202605"}
        assert td.is_monthly_ticket_record(item) is True

    def test_non_monthly(self):
        item = {"listType": "畅销榜", "sourceUrl": ""}
        assert td.is_monthly_ticket_record(item) is False

    def test_needs_month_token(self):
        """'月票' without a month token returns False."""
        item = {"listType": "月票", "sourceUrl": ""}
        assert td.is_monthly_ticket_record(item) is False


class TestMonthTokenFromItem:
    def test_month_param(self):
        item = {"listType": "月票 month=202605", "sourceUrl": ""}
        assert td.month_token_from_item(item) == "20265"

    def test_chinese_date(self):
        item = {"listType": "2026年5月月票榜", "sourceUrl": ""}
        assert td.month_token_from_item(item) == "20265"

    def test_no_month_returns_none(self):
        item = {"listType": "畅销榜", "sourceUrl": ""}
        assert td.month_token_from_item(item) is None


# ===================================================================
# envelope
# ===================================================================


class TestEnvelope:
    def test_default_message(self):
        result = td.envelope({"key": "value"})
        assert result["code"] == 0
        assert result["message"] == "success"
        assert result["data"]["key"] == "value"

    def test_custom_message(self):
        result = td.envelope({"key": "value"}, "custom msg")
        assert result["message"] == "custom msg"

    def test_timestamp_present(self):
        result = td.envelope({})
        assert "timestamp" in result
        # ISO format check
        assert "T" in result["timestamp"]


# ===================================================================
# tail
# ===================================================================


class TestTail:
    def test_returns_last_n_chars(self):
        assert td.tail("hello world", 5) == "world"

    def test_empty_string(self):
        assert td.tail("") == ""

    def test_default_limit_4000(self):
        long = "a" * 5000
        result = td.tail(long)
        assert len(result) == 4000

    def test_shorter_than_limit(self):
        assert td.tail("hi", 10) == "hi"


# ===================================================================
# to_k
# ===================================================================


class TestToK:
    def test_small_values(self):
        assert td.to_k(500) == 0.5
        assert td.to_k(1200) == 1.2

    def test_large_values_round_to_integer(self):
        assert td.to_k(100_000) == 100
        assert td.to_k(150_000) == 150

    def test_medium_values(self):
        # Between 10k and 100k → 1 decimal
        val = td.to_k(12_345)
        assert val == 12.3  # 12.345 → 12.3

    def test_zero(self):
        assert td.to_k(0) == 0


# ===================================================================
# empty_dashboard
# ===================================================================


class TestEmptyDashboard:
    def test_structure(self):
        result = td.empty_dashboard("2026-06-07T12:00:00Z")
        assert result["generatedAt"] == "2026-06-07T12:00:00Z"
        assert isinstance(result["summary"], str)
        assert result["metrics"] == []
        assert result["hotTags"] == []
        assert result["heatCurve"]["dates"] == []
        assert result["heatCurve"]["series"] == []
        assert result["platformCompare"] == []
        assert result["wordCloud"] == []
        assert result["migration"]["nodes"] == []
        assert result["migration"]["links"] == []
        assert result["migrationTimeline"]["periods"] == []
        assert result["migrationTimeline"]["flows"] == []
        assert result["genreCloudTimeline"]["clouds"] == []
        assert result["risingWorks"] == []

    def test_summary_says_no_data(self):
        result = td.empty_dashboard("now")
        assert "尚未发现可用趋势数据" in result["summary"]


# ===================================================================
# resolve_genres
# ===================================================================


class TestResolveGenres:
    def test_matches_by_category_and_tags(self):
        item = {"category": "玄幻", "tags": ["热血", "高燃"]}
        genres = td.resolve_genres(item)
        assert "传统玄幻" in genres
        assert len(genres) <= 4

    def test_returns_unique_values(self):
        item = {"category": "仙侠", "tags": ["仙侠", "修真"]}
        genres = td.resolve_genres(item)
        assert genres == ["仙侠修真"]

    def test_falls_back_to_category(self):
        # "历史" matches the "权谋博弈" GENRE_RULE keyword "历史",
        # so it does NOT fall back — use a category with no keyword match.
        item = {"category": "军事", "tags": []}
        genres = td.resolve_genres(item)
        assert "军事" in genres


# ===================================================================
# canonical_list_key
# ===================================================================


class TestCanonicalListKey:
    def test_monthly_ticket_returns_monthly_ticket(self):
        item = {"listType": "月票 month=202605", "sourceUrl": "month=202605"}
        assert td.canonical_list_key(item) == "monthly-ticket"

    def test_non_monthly_returns_list_type(self):
        item = {"listType": "推荐榜", "sourceUrl": ""}
        assert td.canonical_list_key(item) == "推荐榜"


# ===================================================================
# migration_reason
# ===================================================================


class TestMigrationReason:
    def test_contains_source_and_target(self):
        reason = td.migration_reason("传统升级流", "反套路群像流")
        assert "传统升级流" in reason
        assert "反套路群像流" in reason
        assert "正向" in reason


# ===================================================================
# build_context with sample records
# ===================================================================


@pytest.fixture
def sample_records():
    """Three sample records spanning two periods for context-building tests."""
    return [
        {
            "title": "诡秘之主",
            "platform": "qidian",
            "listType": "月票 month=202605",
            "sourceUrl": "https://example.com?month=202605",
            "heatScore": 9500.0,
            "rank": 1,
            "rankChange": 2,
            "tags": ["克苏鲁", "蒸汽朋克"],
            "category": "玄幻",
            "author": "爱潜水的乌贼",
            "detailUrl": "https://qidian.com/book/101",
            "capturedAt": "2026-05-15T12:00:00Z",
        },
        {
            "title": "凡人修仙传",
            "platform": "qidian",
            "listType": "月票 month=202605",
            "sourceUrl": "https://example.com?month=202605",
            "heatScore": 8200.0,
            "rank": 3,
            "rankChange": 1,
            "tags": ["修仙", "凡人流"],
            "category": "仙侠",
            "author": "忘语",
            "detailUrl": "https://qidian.com/book/102",
            "capturedAt": "2026-05-15T12:00:00Z",
        },
        {
            "title": "剑来",
            "platform": "zongheng",
            "listType": "月票 month=202604",
            "sourceUrl": "https://example.com?month=202604",
            "heatScore": 7800.0,
            "rank": 5,
            "rankChange": 3,
            "tags": ["仙侠", "剑道", "群像"],
            "category": "仙侠",
            "author": "烽火戏诸侯",
            "detailUrl": "https://zongheng.com/book/201",
            "capturedAt": "2026-04-20T10:00:00Z",
        },
    ]


@pytest.fixture
def context(sample_records):
    """Build a context dict from sample_records for downstream tests."""
    return td.build_context(sample_records, score_mode="raw_heat")


class TestBuildContext:
    def test_keys_present(self, context):
        assert "records" in context
        assert "periods" in context
        assert "tagTotal" in context
        assert "tagPeriod" in context
        assert "tagWorks" in context
        assert "platformTotal" in context
        assert "platformTags" in context
        assert "worksByKey" in context

    def test_periods_sorted(self, context):
        periods = context["periods"]
        keys = [p[0] for p in periods]
        assert keys == sorted(keys)

    def test_tag_total_aggregates(self, context):
        # 克苏鲁 appears in record 0 only, with heatScore 9500
        assert context["tagTotal"]["克苏鲁"] == 9500.0
        # "仙侠" is a tag of record 2 (剑来, heatScore=7800) only.
        # Record 1 (凡人修仙传) has category="仙侠" but tags=["修仙", "凡人流"],
        # so "仙侠" as a tag only gets the 7800 contribution.
        assert context["tagTotal"]["仙侠"] == 7800.0

    def test_platform_total(self, context):
        assert context["platformTotal"]["qidian"] == 9500.0 + 8200.0
        assert context["platformTotal"]["zongheng"] == 7800.0

    def test_tag_period_nested_dict(self, context):
        # 克苏鲁 in 2026-05 with score 9500
        assert context["tagPeriod"]["克苏鲁"]["2026-05"] == 9500.0

    def test_tag_works_contains_max_score(self, context):
        assert context["tagWorks"]["克苏鲁"]["诡秘之主"] == 9500.0

    def test_works_by_key(self, context):
        assert len(context["worksByKey"]) == 3
        assert "https://qidian.com/book/101" in context["worksByKey"]


# ===================================================================
# build_hot_tags
# ===================================================================


class TestBuildHotTags:
    def test_returns_sorted_list(self, context):
        hot_tags = td.build_hot_tags(context)
        assert isinstance(hot_tags, list)
        assert len(hot_tags) > 0

    def test_each_tag_has_required_fields(self, context):
        hot_tags = td.build_hot_tags(context)
        for tag in hot_tags:
            assert "tag" in tag
            assert "heat" in tag
            assert "change" in tag
            assert "group" in tag
            assert "stage" in tag
            assert "relatedWorks" in tag

    def test_sorted_by_heat_descending(self, context):
        hot_tags = td.build_hot_tags(context)
        heats = [t["heat"] for t in hot_tags]
        assert heats == sorted(heats, reverse=True)

    def test_group_is_valid(self, context):
        hot_tags = td.build_hot_tags(context)
        valid_groups = {"题材", "情绪价值", "元素机制", "叙事人设", "细标签"}
        for tag in hot_tags:
            assert tag["group"] in valid_groups

    def test_stage_is_valid(self, context):
        hot_tags = td.build_hot_tags(context)
        for tag in hot_tags:
            assert tag["stage"] in ("rising", "cooling", "stable")


# ===================================================================
# build_platform_compare
# ===================================================================


class TestBuildPlatformCompare:
    def test_returns_list(self, context):
        result = td.build_platform_compare(context)
        assert isinstance(result, list)

    def test_each_platform_has_required_fields(self, context):
        result = td.build_platform_compare(context)
        for entry in result:
            assert "platform" in entry
            assert "heat" in entry
            assert "works" in entry
            assert "topTags" in entry
            assert "status" in entry

    def test_sorted_by_heat_descending(self, context):
        result = td.build_platform_compare(context)
        heats = [p["heat"] for p in result]
        assert heats == sorted(heats, reverse=True)

    def test_status_is_active(self, context):
        result = td.build_platform_compare(context)
        for entry in result:
            assert entry["status"] == "active"


# ===================================================================
# build_rising_works
# ===================================================================


class TestBuildRisingWorks:
    def test_returns_list(self, context):
        result = td.build_rising_works(context)
        assert isinstance(result, list)

    def test_each_work_has_required_fields(self, context):
        result = td.build_rising_works(context)
        for work in result:
            assert "title" in work
            assert "author" in work
            assert "platform" in work
            assert "rank" in work
            assert "rankChange" in work
            assert "heatScore" in work
            assert "tags" in work
            assert "detailUrl" in work

    def test_sorted_by_rank_change_desc(self, context):
        result = td.build_rising_works(context)
        if len(result) >= 2:
            changes = [(w["rankChange"], w["heatScore"]) for w in result]
            assert changes == sorted(changes, reverse=True)


# ===================================================================
# build_monthly_coverage
# ===================================================================


class TestBuildMonthlyCoverage:
    def test_empty_records(self):
        result = td.build_monthly_coverage([])
        assert "requiredMonths" in result
        assert "months" in result
        assert "missingMonths" in result
        assert "incompleteMonths" in result
        assert "isComplete" in result
        assert result["isComplete"] is False
        assert len(result["missingMonths"]) > 0

    def test_with_monthly_records(self):
        records = [
            {
                "title": "诡秘之主",
                "platform": "qidian",
                "listType": "月票 month=202605",
                "sourceUrl": "https://example.com?month=202605",
                "heatScore": 9500.0,
                "tags": ["克苏鲁"],
                "detailUrl": "https://qidian.com/book/101",
            },
            {
                "title": "凡人修仙传",
                "platform": "qidian",
                "listType": "月票 month=202605",
                "sourceUrl": "https://example.com?month=202605",
                "heatScore": 8200.0,
                "tags": ["修仙"],
                "detailUrl": "https://qidian.com/book/102",
            },
        ]
        result = td.build_monthly_coverage(records)
        assert result["isComplete"] is False  # only 2 records, expected 200

        # Find the 2026-05 month entry
        may_entry = next((m for m in result["months"] if m["month"] == "20265"), None)
        assert may_entry is not None
        assert may_entry["records"] == 2
        assert may_entry["uniqueWorks"] == 2
        assert may_entry["tagCount"] == 2
        assert may_entry["complete"] is False

    def test_month_key_not_matching_still_included(self):
        """Records without a month token still get grouped."""
        records = [
            {
                "listType": "畅销榜",
                "sourceUrl": "",
                "heatScore": 100.0,
                "tags": [],
                "title": "test",
            }
        ]
        result = td.build_monthly_coverage(records)
        # month_token_from_item returns None, so it won't be added to any
        # month bucket, but the required months are still present
        assert len(result["months"]) > 0


# ===================================================================
# build_summary
# ===================================================================


class TestBuildSummary:
    def test_returns_string(self):
        summary = td.build_summary(
            records=[{"title": "a"}, {"title": "b"}],
            monthly_records=[{"title": "a"}],
            hot_tags=[
                {"tag": "克苏鲁", "heat": 90, "change": 10, "group": "题材",
                 "stage": "rising", "relatedWorks": []},
                {"tag": "仙侠", "heat": 80, "change": 5, "group": "题材",
                 "stage": "stable", "relatedWorks": []},
            ],
            platforms=[
                {"platform": "qidian", "heat": 100, "works": 2, "topTags": [],
                 "status": "active"},
                {"platform": "zongheng", "heat": 50, "works": 0, "topTags": [],
                 "status": "inactive"},
            ],
            genre_cloud_timeline={
                "periods": [], "unit": "k", "clouds": [],
                "summary": "月票榜流派热度从传统玄幻到规则怪谈。",
            },
        )
        assert isinstance(summary, str)
        assert "2" in summary  # total record count
        assert "1" in summary  # monthly record count
        assert "克苏鲁" in summary
        assert "qidian" in summary
        assert "月票榜流派热度" in summary


# ===================================================================
# build_heat_curve
# ===================================================================


class TestBuildHeatCurve:
    def test_structure(self, context):
        hot_tags = td.build_hot_tags(context)
        curve = td.build_heat_curve(context, hot_tags)
        assert "dates" in curve
        assert "series" in curve
        assert "unit" in curve
        assert "source" in curve
        assert "valueLabel" in curve
        assert curve["unit"] == "k"
        assert curve["source"] == "monthly-ticket"
        assert curve["valueLabel"] == "月票"

    def test_series_have_names_and_data(self, context):
        hot_tags = td.build_hot_tags(context)
        curve = td.build_heat_curve(context, hot_tags)
        for series in curve["series"]:
            assert "name" in series
            assert "data" in series
            assert "description" in series


# ===================================================================
# build_genre_cloud_timeline
# ===================================================================


class TestBuildGenreCloudTimeline:
    def test_structure(self, context):
        result = td.build_genre_cloud_timeline(context)
        assert "periods" in result
        assert "unit" in result
        assert "clouds" in result
        assert "summary" in result
        assert result["unit"] == "k"

    def test_cloud_entries_have_period_and_genres(self, context):
        result = td.build_genre_cloud_timeline(context)
        for cloud in result["clouds"]:
            assert "period" in cloud
            assert "genres" in cloud


# ===================================================================
# build_migration
# ===================================================================


class TestBuildMigration:
    def test_returns_migration_and_timeline(self, context):
        migration, timeline = td.build_migration(context)
        assert "nodes" in migration
        assert "links" in migration
        assert "periods" in timeline
        assert "flows" in timeline

    def test_link_fields(self, context):
        migration, _ = td.build_migration(context)
        for link in migration["links"]:
            assert "source" in link
            assert "target" in link
            assert "value" in link
            assert "change" in link
            assert "reason" in link


# ===================================================================
# derive_rank_change, avg_change, avg_positive_rank_change, avg_link_change
# ===================================================================


class TestDeriveRankChange:
    def test_fewer_than_two_records_returns_zero(self):
        assert td.derive_rank_change([{"rank": 1}]) == 0

    def test_two_periods_computes_difference(self):
        items = [
            {"rank": 5, "listType": "月票 month=202604", "sourceUrl": "month=202604"},
            {"rank": 2, "listType": "月票 month=202605", "sourceUrl": "month=202605"},
        ]
        # first period rank=5, last period rank=2 → 5 - 2 = 3
        assert td.derive_rank_change(items) == 3

    def test_non_positive_result_clamped_to_zero(self):
        items = [
            {"rank": 1, "listType": "月票 month=202604", "sourceUrl": "month=202604"},
            {"rank": 5, "listType": "月票 month=202605", "sourceUrl": "month=202605"},
        ]
        # first=1, last=5 → 1 - 5 = -4 → max(0, -4) = 0
        assert td.derive_rank_change(items) == 0


class TestAvgChange:
    def test_positive_values(self):
        hot_tags = [
            {"tag": "a", "heat": 100, "change": 10, "group": "题材", "stage": "rising",
             "relatedWorks": []},
            {"tag": "b", "heat": 80, "change": 5, "group": "题材", "stage": "stable",
             "relatedWorks": []},
            {"tag": "c", "heat": 60, "change": 0, "group": "题材", "stage": "stable",
             "relatedWorks": []},
        ]
        assert td.avg_change(hot_tags) == 5.0  # (10+5+0)/3 = 5.0

    def test_tags_are_limited_to_first_10(self):
        tags = [
            {"tag": f"t{i}", "heat": 100 - i, "change": i, "group": "题材",
             "stage": "stable", "relatedWorks": []}
            for i in range(15)
        ]
        # avg of first 10: (0+1+...+9)/10 = 45/10 = 4.5
        assert td.avg_change(tags) == 4.5


class TestAvgPositiveRankChange:
    def test_filters_positive_only(self):
        works = [
            {"title": "a", "rankChange": 5, "heatScore": 100},
            {"title": "b", "rankChange": -2, "heatScore": 80},
            {"title": "c", "rankChange": 10, "heatScore": 90},
            {"title": "d", "rankChange": 0, "heatScore": 70},
        ]
        # only 5 and 10 → avg = 7.5
        assert td.avg_positive_rank_change(works) == 7.5


class TestAvgLinkChange:
    def test_average_of_changes(self):
        links = [
            {"source": "a", "target": "b", "change": 10, "value": 5, "reason": ""},
            {"source": "c", "target": "d", "change": 20, "value": 3, "reason": ""},
        ]
        assert td.avg_link_change(links) == 15.0

    def test_empty_list(self):
        assert td.avg_link_change([]) == 0


# ===================================================================
# score_item / monthly_heat_score
# ===================================================================


class TestScoreItem:
    def test_score_with_heat_and_rank(self):
        item = {"heatScore": 1000, "rank": 10}
        score = td.score_item(item)
        # math.log1p(1000) * 10 + max(0, 120-10)/3
        expected = math.log1p(1000) * 10 + (110 / 3)
        assert score == pytest.approx(expected, rel=1e-9)

    def test_rank_zero_no_bonus(self):
        item = {"heatScore": 100, "rank": 0}
        score = td.score_item(item)
        assert score == math.log1p(100) * 10  # no rank bonus


class TestMonthlyHeatScore:
    def test_returns_heat_score(self):
        assert td.monthly_heat_score({"heatScore": 9500}) == 9500.0

    def test_defaults_to_zero(self):
        assert td.monthly_heat_score({}) == 0.0


# ===================================================================
# now_iso
# ===================================================================


class TestNowIso:
    def test_returns_zulu_format(self):
        result = td.now_iso()
        assert result.endswith("Z")
        assert "T" in result
        # Rough check — should be the current date
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert result.startswith(today)

    def test_no_microseconds(self):
        result = td.now_iso()
        # If microseconds were present there would be a '.' before the Z
        assert "." not in result.replace("+00:00", "Z")


# ===================================================================
# summarize_genre_clouds / genre_cloud_delta
# ===================================================================


class TestSummarizeGenreClouds:
    def test_empty_clouds(self):
        result = td.summarize_genre_clouds([])
        assert "暂无" in result

    def test_with_clouds(self):
        clouds = [
            {"period": "01月", "genres": [
                {"name": "传统玄幻", "value": 50},
                {"name": "系统流", "value": 30},
            ]},
            {"period": "02月", "genres": [
                {"name": "规则怪谈", "value": 60},
                {"name": "家族群像流", "value": 40},
            ]},
        ]
        result = td.summarize_genre_clouds(clouds)
        assert "传统玄幻" in result
        assert "规则怪谈" in result


class TestGenreCloudDelta:
    def test_single_cloud_returns_zero(self):
        clouds = [{"period": "01月", "genres": [{"name": "a", "value": 10}]}]
        assert td.genre_cloud_delta({"clouds": clouds}) == 0

    def test_two_clouds(self):
        clouds = [
            {"period": "01月", "genres": [{"name": "a", "value": 100}]},
            {"period": "02月", "genres": [{"name": "b", "value": 150}]},
        ]
        # first_total=100, last_total=150 → (150-100)/100*100 = 50
        assert td.genre_cloud_delta({"clouds": clouds}) == 50.0


# ===================================================================
# normalize_record — edge: Chinese category added to tags
# ===================================================================


class TestNormalizeRecordEdgeCases:
    def test_category_added_to_tags(self):
        item = {
            "title": "test",
            "platform": "p",
            "listType": "l",
            "category": "玄幻",
            "tags": ["爽文"],
            "capturedAt": "2026-01-01T00:00:00Z",
        }
        td.normalize_record(item)
        assert "玄幻" in item["tags"]
        assert "爽文" in item["tags"]

    def test_no_tags_field(self):
        item = {
            "title": "test",
            "platform": "p",
            "listType": "l",
            "capturedAt": "2026-01-01T00:00:00Z",
        }
        td.normalize_record(item)
        assert item["tags"] == []  # no category, no tags


# ===================================================================
# canonical_list_key edge cases
# ===================================================================


class TestCanonicalListKeyEdgeCases:
    def test_source_url_without_month_param(self):
        """monthly-ticket keyword in listType but no month param."""
        item = {"listType": "monthly-ticket", "sourceUrl": ""}
        assert td.canonical_list_key(item) == "monthly-ticket"
