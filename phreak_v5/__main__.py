"""Command-line entrypoint for the PHREAK v5 console."""
from .presentation.rich_console import main


def run() -> None:
    """Launch the interactive Rich console."""
    main()


if __name__ == "__main__":
    run()
