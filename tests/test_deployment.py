import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_bot(env):
    with patch.dict(os.environ, env, clear=True):
        spec = importlib.util.spec_from_file_location("bot", ROOT / "telegram_rss_bot.py")
        bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot)
        return bot


class DeploymentTests(unittest.TestCase):
    def test_independent_bots_do_not_share_data_or_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            bots = [load_bot({"TELEGRAM_BOT_TOKEN": token,
                              "DATA_DIR": str(Path(directory) / name)})
                    for name, token in (("bot1", "111:a"), ("bot2", "222:b"))]
            for bot in bots:
                Path(bot.DATA_DIR).mkdir()
            bots[0].save_user_data({"123": {"rss_sources": []}})
            bots[0].save_allowed_users({123})
            bots[0].save_whitelist_status(True)
            bots[0].save_cache({"first-bot-entry"})
            self.assertEqual(bots[1].load_user_data(), {})
            self.assertEqual(bots[1].load_allowed_users(), set())
            self.assertFalse(bots[1].load_whitelist_status())
            self.assertEqual(bots[1].load_cache(), set())
            self.assertNotEqual(bots[0].TELEGRAM_BOT_TOKEN, bots[1].TELEGRAM_BOT_TOKEN)

    def test_instance_setup_preserves_config_and_routes_compose_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for name in ("bot-instance.sh", ".env.example", "docker-compose.yml"):
                shutil.copy2(ROOT / name, repo / name)
            for name in ("bot1", "bot2"):
                subprocess.run(["bash", str(repo / "bot-instance.sh"), "init", name],
                               check=True, capture_output=True)
            first = repo / "instances/bot1/.env"
            original = first.read_text() + "# user customization\n"
            first.write_text(original)
            subprocess.run(["bash", str(repo / "bot-instance.sh"), "init", "bot1"],
                           check=True, capture_output=True)
            self.assertEqual(first.read_text(), original)
            self.assertIn("BOT_DATA_DIR=./instances/bot2/data",
                          (repo / "instances/bot2/.env").read_text())
            self.assertEqual(first.stat().st_mode & 0o777, 0o600)
            stub = repo / "docker"
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            stub.chmod(0o700)
            with patch.dict(os.environ, {"PATH": str(repo) + os.pathsep + os.environ["PATH"]}):
                p = subprocess.run(["bash", str(repo / "bot-instance.sh"), "stop", "bot2"],
                                   cwd="/", check=True, capture_output=True, text=True)
            args = p.stdout.splitlines()
            self.assertEqual(args[args.index("-p") + 1], "feed-push-bot2")
            self.assertEqual(args[args.index("--env-file") + 1],
                             str(repo / "instances/bot2/.env"))
            self.assertEqual(args[-1], "stop")

    def test_native_default_data_directory(self):
        bot = load_bot({})
        self.assertEqual(Path(bot.USER_DATA_FILE), Path("user_data.json"))
        self.assertEqual(bot.UPDATE_INTERVAL, 300)
        self.assertFalse(bot.ENABLE_GROUP_VERIFY)
        with self.assertRaisesRegex(ValueError, "TELEGRAM_BOT_TOKEN"):
            bot.main()

    def test_environment_config_reaches_application_and_scheduler(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "new-data"
            bot = load_bot({
                "TELEGRAM_BOT_TOKEN": "123456:example",
                "ROOT_ID": "123456",
                "WHITELIST_GROUP_ID": "-100123456",
                "ENABLE_GROUP_VERIFY": "True",
                "UPDATE_INTERVAL": "600",
                "DATA_DIR": str(data_dir),
            })
            self.assertEqual(bot.ROOT_ID, 123456)
            self.assertEqual(bot.WHITELIST_GROUP_ID, -100123456)
            self.assertTrue(bot.ENABLE_GROUP_VERIFY)
            builder = Mock()
            builder.token.return_value = builder
            builder.connect_timeout.return_value = builder
            with patch.object(bot.Application, "builder", return_value=builder):
                bot.main()
            builder.token.assert_called_once_with("123456:example")
            app = builder.build.return_value
            self.assertIs(app.post_init, bot.register_commands)
            guard = next(call for call in app.add_handler.call_args_list if call.kwargs.get("group") == -2)
            self.assertIsInstance(guard.args[0], bot.TypeHandler)
            self.assertIs(guard.args[0].callback, bot.enforce_admin)
            app.job_queue.run_repeating.assert_called_once_with(
                bot.check_new_posts, interval=600, first=0
            )
            app.run_polling.assert_called_once_with()
            self.assertTrue(data_dir.is_dir())

    def test_legacy_data_files_are_read_and_updated_in_mounted_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            user_data = {"123": {"rss_sources": [{"url": "https://example.com/rss",
                         "keywords": ["+A-B"], "regex_patterns": ["existing-pattern"]}]}}
            (path / "user_data.json").write_text(json.dumps(user_data))
            (path / "allowed_users.json").write_text("[123]")
            (path / "whitelist_status.json").write_text('{"whitelist_enabled": true}')
            (path / "rss_cache3.txt").write_text("already-sent\n")
            bot = load_bot({"DATA_DIR": directory})
            self.assertEqual(bot.load_user_data(), user_data)
            self.assertEqual(bot.load_allowed_users(), {123})
            self.assertTrue(bot.is_whitelist_enabled())
            self.assertEqual(bot.load_cache(), {"already-sent"})
            bot.save_user_data(user_data)
            bot.save_allowed_users({123, 456})
            bot.save_whitelist_status(False)
            bot.save_cache({"already-sent", "new-entry"})
            self.assertEqual(json.loads((path / "user_data.json").read_text()), user_data)
            self.assertEqual(set(json.loads((path / "allowed_users.json").read_text())), {123, 456})
            self.assertFalse(bot.is_whitelist_enabled())
            self.assertEqual(bot.load_cache(), {"already-sent", "new-entry"})

    def test_legacy_false_group_id_is_supported(self):
        bot = load_bot({"WHITELIST_GROUP_ID": "false"})
        self.assertEqual(bot.WHITELIST_GROUP_ID, "false")

    def test_invalid_interval_fails_before_network_start(self):
        bot = load_bot({"TELEGRAM_BOT_TOKEN": "123456:example", "ROOT_ID": "123", "UPDATE_INTERVAL": "0"})
        with self.assertRaisesRegex(ValueError, "UPDATE_INTERVAL"):
            bot.main()


if __name__ == "__main__":
    unittest.main()
