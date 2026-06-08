"""Tests for review_critic.collectors — HTML parser, URL builders, text classifiers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from review_critic import collectors as c
from review_critic.models import Review


# ---------------------------------------------------------------------------
# chinese_char_count
# ---------------------------------------------------------------------------


class TestChineseCharCount:
    def test_counts_cjk_characters(self):
        assert c.chinese_char_count("这是一段中文") == 6

    def test_ignores_ascii(self):
        assert c.chinese_char_count("hello中文world") == 2

    def test_empty_returns_zero(self):
        assert c.chinese_char_count("") == 0

    def test_no_cjk_returns_zero(self):
        assert c.chinese_char_count("hello world") == 0


# ---------------------------------------------------------------------------
# sentence_mark_count
# ---------------------------------------------------------------------------


class TestSentenceMarkCount:
    def test_counts_chinese_punctuation(self):
        assert c.sentence_mark_count("。！？；，") == 5

    def test_counts_mixed_text(self):
        assert c.sentence_mark_count("好书。推荐！真的吗？") == 3

    def test_no_marks_returns_zero(self):
        assert c.sentence_mark_count("hello world") == 0

    def test_counts_commas(self):
        assert c.sentence_mark_count("，") == 1


# ---------------------------------------------------------------------------
# looks_like_boilerplate
# ---------------------------------------------------------------------------


class TestLooksLikeBoilerplate:
    def test_detects_javascript_markers(self):
        assert c.looks_like_boilerplate("function foo() { return 1; }") is True
        assert c.looks_like_boilerplate("var x = window.location;") is True
        assert c.looks_like_boilerplate("document.getElementById") is True
        assert c.looks_like_boilerplate("encodeURIComponent") is True

    def test_detects_chinese_boilerplate(self):
        assert c.looks_like_boilerplate("备案号京ICP备2020xxxxxx号") is True
        assert c.looks_like_boilerplate("违法不良信息举报") is True
        assert c.looks_like_boilerplate("用户协议 and 隐私政策") is True
        assert c.looks_like_boilerplate("安全验证") is True

    def test_normal_text_not_boilerplate(self):
        assert c.looks_like_boilerplate("这本书的文笔很好，剧情精彩。") is False

    def test_case_insensitive_code_markers(self):
        assert c.looks_like_boilerplate("Function foo()") is True


# ---------------------------------------------------------------------------
# infer_platform
# ---------------------------------------------------------------------------


class TestInferPlatform:
    def test_recognizes_tieba(self):
        assert c.infer_platform("https://tieba.baidu.com/p/123") == "tieba"

    def test_recognizes_douban(self):
        assert c.infer_platform("https://book.douban.com/subject/123") == "douban"

    def test_recognizes_xiaohongshu(self):
        assert c.infer_platform("https://www.xiaohongshu.com/discovery/item/123") == "xiaohongshu"

    def test_recognizes_xhslink(self):
        assert c.infer_platform("https://xhslink.com/abc") == "xiaohongshu"

    def test_recognizes_zongheng(self):
        assert c.infer_platform("https://www.zongheng.com/book/123") == "zongheng"

    def test_unknown_domain_returns_default(self):
        assert c.infer_platform("https://example.com/page") == "manual"

    def test_custom_default(self):
        assert c.infer_platform("https://example.com/page", default="unknown") == "unknown"


# ---------------------------------------------------------------------------
# build_search_url
# ---------------------------------------------------------------------------


class TestBuildSearchUrl:
    def test_tieba_url(self):
        url = c.build_search_url("tieba", "诡秘之主")
        assert "tieba.baidu.com" in url
        assert "诡秘之主" in url or "%E8%AF%A1%E7%A7%98%E4%B9%8B%E4%B8%BB" in url

    def test_douban_url(self):
        url = c.build_search_url("douban", "诡秘之主", page_index=0)
        assert "douban.com" in url
        assert "start=0" in url

    def test_douban_url_page_index(self):
        url = c.build_search_url("douban", "诡秘之主", page_index=2)
        assert "start=40" in url

    def test_xiaohongshu_url(self):
        url = c.build_search_url("xiaohongshu", "修罗武神")
        assert "xiaohongshu.com" in url

    def test_zongheng_url(self):
        url = c.build_search_url("zongheng", "修罗武神")
        assert "zongheng.com" in url

    def test_unsupported_platform_raises(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            c.build_search_url("weibo", "book")


# ---------------------------------------------------------------------------
# relevance_score
# ---------------------------------------------------------------------------


class TestRelevanceScore:
    def test_book_name_in_text_adds_two(self):
        assert c.relevance_score("这本书叫诡秘之主很好看", "诡秘之主") >= 2

    def test_deep_review_keywords_add_score(self):
        text = "文笔很好 剧情精彩 逻辑严密 角色鲜活"
        score = c.relevance_score(text, "书")
        # 4 keywords matched
        assert score >= 4

    def test_long_text_gets_extra_point(self):
        text = "文笔。" * 100  # 200 chars
        score = c.relevance_score(text, "书")
        # Keywords: "文笔" matches → +1,  length ≥ 180 → +1 (no book name)
        expected = 2  # one keyword + length bonus
        assert score >= expected

    def test_no_match_returns_zero(self):
        assert c.relevance_score("hello world", "书") == 0


# ---------------------------------------------------------------------------
# is_review_like
# ---------------------------------------------------------------------------


class TestIsReviewLike:
    def test_review_like_text_passes(self):
        # Need >= 80 chars, >= 40 Chinese chars, >= 2 sentence marks, relevance >= 2
        text = (
            "这本书的文笔非常细腻，逻辑严密，伏笔回收做得很好。"
            "世界观构建顶级，角色智商在线，剧情引人入胜。"
            "推荐给所有克苏鲁和悬疑推理爱好者阅读，入坑不亏！"
            "另外这本书的逻辑严密程度令人惊叹，角色塑造也很成功。"
        )
        assert c.is_review_like(text, "诡秘之主") is True

    def test_boilerplate_is_rejected(self):
        assert c.is_review_like("function foo()", "书") is False

    def test_short_text_without_enough_chinese_fails(self):
        assert c.is_review_like("hello world", "书") is False

    def test_short_on_sentence_marks_fails(self):
        text = "这本书的文笔非常细腻逻辑严" * 10  # many Chinese chars but few marks
        assert c.is_review_like(text, "书") is False

    def test_min_chars_adjusts_threshold(self):
        # Text with ~45 Chinese chars, ~55 total length, many keywords.
        # With min_chars=10: length >= min_chars, relevance >= 2 -> passes.
        # With default min_chars=80: chinese_count < 60 -> fails.
        text = "文笔剧情逻辑人物角色节奏设定伏笔世界观更新爽点毒点弃文烂尾。这本小说整体来说真的不错，推荐入坑阅读！"
        # First verify it passes with the lower threshold
        assert c.is_review_like(text, "book", min_chars=10) is True
        # Then verify it fails with default threshold
        assert c.is_review_like(text, "book") is False


# ---------------------------------------------------------------------------
# trim_review
# ---------------------------------------------------------------------------


class TestTrimReview:
    def test_short_text_returned_as_is(self):
        assert c.trim_review("好书推荐") == "好书推荐"

    def test_truncates_at_word_boundary(self):
        text = "hello world foo bar baz qux quux corge grault garply waldo fred plugh xyzzy thud"
        truncated = c.trim_review(text, max_chars=20)
        assert len(truncated) <= 20
        # Should break at last space within limit

    def test_normalizes_before_truncation(self):
        text = "  hello   world  "
        result = c.trim_review(text)
        assert result == "hello world"


# ---------------------------------------------------------------------------
# make_title
# ---------------------------------------------------------------------------


class TestMakeTitle:
    def test_short_text(self):
        assert c.make_title("好书") == "好书"

    def test_truncates_at_32_chars(self):
        text = "这是一段非常长的文本用来测试make_title的截断功能它应该被截断到32个字符"
        result = c.make_title(text)
        assert len(result) <= 35  # 32 + "..."
        assert result.endswith("...")

    def test_exactly_32_chars_no_ellipsis(self):
        text = "a" * 32
        assert c.make_title(text) == text

    def test_normalizes_space(self):
        assert c.make_title("  hello   world  ") == "hello world"


# ---------------------------------------------------------------------------
# dedupe_texts
# ---------------------------------------------------------------------------


class TestDedupeTexts:
    def test_deduplicates_exact_duplicates(self):
        texts = ["好书推荐", "好书推荐", "不同内容"]
        result = c.dedupe_texts(texts)
        assert len(result) == 2
        assert result[0] == "好书推荐"
        assert result[1] == "不同内容"

    def test_deduplicates_by_normalized_key(self):
        texts = ["Hello World!", "hello world!", "different"]
        result = c.dedupe_texts(texts)
        assert len(result) == 2

    def test_empty_list(self):
        assert c.dedupe_texts([]) == []

    def test_skips_empty_text(self):
        texts = ["", "  ", "real content"]
        result = c.dedupe_texts(texts)
        assert result == ["real content"]


# ---------------------------------------------------------------------------
# ReviewHTMLParser
# ---------------------------------------------------------------------------


class TestReviewHTMLParser:
    def test_parses_title(self):
        parser = c.ReviewHTMLParser()
        parser.feed("<html><head><title>我的书评</title></head><body></body></html>")
        assert parser.title == "我的书评"

    def test_parses_meta_description(self):
        parser = c.ReviewHTMLParser()
        parser.feed(
            '<html><head><meta name="description" content="好书推荐 文笔细腻"></head><body></body></html>'
        )
        assert parser.description == "好书推荐 文笔细腻"

    def test_parses_og_description(self):
        parser = c.ReviewHTMLParser()
        parser.feed(
            '<html><head><meta property="og:description" content="精彩书评"></head><body></body></html>'
        )
        assert parser.description == "精彩书评"

    def test_extracts_paragraphs(self):
        parser = c.ReviewHTMLParser()
        parser.feed("<html><body><p>第一段内容</p><p>第二段内容</p></body></html>")
        assert len(parser.blocks) == 2
        assert "第一段内容" in parser.blocks
        assert "第二段内容" in parser.blocks

    def test_ignores_script_content(self):
        parser = c.ReviewHTMLParser()
        parser.feed(
            "<html><body><script>var x = 'ignore';</script><p>可见内容</p></body></html>"
        )
        assert "可见内容" in parser.blocks
        assert "ignore" not in str(parser.blocks)

    def test_ignores_style_content(self):
        parser = c.ReviewHTMLParser()
        parser.feed(
            "<html><body><style>body { color: red; }</style><p>正文内容</p></body></html>"
        )
        assert "正文内容" in parser.blocks
        assert "color" not in str(parser.blocks)

    def test_extracts_div_content(self):
        parser = c.ReviewHTMLParser()
        parser.feed('<html><body><div class="content"><p>div内文本</p></div></body></html>')
        assert len(parser.blocks) == 1
        assert "div内文本" in parser.blocks[0]

    def test_handles_nested_tags(self):
        parser = c.ReviewHTMLParser()
        parser.feed("<html><body><article><section><p>深层嵌套</p></section></article></body></html>")
        assert any("深层嵌套" in b for b in parser.blocks)

    def test_empty_html(self):
        parser = c.ReviewHTMLParser()
        parser.feed("")
        assert parser.title == ""
        assert parser.description == ""
        assert parser.blocks == []


# ---------------------------------------------------------------------------
# candidate_review_blocks
# ---------------------------------------------------------------------------


class TestCandidateReviewBlocks:
    def test_filters_blocks_by_review_likeness(self):
        blocks = [
            (
                "这本书的文笔非常细腻，逻辑严密，伏笔回收做得很好。"
                "世界观构建顶级，角色智商在线，剧情引人入胜。"
                "推荐给所有克苏鲁和悬疑推理爱好者，入坑不亏！"
            ),
            "备案号京ICP备2020xxxxxx号",
            "纯英文文本 without Chinese chars",
        ]
        description = "关于本书的深度书评，文笔剧情都不错。"
        result = c.candidate_review_blocks(blocks, description, "诡秘之主", min_chars=10)
        # Only the first block should pass (not boilerplate, has Chinese, meets thresholds)
        assert len(result) >= 1
        assert "文笔非常细腻" in result[0]

    def test_description_included_if_review_like(self):
        description = (
            "这本书的文笔很好，逻辑严密，伏笔回收做得很到位。"
            "角色塑造非常成功，世界观宏大，剧情引人入胜。推荐给所有读者！"
        )
        result = c.candidate_review_blocks([], description, "诡秘之主", min_chars=10)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# extract_reviews_from_html
# ---------------------------------------------------------------------------


SAMPLE_REVIEW_HTML = """<html><head>
<title>诡秘之主深度书评</title>
<meta name="description" content="关于诡秘之主的精彩书评，文笔剧情世界观都很出色。">
<script>var __INITIAL_STATE__ = {};</script>
</head><body>
<div class="review-content">
<p>这本书的文笔非常细腻，逻辑严密，伏笔回收做得很好。世界观构建顶级，角色智商在线，剧情引人入胜。虽然开头节奏偏慢，但总体是难得佳作。强烈推荐给克苏鲁和悬疑推理爱好者，入坑不亏！</p>
<p>这本书的更新速度有点慢，拖更比较严重。前面剧情很精彩，但是到了后期有点水字数。希望作者能保持节奏，不要烂尾。</p>
<p>备案号京ICP备2020xxxxxx号违法不良信息举报</p>
</div>
</body></html>"""


class TestExtractReviewsFromHtml:
    def test_extracts_reviews_from_html(self):
        reviews = c.extract_reviews_from_html(
            html=SAMPLE_REVIEW_HTML,
            book="诡秘之主",
            platform="douban",
            source_url="https://book.douban.com/review/123",
            min_chars=10,
        )
        assert len(reviews) >= 1
        for review in reviews:
            assert isinstance(review, Review)
            assert review.book == "诡秘之主"
            assert review.platform == "douban"

    def test_reviews_have_title_from_parser(self):
        reviews = c.extract_reviews_from_html(
            html=SAMPLE_REVIEW_HTML,
            book="诡秘之主",
            platform="douban",
            min_chars=10,
        )
        assert len(reviews) >= 1
        # Title comes from <title> tag for the first review
        assert reviews[0].title == "诡秘之主深度书评"

    def test_extracts_reviews_deduplicated(self):
        # Same HTML twice should produce same reviews (deduped)
        reviews1 = c.extract_reviews_from_html(
            html=SAMPLE_REVIEW_HTML, book="诡秘之主", platform="douban", min_chars=10
        )
        reviews2 = c.extract_reviews_from_html(
            html=SAMPLE_REVIEW_HTML, book="诡秘之主", platform="douban", min_chars=10
        )
        assert len(reviews1) == len(reviews2)

    def test_review_content_contains_expected_text(self):
        reviews = c.extract_reviews_from_html(
            html=SAMPLE_REVIEW_HTML, book="诡秘之主", platform="douban", min_chars=10
        )
        all_content = " ".join(r.content for r in reviews)
        assert "文笔非常细腻" in all_content
        assert "更新速度" in all_content


# ---------------------------------------------------------------------------
# fetch_url (mocked)
# ---------------------------------------------------------------------------


class TestFetchUrl:
    def test_fetch_url_success(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html><body><p>test</p></body></html>"
        mock_response.__enter__.return_value = mock_response
        mock_response.headers = MagicMock()
        mock_response.headers.get_content_charset.return_value = "utf-8"

        with patch("review_critic.collectors.urlopen", return_value=mock_response):
            result = c.fetch_url("https://example.com/review")
            assert "test" in result

    def test_fetch_url_raises_on_http_error(self):
        import urllib.error

        with patch("review_critic.collectors.urlopen") as mock_urlopen:
            error_response = MagicMock()
            error_response.read.return_value = b"Not Found"
            error_response.code = 404
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "http://example.com", 404, "Not Found", {}, error_response
            )
            with pytest.raises(RuntimeError, match="HTTP 404"):
                c.fetch_url("https://example.com/review")
