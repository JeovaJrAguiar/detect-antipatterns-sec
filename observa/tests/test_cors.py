import unittest

from observa.security.cors import parse_allowed_origins


class CorsOriginParsingTests(unittest.TestCase):
    def test_parses_explicit_origins_from_environment_value(self):
        origins = parse_allowed_origins(
            "http://localhost:3000, https://app.example.com/"
        )

        self.assertEqual(
            origins,
            ["http://localhost:3000", "https://app.example.com"],
        )

    def test_empty_value_disallows_cross_origin_requests(self):
        self.assertEqual(parse_allowed_origins(""), [])

    def test_rejects_wildcard_origin(self):
        with self.assertRaisesRegex(ValueError, "explicit origins"):
            parse_allowed_origins("*")

    def test_rejects_origin_with_path(self):
        with self.assertRaisesRegex(ValueError, "explicit origins"):
            parse_allowed_origins("https://app.example.com/dashboard")


if __name__ == "__main__":
    unittest.main()