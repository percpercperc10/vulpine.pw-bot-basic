import unittest

from bot import COMMANDS
from core import CommandRateLimiter, VulpineClient, command_args
from cogs.general import help_message
from cogs.giveaways import parse_duration
from cogs.stock import _message
from cogs.community import settings_for


class BotRegressionTests(unittest.TestCase):
    def test_command_parser_supports_mentions(self):
        self.assertEqual(command_args("!help@social_bot"), ("help", []))
        self.assertEqual(command_args("!giveaway start 1h 2 Nitro"), ("giveaway", ["start", "1h", "2", "Nitro"]))

    def test_send_payload_uses_api_limits(self):
        payload = VulpineClient._send_payload(
            "conversation",
            "x" * 5000,
            [{"label": str(index), "data": str(index)} for index in range(8)],
            None,
            "row",
            [str(index) for index in range(25)],
        )
        self.assertEqual(len(payload["text"]), 4000)
        self.assertEqual(len(payload["buttons"]), 6)
        self.assertEqual(len(payload["targetUserIds"]), 20)
        self.assertEqual(payload["buttonsLayout"], "row")

    def test_command_rate_limiter_blocks_only_repeated_user_commands(self):
        limiter = CommandRateLimiter(10.0)
        self.assertEqual(limiter.check("conversation", "user"), 0.0)
        self.assertGreater(limiter.check("conversation", "user"), 0.0)
        self.assertEqual(limiter.check("conversation", "other-user"), 0.0)
        self.assertEqual(limiter.check("other-conversation", "user"), 0.0)

    def test_giveaway_duration_limits(self):
        self.assertEqual(parse_duration("30d"), 30 * 86400)
        self.assertIsNone(parse_duration("31d"))
        self.assertIsNone(parse_duration("0m"))

    def test_rich_text_messages_stay_within_api_limit(self):
        self.assertLessEqual(len(help_message()), 4000)
        self.assertLessEqual(len(_message({"Vulpine Pro": 1})), 4000)
        self.assertIn(":::drop", help_message())
        self.assertIn("| Area | Commands |", help_message())

    def test_command_registry_contains_core_features(self):
        for command in ("help", "giveaway", "stock", "verify", "mute"):
            self.assertIn(command, COMMANDS)

    def test_community_commands_are_registered(self):
        for command in ("settings", "warn", "warnings", "clearwarnings", "poll", "report", "backup"):
            self.assertIn(command, COMMANDS)

    def test_group_settings_default_to_enabled(self):
        self.assertEqual(settings_for("missing-group"), {"welcome": True, "verify": True})


if __name__ == "__main__":
    unittest.main()
