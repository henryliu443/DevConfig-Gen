import json
import tempfile
import unittest
from pathlib import Path

from devconfig_gen import GenerationRequest, generate
from devconfig_gen.cli import build_parser


class TestDevConfigCore(unittest.TestCase):
    def test_json_provider_generates_and_persists_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate("json", GenerationRequest(context={"app": {"enabled": True}}), output_dir=directory)
            output = Path(directory) / "config.json"
            self.assertEqual(result.provider, "json")
            self.assertEqual(json.loads(output.read_text()), {"app": {"enabled": True}})

    def test_json_provider_unwraps_document_key(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate(
                "json",
                GenerationRequest(context={"document": {"app": {"enabled": True}}}),
                output_dir=directory,
            )
            output = Path(directory) / "config.json"
            self.assertEqual(result.provider, "json")
            self.assertEqual(json.loads(output.read_text()), {"app": {"enabled": True}})

    def test_registry_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ValueError, "unknown provider"):
            generate("missing", GenerationRequest())

    def test_artifact_cannot_escape_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            request = GenerationRequest(context={}, options={"name": "../outside.json"})
            with self.assertRaisesRegex(ValueError, "escapes output directory"):
                generate("json", request, output_dir=directory)

    def test_cli_is_provider_oriented(self):
        args = build_parser().parse_args(["generate", "--input", "in.json", "--output-dir", "out"])
        self.assertEqual(args.provider, "json")
