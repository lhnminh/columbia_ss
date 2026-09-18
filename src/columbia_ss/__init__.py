"""Bench adoption demo."""

from .app import create_app


def main() -> None:
    """Run the local demonstration server."""
    app = create_app()
    app.run(debug=False)
