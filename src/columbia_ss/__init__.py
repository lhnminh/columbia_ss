"""Bench adoption service."""

from .app import create_app


def main() -> None:
    """Run the local development server."""
    app = create_app()
    app.run(debug=False)
