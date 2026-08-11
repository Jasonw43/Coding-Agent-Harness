"""Allow ``python -m cah`` to run the CLI."""

from cah.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
