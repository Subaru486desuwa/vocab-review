import os
import unittest
from unittest.mock import patch

from app import create_app


class AppSmokeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_home_links_to_lab_and_marks_business_as_planned(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("词汇诊断", response.get_data(as_text=True))
        self.assertIn('href="/lab/hello"', response.get_data(as_text=True))
        self.assertIn("后续实现", response.get_data(as_text=True))

    def test_hello_renders_text_and_static_image(self):
        response = self.client.get("/lab/hello")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hello Flask", response.get_data(as_text=True))
        self.assertIn("/static/images/learning-loop.svg", response.get_data(as_text=True))

    def test_static_image_is_served(self):
        response = self.client.get("/static/images/learning-loop.svg")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/svg+xml")
        self.assertIn(b"<svg", response.data)
        response.close()

    def test_missing_database_and_models_do_not_block_basic_page(self):
        with patch.dict(
            os.environ, {"DB_HOST": "unavailable.invalid", "ML_MODEL_DIR": "/missing/ml", "DL_MODEL_DIR": "/missing/dl"}
        ):
            client = create_app({"TESTING": True}).test_client()
            self.assertEqual(client.get("/lab/hello").status_code, 200)

    def test_security_config_uses_environment_and_does_not_enable_debug(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "SECRET_KEY": "test-only"}):
            app = create_app()
        self.assertEqual(app.config["SECRET_KEY"], "test-only")
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertFalse(app.debug)

    def test_missing_secret_key_refuses_to_start(self):
        with patch.dict(os.environ, {"APP_ENV": "development", "SECRET_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                create_app()

    def test_auth_pages_render_without_database(self):
        for path in ("/login", "/register"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('name="csrf_token"', response.get_data(as_text=True))

    def test_unimplemented_business_routes_are_not_fake_successes(self):
        for path in ("/lab/ml", "/examples", "/api/v1/ml/recall"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


if __name__ == "__main__":
    unittest.main()
