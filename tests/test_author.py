import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import feedparser
import requests

from test_deployment import load_bot


class AuthorFooterTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.bot = load_bot({"DATA_DIR": directory})

    def test_dc_creator_is_displayed_and_markdown_escaped(self):
        feed = feedparser.parse('''<rss version="2.0"
            xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item>
            <link>https://www.nodeseek.com/post-1060392-1</link>
            <dc:creator>A_[测试] &amp; B</dc:creator>
            </item></channel></rss>''')
        self.assertEqual(self.bot.notification_footer(feed.entries[0], "nodeseek"),
                         r"👤 A\_\[测试\] & B")

    def test_nodeseek_source_is_hidden_and_other_feeds_keep_original_footer(self):
        entry = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-1-1")
        self.assertEqual(self.bot.notification_footer(entry, "nodeseek"), "")
        entry = feedparser.FeedParserDict(link="https://example.com/post", author="A")
        self.assertEqual(self.bot.notification_footer(entry, "source"), "📱 source")

    def test_only_matching_author_links_on_nodeseek_are_accepted(self):
        parser = self.bot.NodeSeekAuthorParser("A_[测试] & B")
        parser.feed('''<a class="author-name" href="/space/1">其他用户</a>
            <a class="author-name" href="https://evil.example/space/2">A_[测试] &amp; B</a>
            <a class="author-name" href="javascript:alert(1)">A_[测试] &amp; B</a>
            <a class="author-name" href="https://[invalid">A_[测试] &amp; B</a>
            <a class="other author-name" href="/space/42"><span>A_[测试]</span> &amp; B</a>
            <a class="author-name" href="/space/99">其他回复者</a>''')
        self.assertEqual(parser.profile_url, "https://www.nodeseek.com/space/42#/discussions")
        entry = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-1-1",
                                          author="A_[测试] & B")
        self.assertEqual(self.bot.notification_footer(entry, "nodeseek", parser.profile_url),
                         r"👤 [A\_\[测试\] & B](https://www.nodeseek.com/space/42#/discussions)")

    def test_lookup_failures_are_optional_and_unrelated_links_are_not_fetched(self):
        entry = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-1-1", author="A")
        with patch.object(self.bot.requests, "get") as get:
            for error in (requests.HTTPError("403"), requests.Timeout("timeout")):
                get.side_effect = error
                self.assertIsNone(self.bot.nodeseek_author_profile(entry))
                self.bot.save_author_cache({"next_lookup_at": 0, "profiles": {}})
            get.side_effect = None
            get.return_value = Mock(status_code=302, headers={})
            self.assertIsNone(self.bot.nodeseek_author_profile(entry))
            self.bot.save_author_cache({"next_lookup_at": 0, "profiles": {}})
            get.return_value = Mock(status_code=200, headers={}, content=b'<html>challenge</html>')
            self.assertIsNone(self.bot.nodeseek_author_profile(entry))
            self.bot.save_author_cache({"next_lookup_at": 0, "profiles": {}})
            get.reset_mock()
            for link in ("https://evil.example/post-1-1", "https://www.nodeseek.com/login"):
                entry.link = link
                self.assertIsNone(self.bot.nodeseek_author_profile(entry))
            get.assert_not_called()

    def test_profile_tabs_and_query_strings_keep_the_author_profile(self):
        for href in ("/space/42", "/space/42#/general", "/space/42#/discussions",
                     "https://www.nodeseek.com/space/42/?from=post"):
            parser = self.bot.NodeSeekAuthorParser("A")
            parser.feed(f'<a class="author-name" href="{href}">A</a>')
            self.assertEqual(parser.profile_url, "https://www.nodeseek.com/space/42#/discussions")

    def test_http_failure_is_reported_without_blocking_push(self):
        entry = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-1-1", author="A")
        with patch.object(self.bot.requests, "get", return_value=Mock(status_code=403, headers={})), \
                patch("builtins.print") as log:
            self.assertIsNone(self.bot.nodeseek_author_profile(entry))
        log.assert_called_once_with("NodeSeek author lookup: HTTP 403 for /post-1-1, paused for 3600s")

    def test_persistent_author_cache_reuses_profiles_and_cools_down_on_challenge(self):
        first = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-1-1", author="A")
        later = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-2-1", author="A")
        unknown = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-3-1", author="B")
        uncached = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-4-1", author="C")
        profile = "https://www.nodeseek.com/space/42#/discussions"
        good = Mock(status_code=200, headers={}, content=b'<a class="author-name" href="/space/42">A</a>')
        recovered = Mock(status_code=200, headers={}, content=b'<a class="author-name" href="/space/43">C</a>')
        challenge = Mock(status_code=403, headers={"cf-mitigated": "challenge"})
        with patch.object(self.bot.time, "time", return_value=1000) as clock, \
                patch.object(self.bot.requests, "get", side_effect=[good, challenge, recovered]) as get:
            self.assertEqual(self.bot.nodeseek_author_profile(first), profile)
            restarted = load_bot({"DATA_DIR": self.bot.DATA_DIR})
            self.assertEqual(restarted.nodeseek_author_profile(later), profile)
            self.assertIsNone(restarted.nodeseek_author_profile(unknown))
            self.assertEqual(get.call_count, 1)

            clock.return_value += 120
            self.assertIsNone(restarted.nodeseek_author_profile(unknown))
            clock.return_value += 3599
            self.assertIsNone(restarted.nodeseek_author_profile(uncached))
            self.assertEqual(restarted.nodeseek_author_profile(later), profile)
            self.assertEqual(get.call_count, 2)

            clock.return_value += 1
            self.assertEqual(restarted.nodeseek_author_profile(uncached),
                             "https://www.nodeseek.com/space/43#/discussions")
            self.assertEqual(get.call_count, 3)


class AuthorNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_matched_posts_have_author_and_keep_filtering_and_deduplication(self):
        for blocked in (False, True):
            with self.subTest(blocked=blocked), tempfile.TemporaryDirectory() as directory:
                bot = load_bot({"DATA_DIR": directory, "ROOT_ID": "123"})
                bot.save_user_data({"123": {"rss_sources": [{"url": "https://rss.nodeseek.com/",
                    "regex_patterns": ["ovh", "netcup"]}]}})
                rss = Mock(content=b'''<rss version="2.0"
                    xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
                    <item><guid>1</guid><title>ovh netcup</title>
                    <link>https://www.nodeseek.com/post-1-1</link><dc:creator>A</dc:creator></item>
                    <item><guid>2</guid><title>unmatched</title>
                    <link>https://www.nodeseek.com/post-2-1</link><dc:creator>B</dc:creator></item>
                    </channel></rss>''')
                page = Mock(status_code=200, headers={}, content=b'<a href="/space/42" class="author-name">A</a>')
                context = SimpleNamespace(bot=SimpleNamespace(
                    send_message=AsyncMock(return_value=SimpleNamespace(message_id=1))))
                result = requests.HTTPError("403") if blocked else page
                with patch.object(bot.requests, "get", side_effect=[rss, result, rss]) as get:
                    await bot.check_new_posts(context)
                    await bot.check_new_posts(context)
                context.bot.send_message.assert_awaited_once()
                text = context.bot.send_message.call_args.kwargs["text"]
                label = "A" if blocked else "[A](https://www.nodeseek.com/space/42#/discussions)"
                self.assertTrue(text.endswith("👤 " + label))
                self.assertNotIn("📱 nodeseek", text)
                self.assertEqual(bot.load_cache(), {"1"})
                self.assertEqual(get.call_count, 3)
                self.assertEqual(get.call_args_list[1].kwargs["timeout"], 3)
                self.assertFalse(get.call_args_list[1].kwargs["allow_redirects"])
