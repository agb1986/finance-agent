"""Shared base argument parser for all finance-agent scripts."""

import argparse


def base_parser() -> argparse.ArgumentParser:
    """Return a base parser with common flags. Use as a parent:

    parser = argparse.ArgumentParser(parents=[base_parser()])
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser
