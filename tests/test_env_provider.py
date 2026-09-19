import tempfile
import unittest
from pathlib import Path

from devconfig_gen import GenerationRequest
from devconfig_gen.providers import EnvProvider


def build(context, **options):
    return GenerationRequest(context=context, options=options)


class TestEnvProvider(unittest.TestCase):
    def setUp(self):
        self.provider = EnvProvider()

    def test_flattens_nested_mappings_to_upper_snake_case(self):
        result = self.provider.generate(
            build({"database": {"host": "localhost", "port": 5432}, "debug": True})
        )
        self.assertEqual(
            result.artifacts[0].content,
            "DATABASE_HOST=localhost\nDATABASE_PORT=5432\nDEBUG=true\n",
        )

    def test_scalar_formatting(self):
        result = self.provider.generate(
            build({"enabled": False, "ratio": 0.5, "empty": None, "tags": ["a", "b"]})
        )
        self.assertEqual(
            result.artifacts[0].content,
            "ENABLED=false\nRATIO=0.5\nEMPTY=\nTAGS=a,b\n",
        )

    def test_key_segments_are_sanitized(self):
        result = self.provider.generate(build({"api-key": {"x.y": 1}}))
        self.assertEqual(result.artifacts[0].content, "API_KEY_X_Y=1\n")

    def test_unwraps_variables_mapping(self):
        result = self.provider.generate(build({"variables": {"api": {"key": "secret"}}}))
        self.assertEqual(result.artifacts[0].content, "API_KEY=secret\n")

    def test_artifact_name_and_media_type(self):
        artifact = self.provider.generate(build({"a": 1})).artifacts[0]
        self.assertEqual(artifact.name, ".env")
        self.assertEqual(artifact.media_type, "text/plain")

    def test_custom_name(self):
        artifact = self.provider.generate(build({"a": 1}, name=".env.production")).artifacts[0]
        self.assertEqual(artifact.name, ".env.production")

    def test_non_mapping_is_reported(self):
        errors = self.provider.validate(build(["not", "a", "mapping"]))
        self.assertIn("variables must be a mapping at the document root", errors)

    def test_empty_mapping_is_reported(self):
        errors = self.provider.validate(build({}))
        self.assertIn("variables must not be empty", errors)

    def test_list_of_mappings_is_reported(self):
        errors = self.provider.validate(build({"b": [{"x": 1}]}))
        self.assertIn("b must not contain mappings", errors)

    def test_empty_key_is_reported(self):
        errors = self.provider.validate(build({"": 1}))
        self.assertTrue(any("is not a valid variable name" in message for message in errors))

    def test_generate_raises_on_invalid_input(self):
        with self.assertRaises(ValueError):
            self.provider.generate(build({}))

    def test_describe_schema_exposes_variables_step(self):
        steps = self.provider.describe_schema()
        self.assertEqual(steps[0].id, "variables")
        self.assertEqual(steps[0].fields[0].name, "variables")

    def test_persists_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            from devconfig_gen import generate

            generate(
                "env",
                build({"database": {"host": "db"}}),
                output_dir=directory,
            )
            output = Path(directory) / ".env"
            self.assertEqual(output.read_text(encoding="utf-8"), "DATABASE_HOST=db\n")


if __name__ == "__main__":
    unittest.main()
