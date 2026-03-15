"""Tests for common.args."""

import argparse

from common.args import base_parser


class TestBaseParser:
    def test_returns_argument_parser(self):
        parser = base_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_has_debug_flag(self):
        parser = base_parser()
        args = parser.parse_args([])
        assert hasattr(args, "debug")
        assert args.debug is False

    def test_debug_flag_true_when_passed(self):
        parser = base_parser()
        args = parser.parse_args(["--debug"])
        assert args.debug is True

    def test_add_help_disabled(self):
        # base_parser sets add_help=False so it can be used as a parent
        parser = base_parser()
        assert parser.add_help is False

    def test_usable_as_parent(self):
        parent = base_parser()
        child = argparse.ArgumentParser(parents=[parent])
        args = child.parse_args(["--debug"])
        assert args.debug is True

    def test_usable_as_parent_without_debug(self):
        parent = base_parser()
        child = argparse.ArgumentParser(parents=[parent])
        args = child.parse_args([])
        assert args.debug is False

    def test_child_parser_can_add_own_args(self):
        parent = base_parser()
        child = argparse.ArgumentParser(parents=[parent])
        child.add_argument("--output", default="out.json")
        args = child.parse_args(["--debug", "--output", "result.json"])
        assert args.debug is True
        assert args.output == "result.json"
