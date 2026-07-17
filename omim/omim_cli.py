#!/usr/bin/env python3
"""
NOTE: This standalone script has been integrated into the `omim` package.

All OMIM REST API functionality is now available as a subcommand group:

    omim api entry --mim 100100 --include clinicalSynopsis
    omim api search --query "Marfan syndrome"
    omim api gene-map --mim 113705
    omim api clinical-synopsis --mim 603903
    omim api allelic-variants --mim 603903
    omim api status
    omim api config --set-key YOUR_KEY

The package sources data exclusively from the official OMIM API and the
official text-file downloads (https://omim.org/downloads). The legacy HTML
scraper has been removed for legal compliance.

This file is kept only for backward compatibility and simply delegates to the
new CLI.
"""
import sys

from omim.bin.cli import main


if __name__ == '__main__':
    # forward any args to the new CLI's `api` group
    if len(sys.argv) == 1 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)
    sys.argv = [sys.argv[0], 'api'] + sys.argv[1:]
    main()
