import json
import tempfile
import unittest
from pathlib import Path

from devconfig_gen import GenerationRequest, generate
from devconfig_gen.providers import CustomProvider


def build(context, **options):
    return GenerationRequest(context=context, options=options)


class TestCustomProvider(unittest.TestCase):
    def setUp(self):
        self.provider = CustomProvider()

    def test_name_and_schema(self):
        self.assertEqual(self.provider.name, "custom")
        steps = self.provider.describe_schema()
        self.assertEqual(steps[0].id, "document")
        self.assertEqual(steps[0].fields[0].type, "tree")
        self.assertFalse(steps[0].fields[0].required)

    def test_accepts_arbitrary_nesting(self):
        context = {
            "document": {
                "app": {
                    "name": "web",
                    "tags": ["a", "b"],
                    "limits": {"cpu": "500m", "memory": "512Mi"},
                    "enabled": True,
                    "retries": 3,
                    "nothing": None,
                }
            }
        }
        self.assertEqual(self.provider.validate(build(context)), ())
        result = self.provider.generate(build(context))
        artifact = result.artifacts[0]
        self.assertEqual(artifact.name, "custom.json")
        self.assertEqual(artifact.content, context["document"])

    def test_unwraps_document_key(self):
        result = self.provider.generate(build({"document": {"a": 1}}))
        self.assertEqual(result.artifacts[0].content, {"a": 1})

    def test_accepts_bare_mapping_without_wrapper(self):
        result = self.provider.generate(build({"a": {"b": 1}}))
        self.assertEqual(result.artifacts[0].content, {"a": {"b": 1}})

    def test_accepts_top_level_list_root(self):
        result = self.provider.generate(build({"document": [1, 2, 3, 4, 5]}))
        self.assertEqual(result.artifacts[0].content, [1, 2, 3, 4, 5])
        self.assertEqual(self.provider.validate(build({"document": [1, 2, 3]})), ())

    def test_yaml_output_name_and_media_type(self):
        result = self.provider.generate(build({"document": {"a": 1}}, format="yaml"))
        artifact = result.artifacts[0]
        self.assertEqual(artifact.name, "custom.yaml")
        self.assertEqual(artifact.media_type, "application/yaml")

    def test_custom_name_overrides_default(self):
        result = self.provider.generate(build({"document": {"a": 1}}, name="mine.json"))
        self.assertEqual(result.artifacts[0].name, "mine.json")

    def test_persists_arbitrary_document(self):
        with tempfile.TemporaryDirectory() as directory:
            context = {"document": {"root": {"nested": {"deep": [1, 2, 3]}}}}
            generate("custom", build(context), output_dir=directory)
            output = Path(directory) / "custom.json"
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                {"root": {"nested": {"deep": [1, 2, 3]}}},
            )


if __name__ == "__main__":
    unittest.main()
