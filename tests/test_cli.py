"""Public Brief CLI 구조 테스트."""

import unittest

from cli import build_parser


class CliParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = build_parser()

    def test_all_required_commands_exist(self) -> None:
        expected = {
            "fetch",
            "clean",
            "summarize",
            "classify",
            "analyze",
            "report",
            "export",
        }
        subparser_action = next(
            action
            for action in self.parser._actions
            if getattr(action, "choices", None)
        )
        self.assertEqual(expected, set(subparser_action.choices))

    def test_fetch_options(self) -> None:
        args = self.parser.parse_args(
            [
                "fetch",
                "--limit",
                "5",
                "--date-from",
                "2026-08-01",
                "--date-to",
                "2026-08-31",
            ]
        )
        self.assertEqual(5, args.limit)
        self.assertEqual("2026-08-01", args.date_from)
        self.assertEqual("2026-08-31", args.date_to)

    def test_analysis_filters(self) -> None:
        args = self.parser.parse_args(
            ["analyze", "--category", "복지", "--priority", "HIGH"]
        )
        self.assertEqual("복지", args.category)
        self.assertEqual("HIGH", args.priority)

    def test_export_format(self) -> None:
        args = self.parser.parse_args(["export", "--format", "csv"])
        self.assertEqual("csv", args.format)

    def test_limit_must_be_positive(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["fetch", "--limit", "0"])

    def test_every_command_has_help(self) -> None:
        subparser_action = next(
            action
            for action in self.parser._actions
            if getattr(action, "choices", None)
        )
        for command, command_parser in subparser_action.choices.items():
            with self.subTest(command=command):
                help_text = command_parser.format_help()
                self.assertIn("usage:", help_text)
                self.assertIn(command, help_text)


if __name__ == "__main__":
    unittest.main()

