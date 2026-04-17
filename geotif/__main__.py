"""geotif — collection of GeoTIFF tools."""

from __future__ import annotations

import argparse
import sys

from . import merge, sqlitedb

COMMANDS = {
    "sqlitedb": sqlitedb,
    "merge": merge,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="geotif", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, mod in COMMANDS.items():
        doc = (mod.__doc__ or "").strip()
        help_line = doc.splitlines()[0] if doc else None
        sp = sub.add_parser(
            name,
            help=help_line,
            description=mod.__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        mod.add_args(sp)
        sp.set_defaults(run=mod.run)
    a = p.parse_args(argv)
    return a.run(a) or 0


if __name__ == "__main__":
    sys.exit(main())
