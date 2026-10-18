"""CLI entrypoint for python -m app.ingestion."""

import sys
from app.ingestion.cli import main

if __name__ == "__main__":
    sys.exit(main())
