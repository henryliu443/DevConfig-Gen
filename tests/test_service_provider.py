import unittest

from devconfig_gen import Diagnostic, GenerationRequest
from devconfig_gen.providers.service import ServiceProvider


def build(context, **options):
    return GenerationRequest(context=context, options=options)


class TestServiceProvider(unittest.TestCase):
    def setUp(self):
        self.provider = ServiceProvider()

    def test_normalizes_defaults(self):
        result = self.provider.generate(build({"name": "web", "port": 8080}))
        service = result.artifacts[0].content["service"]
        self.assertEqual(service["name"], "web")
        self.assertEqual(service["version"], "0.1.0")
        self.assertEqual(service["image"], "web:0.1.0")
        self.assertEqual(service["environment"], "development")
        self.assertEqual(service["replicas"], 1)
        self.assertEqual(service["labels"], {})
        self.assertEqual(
            service["health_check"],
            {"path": "/healthz", "interval_seconds": 10, "timeout_seconds": 5},
        )

    def test_coerces_numeric_strings_and_lowercases_environment(self):
        result = self.provider.generate(
            build({"name": "web", "port": "8080", "replicas": "3", "environment": "PRODUCTION"})
        )
        service = result.artifacts[0].content["service"]
        self.assertEqual(service["port"], 8080)
        self.assertEqual(service["replicas"], 3)
        self.assertEqual(service["environment"], "production")

    def test_accepts_flat_and_nested_documents(self):
        flat = self.provider.generate(build({"name": "web", "port": 80})).artifacts[0].content
        nested = self.provider.generate(
            build({"service": {"name": "web", "port": 80}})
        ).artifacts[0].content
        self.assertEqual(flat, nested)

    def test_explicit_image_is_respected(self):
        result = self.provider.generate(
            build({"name": "web", "port": 80, "image": "registry/web:latest"})
        )
        self.assertEqual(result.artifacts[0].content["service"]["image"], "registry/web:latest")

    def test_labels_are_normalized_to_strings(self):
        result = self.provider.generate(
            build({"name": "web", "port": 80, "labels": {"count": 3, "tier": "api"}})
        )
        self.assertEqual(
            result.artifacts[0].content["service"]["labels"], {"count": "3", "tier": "api"}
        )

    def test_missing_required_fields_are_reported(self):
        errors = self.provider.validate(build({"environment": "staging"}))
        self.assertIn("missing required field: 'service.name'", errors)
        self.assertIn("missing required field: 'service.port'", errors)

    def test_port_range_error_is_useful(self):
        errors = self.provider.validate(build({"name": "web", "port": 99999}))
        self.assertEqual(errors, ("port must be between 1 and 65535, got 99999",))

    def test_unknown_fields_are_rejected(self):
        errors = self.provider.validate(build({"name": "web", "port": 80, "bogus": True}))
        self.assertIn("unknown field: 'service.bogus'", errors)

    def test_invalid_environment_is_reported(self):
        errors = self.provider.validate(
            build({"name": "web", "port": 80, "environment": "prod"})
        )
        self.assertEqual(
            errors,
            ("environment must be one of development, staging, production, got 'prod'",),
        )

    def test_health_check_validation(self):
        errors = self.provider.validate(
            build(
                {
                    "name": "web",
                    "port": 80,
                    "health_check": {"path": "healthz", "interval_seconds": 0, "extra": 1},
                }
            )
        )
        self.assertIn("health_check.path must start with '/', got 'healthz'", errors)
        self.assertIn("interval_seconds must be between 1 and 86400, got 0", errors)
        self.assertIn("unknown field: 'service.health_check.extra'", errors)

    def test_diagnose_returns_structured_diagnostics(self):
        diagnostics = self.provider.diagnose(build({"port": 99999, "environment": "prod"}))
        self.assertTrue(all(isinstance(item, Diagnostic) for item in diagnostics))
        by_field = {item.field: item for item in diagnostics}
        self.assertEqual(by_field["service.name"].message, "missing required field: 'service.name'")
        self.assertEqual(by_field["service.port"].severity, "error")
        self.assertEqual(by_field["service.environment"].field, "service.environment")

    def test_generate_raises_on_invalid_input(self):
        with self.assertRaises(ValueError) as ctx:
            self.provider.generate(build({"name": "web", "port": 0}))
        self.assertIn("port must be between 1 and 65535", str(ctx.exception))

    def test_yaml_output_uses_media_type_and_name(self):
        result = self.provider.generate(build({"name": "web", "port": 80}, format="yaml"))
        artifact = result.artifacts[0]
        self.assertEqual(artifact.media_type, "application/yaml")
        self.assertEqual(artifact.name, "service.yaml")

    def test_explicit_name_overrides_default(self):
        result = self.provider.generate(build({"name": "web", "port": 80}, name="custom.json"))
        self.assertEqual(result.artifacts[0].name, "custom.json")

    def test_validate_returns_tuple(self):
        self.assertIsInstance(self.provider.validate(build({"name": "web", "port": 80})), tuple)

    def test_describe_schema_returns_steps_with_fields(self):
        steps = self.provider.describe_schema()
        self.assertGreaterEqual(len(steps), 2)
        field_names = {field.name for step in steps for field in step.fields}
        self.assertIn("service.name", field_names)
        self.assertIn("service.port", field_names)


if __name__ == "__main__":
    unittest.main()
