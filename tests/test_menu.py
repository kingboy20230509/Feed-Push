import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from test_deployment import load_bot


def make_update(user_id=123, chat_id=123, callback=None):
    message = SimpleNamespace(reply_text=AsyncMock(), text="")
    query = (SimpleNamespace(data=callback, answer=AsyncMock(),
                             edit_message_text=AsyncMock(), message=message)
             if callback is not None else None)
    return SimpleNamespace(effective_user=SimpleNamespace(id=user_id),
                           effective_chat=SimpleNamespace(id=chat_id),
                           message=message if query is None else None,
                           effective_message=message, callback_query=query)


class MenuTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.bot = load_bot({"DATA_DIR": self.directory.name, "ROOT_ID": "123"})
        self.context = SimpleNamespace(user_data={}, args=[], bot=SimpleNamespace())
        self.source = {"url": "https://rss.nodeseek.com/",
                       "keywords": [f"rule-{i}" for i in range(27)],
                       "regex_patterns": [f"pattern-{i}" for i in range(27)]}
        self.bot.save_user_data({"123": {"rss_sources": [self.source]}})

    def callback(self, action, user_id=123, chat_id=123):
        token = self.context.user_data["rss_menu"]["token"]
        return make_update(user_id, chat_id, f"ui:123:{token}:{action}")

    async def test_start_shows_menu_and_preserves_subscriptions(self):
        update = make_update()
        await self.bot.start(update, self.context)
        markup = update.message.reply_text.call_args.kwargs["reply_markup"]
        self.assertTrue(any("订阅源" in b.text for row in markup.inline_keyboard for b in row))
        self.assertEqual(self.bot.load_user_data()["123"]["rss_sources"], [self.source])
        self.assertTrue(all(len(b.callback_data.encode()) <= 64
                            for row in markup.inline_keyboard for b in row))

    async def test_rules_are_paginated_and_source_selection_uses_snapshot(self):
        await self.bot.render_menu(make_update(), self.context, "sources")
        await self.bot.menu_callback(self.callback("source:0"), self.context)
        update = self.callback("rules:3")
        await self.bot.menu_callback(update, self.context)
        text = update.callback_query.edit_message_text.call_args.args[0]
        self.assertIn("27. rule-26", text)
        self.assertNotIn("1. rule-0", text)

    async def test_other_users_chats_and_stale_buttons_are_rejected(self):
        self.bot.home_keyboard(make_update(), self.context)
        for update in (self.callback("home", user_id=456),
                       self.callback("home", chat_id=456),
                       make_update(callback="ui:123:expired:home")):
            await self.bot.menu_callback(update, self.context)
            self.assertTrue(update.callback_query.answer.call_args.kwargs["show_alert"])
            update.callback_query.edit_message_text.assert_not_called()

    async def test_access_is_checked_again_when_pressing_existing_button(self):
        self.bot.home_keyboard(make_update(), self.context)
        self.bot.ROOT_ID = 456
        update = self.callback("sources:0")
        await self.bot.menu_callback(update, self.context)
        self.assertIn("权限", update.callback_query.answer.call_args.args[0])
        update.callback_query.edit_message_text.assert_not_called()

    async def test_telegram_command_menu_is_registered(self):
        app = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))
        await self.bot.register_commands(app)
        commands = app.bot.set_my_commands.call_args.args[0]
        self.assertIn("menu", [command.command for command in commands])

    async def test_admin_guard_covers_messages_callbacks_and_group_chats(self):
        for update in (make_update(user_id=456), make_update(user_id=456, callback="ui:any"),
                       make_update(chat_id=-100123)):
            with self.assertRaises(self.bot.ApplicationHandlerStop):
                await self.bot.enforce_admin(update, self.context)
        await self.bot.enforce_admin(make_update(), self.context)

    async def test_whitelist_can_never_grant_access_to_non_admin(self):
        self.bot.save_allowed_users({456})
        for enabled in (True, False):
            self.bot.save_whitelist_status(enabled)
            self.assertTrue(self.bot.is_allowed_user(123))
            self.assertFalse(self.bot.is_allowed_user(456))
            self.assertFalse(self.bot.is_allowed_user(789))

    async def test_existing_non_admin_subscriptions_are_not_polled_or_deleted(self):
        from unittest.mock import patch
        users = {"456": {"rss_sources": [self.source]},
                 "-100123": {"rss_sources": [self.source]}}
        self.bot.save_user_data(users)
        with patch.object(self.bot.requests, "get") as request:
            await self.bot.check_new_posts(self.context)
        request.assert_not_called()
        self.assertEqual(self.bot.load_user_data(), users)

    async def test_button_input_reuses_existing_rule_matching_and_data_format(self):
        import re
        self.bot.home_keyboard(make_update(), self.context)
        await self.bot.render_menu(make_update(), self.context, "rules", url=self.source["url"])
        await self.bot.menu_callback(self.callback("add_rules"), self.context)
        update = make_update()
        update.message.text = "ovh\n+pi+desktop"
        await self.bot.menu_text(update, self.context)
        source = self.bot.load_user_data()["123"]["rss_sources"][0]
        self.assertEqual(source["keywords"][-2:], ["ovh", "+pi+desktop"])
        self.assertTrue(re.search(source["regex_patterns"][-1], "PI Desktop", re.I))
        self.assertFalse(re.search(source["regex_patterns"][-1], "PI only", re.I))
        self.assertEqual(self.context.args, [])

    async def test_add_source_validates_url_and_cancel_clears_pending_input(self):
        self.bot.home_keyboard(make_update(), self.context)
        await self.bot.menu_callback(self.callback("add_source"), self.context)
        update = make_update()
        update.message.text = "not-a-url"
        await self.bot.menu_text(update, self.context)
        self.assertEqual(len(self.bot.load_user_data()["123"]["rss_sources"]), 1)
        update.message.text = "https://example.com/rss"
        await self.bot.menu_text(update, self.context)
        self.assertEqual(len(self.bot.load_user_data()["123"]["rss_sources"]), 2)
        await self.bot.menu_callback(self.callback("add_source"), self.context)
        await self.bot.clear_menu_input(update, self.context)
        self.assertNotIn("rss_menu", self.context.user_data)

    async def test_expired_input_and_input_in_another_chat_cannot_modify_rules(self):
        self.bot.home_keyboard(make_update(), self.context)
        await self.bot.menu_callback(self.callback("add_source"), self.context)
        update = make_update(chat_id=456)
        update.message.text = "https://example.com/rss"
        await self.bot.menu_text(update, self.context)
        self.assertEqual(len(self.bot.load_user_data()["123"]["rss_sources"]), 1)
        update = make_update()
        update.message.text = "https://example.com/rss"
        self.context.user_data["rss_menu"]["expires"] = 0
        await self.bot.menu_text(update, self.context)
        self.assertNotIn("rss_menu", self.context.user_data)
        self.assertEqual(len(self.bot.load_user_data()["123"]["rss_sources"]), 1)

    async def test_rule_delete_requires_confirmation_and_only_removes_selected_rule(self):
        await self.bot.render_menu(make_update(), self.context, "rules", url=self.source["url"])
        await self.bot.menu_callback(self.callback("delete_rule:1"), self.context)
        self.assertEqual(self.bot.load_user_data()["123"]["rss_sources"], [self.source])
        confirmed = self.callback("confirm_delete")
        await self.bot.menu_callback(confirmed, self.context)
        source = self.bot.load_user_data()["123"]["rss_sources"][0]
        self.assertEqual(source["keywords"], [k for i, k in enumerate(self.source["keywords"]) if i != 1])
        self.assertEqual(source["regex_patterns"], [p for i, p in enumerate(self.source["regex_patterns"]) if i != 1])
        await self.bot.menu_callback(confirmed, self.context)
        self.assertEqual(self.bot.load_user_data()["123"]["rss_sources"], [source])

    async def test_source_delete_and_stale_confirmation_do_not_delete_new_content(self):
        await self.bot.render_menu(make_update(), self.context, "rules", url=self.source["url"])
        await self.bot.menu_callback(self.callback("delete_source"), self.context)
        changed = self.bot.load_user_data()
        changed["123"]["rss_sources"][0]["keywords"].append("new")
        self.bot.save_user_data(changed)
        await self.bot.menu_callback(self.callback("confirm_delete"), self.context)
        self.assertEqual(self.bot.load_user_data(), changed)
        await self.bot.menu_callback(self.callback("delete_source"), self.context)
        await self.bot.menu_callback(self.callback("confirm_delete"), self.context)
        self.assertEqual(self.bot.load_user_data()["123"]["rss_sources"], [])

    async def test_source_indices_can_change_without_redirecting_button_actions(self):
        await self.bot.render_menu(make_update(), self.context, "sources")
        users = self.bot.load_user_data()
        users["123"]["rss_sources"].insert(0, {"url": "https://another.example/rss", "keywords": []})
        self.bot.save_user_data(users)
        await self.bot.menu_callback(self.callback("source:0"), self.context)
        self.assertEqual(self.context.user_data["rss_menu"]["url"], self.source["url"])

    async def test_settings_buttons_reuse_existing_admin_handler(self):
        self.bot.home_keyboard(make_update(), self.context)
        await self.bot.menu_callback(self.callback("settings"), self.context)
        await self.bot.menu_callback(self.callback("group_verify:on"), self.context)
        self.assertTrue(self.bot.ENABLE_GROUP_VERIFY)
        self.bot.WHITELIST_GROUP_ID = -100123
        self.context.bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="left"))
        await self.bot.menu_callback(self.callback("group_verify:off"), self.context)
        self.assertFalse(self.bot.ENABLE_GROUP_VERIFY)


if __name__ == "__main__":
    unittest.main()
