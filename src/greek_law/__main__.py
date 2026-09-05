"""Entry point for ``python -m greek_law``.

It lives here rather than under an ``if __name__ == "__main__":`` guard in
cli.py so that cli.py is only ever imported, never run as the main module —
which keeps its ``__name__`` (and therefore its logger name) "greek_law.cli"
instead of "__main__".
"""

from greek_law.cli import main

raise SystemExit(main())
