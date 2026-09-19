import unittest

from devconfig_gen import Diagnostic, validation


class TestValidationHelpers(unittest.TestCase):
    def test_expect_string_rejects_wrong_type_and_empty(self):
        errors = []
        self.assertIsNone(validation.expect_string(5, "a.b", errors))
        self.assertIsNone(validation.expect_string("  ", "a.c", errors))
        self.assertEqual(
            [(d.field, d.message) for d in errors],
            [("a.b", "b must be a string, got int 5"), ("a.c", "c must not be empty")],
        )

    def test_expect_string_trims_whitespace(self):
        errors = []
        self.assertEqual(validation.expect_string("  web  ", "a.b", errors), "web")
        self.assertEqual(errors, [])

    def test_expect_integer_range_message(self):
        errors = []
        self.assertIsNone(
            validation.expect_integer(99999, "service.port", errors, minimum=1, maximum=65535)
        )
        self.assertEqual(errors[0].field, "service.port")
        self.assertEqual(errors[0].message, "port must be between 1 and 65535, got 99999")
        self.assertEqual(errors[0].severity, "error")

    def test_expect_integer_rejects_bool(self):
        errors = []
        self.assertIsNone(validation.expect_integer(True, "a.b", errors))
        self.assertEqual(errors[0].message, "b must be an integer, got boolean True")

    def test_expect_integer_minimum_only(self):
        errors = []
        self.assertIsNone(validation.expect_integer(0, "a.b", errors, minimum=1))
        self.assertEqual(errors[0].message, "b must be >= 1, got 0")

    def test_expect_enum_is_case_insensitive_and_reports_options(self):
        errors = []
        self.assertEqual(
            validation.expect_enum(
                "Production", "service.environment", errors, allowed=("development", "production")
            ),
            "production",
        )
        self.assertEqual(errors, [])
        self.assertIsNone(
            validation.expect_enum(
                "prod", "service.environment", errors, allowed=("development", "production")
            )
        )
        self.assertEqual(
            errors[0].message,
            "environment must be one of development, production, got 'prod'",
        )

    def test_expect_string_mapping_normalizes_values(self):
        errors = []
        result = validation.expect_string_mapping(
            {"team": "platform", "count": 3, "empty": None}, "service.labels", errors
        )
        self.assertEqual(result, {"team": "platform", "count": "3", "empty": ""})
        self.assertEqual(errors, [])

    def test_expect_string_mapping_rejects_nested_values(self):
        errors = []
        validation.expect_string_mapping({"bad": {"x": 1}}, "service.labels", errors)
        self.assertEqual(errors[0].field, "service.labels.bad")
        self.assertEqual(
            errors[0].message, "labels.bad must be a scalar value, got dict {'x': 1}"
        )

    def test_validation_error_accepts_diagnostics(self):
        error = validation.ValidationError(
            [Diagnostic("a", "a is bad"), Diagnostic("b", "b is bad", severity="warning")]
        )
        self.assertEqual(error.errors, ("a is bad", "b is bad"))
        self.assertEqual(str(error), "a is bad; b is bad")

    def test_validation_error_accepts_plain_strings(self):
        error = validation.ValidationError(["a: one", "b: two"])
        self.assertEqual(error.errors, ("a: one", "b: two"))
        self.assertEqual(error.diagnostics[0].field, "")

    def test_diagnostic_renders_and_serializes(self):
        diagnostic = Diagnostic("service.port", "port must be between 1 and 65535, got 99999")
        self.assertEqual(str(diagnostic), diagnostic.message)
        self.assertEqual(
            diagnostic.as_dict(),
            {
                "field": "service.port",
                "message": "port must be between 1 and 65535, got 99999",
                "severity": "error",
            },
        )


if __name__ == "__main__":
    unittest.main()
