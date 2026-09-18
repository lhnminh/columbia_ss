"""Tests for hosted startup and operator safeguards."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from columbia_ss import create_app
from columbia_ss import admin


class HostedSetupTests(unittest.TestCase):
    def test_postgres_startup_does_not_initialize_sqlite(self) -> None:
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example.invalid/demo"}):
            with patch("columbia_ss.database.initialize_database") as initialize:
                app = create_app()
        initialize.assert_not_called()
        self.assertEqual(app.config["DATABASE_URL"], "postgresql://example.invalid/demo")

    def test_vercel_requires_database_url(self) -> None:
        with patch.dict("os.environ", {"VERCEL": "1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL is required"):
                create_app()

    def test_public_stylesheet_is_available_locally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(Path(directory) / "demo.sqlite3")
            response = app.test_client().get("/static/style.css")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"body", response.get_data())
            response.close()

    def test_reset_requires_explicit_yes(self) -> None:
        with patch("sys.argv", ["admin", "reset"]):
            with self.assertRaises(SystemExit) as error:
                admin.main()
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
