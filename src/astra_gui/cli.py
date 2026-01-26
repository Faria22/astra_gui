"""Command-line interface for launching the ASTRA GUI."""

import argparse
import sys
from collections.abc import Sequence

from astra_gui.__about__ import __version__
from astra_gui.app import Astra
from astra_gui.utils.logger_module import setup_logger


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI.

    Returns
    -------
    argparse.ArgumentParser
        Parser configured with all ASTRA GUI CLI options.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', default=None, action='store', help='Path to run the GUI on (optional)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    logging_group = parser.add_mutually_exclusive_group()
    logging_group.add_argument('-db', '--debug', action='store_true', help='Enable debug logging output')
    logging_group.add_argument('-v', '--verbose', action='store_true', help='Show info level logging output')
    logging_group.add_argument('-q', '--quiet', action='store_true', help='Only show error logging output')
    parser.add_argument('-ssh', action='store_true', help='Run the GUI using the ssh client')

    create_cc = parser.add_argument_group(title='Create Close Coupling pages')
    create_cc.add_argument('-m', '--molecule', action='store_true')
    create_cc.add_argument('-d', '--dalton', action='store_true')
    create_cc.add_argument('-l', '--lucia', action='store_true')
    create_cc.add_argument('-c', '--closecoupling', action='store_true')
    create_cc.add_argument('-b', '--bsplines', action='store_true')

    time_independent = parser.add_argument_group('Time Independent pages')
    time_independent.add_argument('-struct', '--structural', action='store_true')
    time_independent.add_argument('-scatt', '--scattering', action='store_true')
    time_independent.add_argument('-pad', '--pad', action='store_true')

    time_dependent = parser.add_argument_group('Time Dependent pages')
    time_dependent.add_argument('-p', '--pulse', action='store_true')

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Parse arguments, configure logging, and launch the GUI."""
    # Allow passing a custom argv during testing or interactive debugging without mutating sys.argv directly.
    arg_list = list(argv) if argv is not None else sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(arg_list)

    setup_logger(debug=args.debug, verbose=args.verbose, quiet=args.quiet)

    astra = Astra(args)
    astra.mainloop()


if __name__ == '__main__':
    main()
