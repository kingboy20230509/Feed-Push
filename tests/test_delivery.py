import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from telegram.error import BadRequest, RetryAfter, TimedOut

from test_deployment import load_bot


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.bot = load_bot({"DATA_DIR": self.directory.name, "ROOT_ID": "123"})
        self.context = SimpleNamespace(bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=42))))
        self.sources = {"123": {"rss_sources": [{"url": "https://example.com/rss"}]}}
        self.delivery = {"chat_id": "123", "rss_url": "https://example.com/rss",
                         "text": "full original message", "title": "post",
                         "attempts": 0, "status": "waiting", "next_attempt_at": 0}
        self.queue = {"post-1": self.delivery}
        self.cache = set()

    async def retry(self):
        await self.bot.retry_deliveries(self.context, self.queue, self.cache, self.sources)

    async def test_backoff_and_limit_survive_restart_and_keep_full_message(self):
        self.context.bot.send_message.side_effect = TimedOut()
        now = 1000
        with patch.object(self.bot.time, "time", side_effect=lambda: now):
            for count, delay in enumerate((120, 600, 1800), start=1):
                await self.retry()
                self.assertEqual(self.context.bot.send_message.await_count, count)
                # 重启后只从磁盘恢复，次数和时间仍然有效。
                self.queue = self.bot.load_deliveries()
                next_at = self.queue["post-1"]["next_attempt_at"]
                self.assertEqual(next_at, now + delay)
                now = next_at - 1
                await self.retry()
                self.assertEqual(self.context.bot.send_message.await_count, count)
                now = next_at
            await self.retry()
            self.queue = self.bot.load_deliveries()
            now += 86400
            await self.retry()
        self.assertEqual(self.context.bot.send_message.await_count, 4)
        self.assertEqual(self.queue["post-1"]["status"], "failed")
        self.assertEqual(self.queue["post-1"]["text"], "full original message")
        self.assertEqual(self.queue["post-1"]["attempts"], 4)
        self.assertEqual(self.cache, set())

    async def test_success_removes_pending_and_records_legacy_cache(self):
        await self.retry()
        self.assertEqual(self.bot.load_cache(), {"post-1"})
        self.assertEqual(self.bot.load_deliveries(), {})
        await self.retry()
        self.context.bot.send_message.assert_awaited_once()

    async def test_success_before_cache_failure_does_not_resend_on_restart(self):
        with patch.object(self.bot, "save_cache", side_effect=OSError("disk write failed")):
            with self.assertRaises(OSError):
                await self.retry()
        self.queue = self.bot.load_deliveries()
        self.cache = self.bot.load_cache()
        self.assertEqual(self.queue["post-1"]["message_id"], 42)
        await self.retry()
        self.context.bot.send_message.assert_awaited_once()
        self.assertEqual(self.bot.load_cache(), {"post-1"})

    async def test_bad_request_is_not_retried(self):
        self.context.bot.send_message.side_effect = BadRequest("invalid Markdown")
        await self.retry()
        await self.retry()
        self.context.bot.send_message.assert_awaited_once()
        self.assertEqual(self.bot.load_deliveries()["post-1"]["status"], "failed")

    async def test_retry_after_never_sends_before_telegram_allows(self):
        self.context.bot.send_message.side_effect = RetryAfter(900)
        with patch.object(self.bot.time, "time", return_value=1000):
            await self.retry()
        self.assertEqual(self.bot.load_deliveries()["post-1"]["next_attempt_at"], 1900)

    async def test_crash_during_send_preserves_budget_and_does_not_retry_immediately(self):
        self.context.bot.send_message.side_effect = RuntimeError("process interrupted")
        with patch.object(self.bot.time, "time", return_value=1000):
            with self.assertRaises(RuntimeError):
                await self.retry()
            self.queue = self.bot.load_deliveries()
            await self.retry()
        self.context.bot.send_message.assert_awaited_once()
        self.assertEqual(self.queue["post-1"]["attempts"], 1)

    async def test_queue_write_failure_prevents_network_send(self):
        with patch.object(self.bot, "save_deliveries", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                await self.retry()
        self.context.bot.send_message.assert_not_awaited()

    async def test_removed_source_or_changed_admin_cancels_pending(self):
        for change_admin in (False, True):
            self.delivery.update(status="waiting", attempts=0)
            self.queue = {"post-1": self.delivery}
            self.sources = {} if not change_admin else {"123": {"rss_sources": [{"url": "https://example.com/rss"}]}}
            self.delivery["chat_id"] = "456" if change_admin else "123"
            await self.retry()
            self.assertEqual(self.bot.load_deliveries()["post-1"]["status"], "cancelled")
        self.context.bot.send_message.assert_not_awaited()

    async def test_corrupt_queue_fails_closed(self):
        Path(self.bot.DELIVERY_FILE).write_text('{broken')
        with self.assertRaises(json.JSONDecodeError):
            self.bot.load_deliveries()

    async def test_atomic_cache_failure_keeps_previous_cache(self):
        self.bot.save_cache({"old-post"})
        with patch.object(self.bot.os, "replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.bot.save_cache({"new-post"})
        self.assertEqual(self.bot.load_cache(), {"old-post"})
        self.assertEqual([p.name for p in Path(self.directory.name).iterdir()], ["rss_cache3.txt"])

    def feed_response(self):
        return Mock(content=b'''<rss version="2.0"><channel>
            <item><guid>post-1</guid><title>gpt first</title>
            <link>https://example.com/post-1</link><description>original preview</description></item>
            <item><guid>post-2</guid><title>gpt second</title>
            <link>https://example.com/post-2</link></item>
            </channel></rss>''')

    async def test_rss_does_not_bypass_backoff_and_retry_works_after_entry_disappears(self):
        self.sources["123"]["rss_sources"][0]["regex_patterns"] = ["gpt", "first"]
        self.bot.save_user_data(self.sources)
        self.context.bot.send_message.side_effect = [TimedOut(), SimpleNamespace(message_id=2),
                                                     SimpleNamespace(message_id=3)]
        with patch.object(self.bot.time, "time", return_value=1000), \
                patch.object(self.bot.requests, "get", return_value=self.feed_response()):
            await self.bot.check_new_posts(self.context)
            await self.bot.check_new_posts(self.context)
        self.assertEqual(self.context.bot.send_message.await_count, 2)
        self.assertEqual(self.bot.load_cache(), {"post-2"})
        original = self.context.bot.send_message.call_args_list[0].kwargs["text"]
        # 容器重启且 RSS 已移除原帖：仍按磁盘保存的消息补发。
        restored = load_bot({"DATA_DIR": self.directory.name, "ROOT_ID": "123"})
        with patch.object(restored.time, "time", return_value=1120), \
                patch.object(restored.requests, "get", return_value=Mock(content=b'<rss><channel/></rss>')):
            await restored.check_new_posts(self.context)
        self.assertEqual(self.context.bot.send_message.await_count, 3)
        self.assertEqual(self.context.bot.send_message.call_args.kwargs["text"], original)
        self.assertEqual(restored.load_cache(), {"post-1", "post-2"})
        self.assertEqual(restored.load_deliveries(), {})

    async def test_exhausted_entry_in_live_rss_does_not_start_new_retry_budget(self):
        self.sources["123"]["rss_sources"][0]["regex_patterns"] = ["first"]
        self.bot.save_user_data(self.sources)
        self.context.bot.send_message.side_effect = TimedOut()
        with patch.object(self.bot.requests, "get", return_value=self.feed_response()):
            for now in (1000, 1120, 1720, 3520, 10000, 20000):
                with patch.object(self.bot.time, "time", return_value=now):
                    await self.bot.check_new_posts(self.context)
        self.assertEqual(self.context.bot.send_message.await_count, 4)
        failed = self.bot.load_deliveries()["post-1"]
        self.assertEqual(failed["status"], "failed")
        self.assertIn("original preview", failed["text"])
        self.assertNotIn("post-1", self.bot.load_cache())
