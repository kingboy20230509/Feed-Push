import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import feedparser
import requests

from test_deployment import load_bot


class AuthorFooterTests(unittest.TestCase):
    def setUp(self):
        self.bot = load_bot({})

    def test_dc_creator_is_displayed_and_markdown_escaped(self):
        feed = feedparser.parse('''<rss version="2.0"
            xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item>
            <link>https://www.nodeseek.com/post-1060392-1</link>
            <dc:creator>A_[测试] &amp; B</dc:creator>
            </item></channel></rss>''')
        self.assertEqual(self.bot.notification_footer(feed.entries[0], "nodeseek"),
                         r"📱 nodeseek    👤 A\_\[测试\] & B")

    def test_missing_author_and_other_feeds_keep_original_footer(self):
        for entry in (feedparser.FeedParserDict(link="https://www.nodeseek.com/post-1-1"),
                      feedparser.FeedParserDict(link="https://example.com/post", author="A")):
            self.assertEqual(self.bot.notification_footer(entry, "source"), "📱 source")

    def test_only_matching_author_links_on_nodeseek_are_accepted(self):
        parser = self.bot.NodeSeekAuthorParser("A_[测试] & B")
        parser.feed('''<a class="author-name" href="/space/1">其他用户</a>
            <a class="author-name" href="https://evil.example/space/2">A_[测试] &amp; B</a>
            <a class="author-name" href="javascript:alert(1)">A_[测试] &amp; B</a>
            <a class="author-name" href="https://[invalid">A_[测试] &amp; B</a>
            <a class="other author-name" href="/space/42"><span>A_[测试]</span> &amp; B</a>
            <a class="author-name" href="/space/99">其他回复者</a>''')
        self.assertEqual(parser.profile_url, "https://www.nodeseek.com/space/42")
        entry = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-1-1",
                                          author="A_[测试] & B")
        self.assertEqual(self.bot.notification_footer(entry, "nodeseek", parser.profile_url),
                         r"📱 nodeseek    👤 [A\_\[测试\] & B](https://www.nodeseek.com/space/42)")

    def test_lookup_failures_are_optional_and_unrelated_links_are_not_fetched(self):
        entry = feedparser.FeedParserDict(link="https://www.nodeseek.com/post-1-1", author="A")
        with patch.object(self.bot.requests, "get") as get:
            for error in (requests.HTTPError("403"), requests.Timeout("timeout")):
                get.side_effect = error
                self.assertIsNone(self.bot.nodeseek_author_profile(entry))
            get.side_effect = None
            get.return_value = Mock(status_code=302)
            self.assertIsNone(self.bot.nodeseek_author_profile(entry))
            get.return_value = Mock(status_code=200, content=b'<html>challenge</html>')
            self.assertIsNone(self.bot.nodeseek_author_profile(entry))
            get.reset_mock()
            for link in ("https://evil.example/post-1-1", "https://www.nodeseek.com/login"):
                entry.link = link
                self.assertIsNone(self.bot.nodeseek_author_profile(entry))
            get.assert_not_called()


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
                page = Mock(status_code=200, content=b'<a href="/space/42" class="author-name">A</a>')
                context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
                result = requests.HTTPError("403") if blocked else page
                with patch.object(bot.requests, "get", side_effect=[rss, result, rss]) as get:
                    await bot.check_new_posts(context)
                    await bot.check_new_posts(context)
                context.bot.send_message.assert_awaited_once()
                text = context.bot.send_message.call_args.kwargs["text"]
                label = "A" if blocked else "[A](https://www.nodeseek.com/space/42)"
                self.assertTrue(text.endswith("📱 nodeseek    👤 " + label))
                self.assertEqual(bot.load_cache(), {"1"})
                self.assertEqual(get.call_count, 3)
                self.assertEqual(get.call_args_list[1].kwargs["timeout"], 3)
                self.assertFalse(get.call_args_list[1].kwargs["allow_redirects"])
