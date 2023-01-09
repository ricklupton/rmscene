"""Experimental cli helpers."""

import sys
import argparse
from . import parse_blocks, TextFormat
from .text import parse_text


def parse_args(args):
    # create the top-level parser
    parser = argparse.ArgumentParser(prog='rmscene')
    # parser.add_argument('--foo', action='store_true', help='foo help')

    subparsers = parser.add_subparsers(help='sub-command help')

    parser_a = subparsers.add_parser('print-blocks', help='dump scene block data')
    parser_a.add_argument('file', type=argparse.FileType('rb'), help='filename to read')
    parser_a.set_defaults(func=pprint_file)

    parser_b = subparsers.add_parser('print-text', help='dump text')
    parser_b.add_argument('file', type=argparse.FileType('rb'), help='filename to read')
    parser_b.set_defaults(func=print_text)

    return parser.parse_args(args)


def pprint_file(args) -> None:
    import pprint
    result = parse_blocks(args.file)
    for el in result:
        print()
        pprint.pprint(el)


def print_text(args):
    for fmt, line in parse_text(args.file):
        if fmt == TextFormat.BULLET:
            print("- " + line)
        elif fmt == TextFormat.BULLET2:
            print("  + " + line)
        elif fmt == TextFormat.BOLD:
            print("> " + line)
        elif fmt == TextFormat.HEADING:
            print("# " + line)
        elif fmt == TextFormat.PLAIN:
            print(line)
        else:
            print(("[unknown format %s] " % fmt) + line)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    args.func(args)
