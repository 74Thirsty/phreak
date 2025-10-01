"""Allow ``python -m phreak`` to launch the legacy console."""

from phreak_cli import main


def run() -> None:
    """Entry point for ``python -m phreak``."""

    main()


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    run()
