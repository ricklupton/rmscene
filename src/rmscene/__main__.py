"""Experimental cli helpers."""

import sys
import argparse
from . import read_blocks, write_blocks, TextFormat
from .text import extract_text, simple_text_document
from .rm2svg import rm2svg, rm2pdf


def parse_args(args):
    # create the top-level parser
    parser = argparse.ArgumentParser(prog="rmscene")
    # parser.add_argument('--foo', action='store_true', help='foo help')

    subparsers = parser.add_subparsers(help="sub-command help")

    parser_a = subparsers.add_parser("print-blocks", help="dump scene block data")
    parser_a.add_argument("file", type=argparse.FileType("rb"), help="filename to read")
    parser_a.set_defaults(func=pprint_file)

    parser_b = subparsers.add_parser("print-text", help="dump text")
    parser_b.add_argument("file", type=argparse.FileType("rb"), help="filename to read")
    parser_b.set_defaults(func=print_text)

    parser_c = subparsers.add_parser("text2rm", help="convert text")
    parser_c.add_argument("file", type=argparse.FileType("wb"), help="filename to write")
    parser_c.set_defaults(func=convert_text)

    parser_d = subparsers.add_parser("rm2svg", help="convert rm to svg")
    parser_d.add_argument("infile", type=str, help="filename to read")
    parser_d.add_argument("outfile", type=str, help="filename to write")
    parser_d.set_defaults(func=do_rm2svg)

    parser_d = subparsers.add_parser("rm2pdf", help="convert rm to pdf")
    parser_d.add_argument("infile", type=str, help="filename to read")
    parser_d.add_argument("outfile", type=str, help="filename to write")
    parser_d.set_defaults(func=do_rm2pdf)

    return parser.parse_args(args)


def pprint_file(args) -> None:
    import pprint

    result = read_blocks(args.file)
    for el in result:
        print()
        pprint.pprint(el)


def print_text(args):
    for fmt, line in extract_text(args.file):
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


def convert_text(args):
    write_blocks(args.file, simple_text_document(sys.stdin.read()))


def do_rm2svg(args):
    rm2svg(args.infile, args.outfile)


def do_rm2pdf(args):
    rm2pdf(args.infile, args.outfile)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    args.func(args)
