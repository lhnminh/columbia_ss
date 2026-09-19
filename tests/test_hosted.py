"""Tests for hosted startup and operator safeguards."""

import unittest
from unittest.mock import patch

from columbia_ss import create_app
from columbia_ss import admin


class HostedSetupTests(unittest.TestCase):
    def test_app_uses_configured_postgres_url(self) -> None:
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example.invalid/bench_adoption"}):
            app = create_app()
        self.assertEqual(app.config["DATABASE_URL"], "postgresql://example.invalid/bench_adoption")

    def test_every_environment_requires_database_url(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL is required"):
                create_app()

    def test_public_stylesheet_is_available_locally(self) -> None:
        app = create_app("postgresql://example.invalid/bench_adoption")
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
