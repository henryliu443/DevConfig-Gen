import io
import tempfile
import unittest
from pathlib import Path

from devconfig_gen.interactive import (
    _get_dotted_path,
    _set_dotted_path,
    prompt_field,
    run_interactive_wizard,
)
from devconfig_gen.models import ProviderField


class TestInteractiveWizard(unittest.TestCase):
    def test_dotted_path_helpers(self):
        data = {}
        _set_dotted_path(data, "service.name", "my-api")
        _set_dotted_path(data, "service.networking.port", 8080)
        self.assertEqual(data["service"]["name"], "my-api")
        self.assertEqual(data["service"]["networking"]["port"], 8080)

        self.assertEqual(_get_dotted_path(data, "service.name"), "my-api")
        self.assertEqual(_get_dotted_path(data, "service.networking.port"), 8080)
        self.assertIsNone(_get_dotted_path(data, "service.missing"))

    def test_prompt_field_string_with_default(self):
        field = ProviderField("service.name", type="string", default="default-app")
        reader = io.StringIO("\n")  # press enter
        writer = io.StringIO()
        val = prompt_field(field, None, reader, writer)
        self.assertEqual(val, "default-app")

    def test_prompt_field_integer_bounds(self):
        field = ProviderField("service.port", type="integer", minimum=1, maximum=65535, default=8080)
        # First enters invalid string, then out of bounds, then valid port
        reader = io.StringIO("not_a_num\n99999\n8081\n")
        writer = io.StringIO()
        val = prompt_field(field, None, reader, writer)
        self.assertEqual(val, 8081)
        output = writer.getvalue()
        self.assertIn("Expected integer", output)
        self.assertIn("Value must be <=", output)

    def test_prompt_field_choices(self):
        field = ProviderField(
            "service.env",
            type="string",
            choices=("dev", "staging", "production"),
            default="dev",
        )
        # Select choice 2 (staging)
        reader = io.StringIO("2\n")
        writer = io.StringIO()
        val = prompt_field(field, None, reader, writer)
        self.assertEqual(val, "staging")

    def test_prompt_field_boolean(self):
        field = ProviderField("service.tls", type="boolean", default=False)
        reader = io.StringIO("y\n")
        writer = io.StringIO()
        val = prompt_field(field, None, reader, writer)
        self.assertTrue(val)

    def test_run_interactive_wizard_full_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Inputs matching the service provider fields:
            # Step 1: name=auth-svc, version [0.1.0], image (empty)
            # Step 2: port=9000, environment (1: development), replicas [1]
            # Step 3: labels (empty), health path [/healthz], interval [10], timeout [5]
            # Output format: 1 (yaml)
            inputs = "\n".join([
                "auth-svc",  # service.name
                "1.2.0",     # service.version
                "",          # service.image (default)
                "9000",      # service.port
                "1",         # environment (development)
                "2",         # replicas
                "",          # labels (empty line finishes mapping)
                "",          # health_check.path (default)
                "",          # health_check.interval_seconds (default)
                "",          # health_check.timeout_seconds (default)
                "1",         # format selection (YAML)
            ]) + "\n"

            reader = io.StringIO(inputs)
            writer = io.StringIO()

            code = run_interactive_wizard(
                "service",
                output_dir=tmpdir,
                output_format="yaml",
                reader=reader,
                writer=writer,
            )
            self.assertEqual(code, 0)

            out_file = Path(tmpdir) / "service.yaml"
            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("name: auth-svc", content)
            self.assertIn("version: 1.2.0", content)
            self.assertIn("port: 9000", content)

    def test_run_interactive_wizard_unknown_provider(self):
        reader = io.StringIO("")
        writer = io.StringIO()
        code = run_interactive_wizard("unknown_provider", reader=reader, writer=writer)
        self.assertEqual(code, 1)
        self.assertIn("Error: unknown provider", writer.getvalue())

    def test_wizard_preserves_answers_when_retrying(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # The terminal prompt accepts 'healthz', but the provider requires a
            # leading slash, so the first pass fails validation. The second pass
            # accepts every pre-filled default except the corrected path.
            inputs = "\n".join([
                "auth-svc",  # name
                "",          # version (default)
                "",          # image (optional, skipped)
                "8080",      # port (valid)
                "",          # environment (default)
                "",          # replicas (default)
                "",          # labels (finish)
                "healthz",   # health path INVALID (missing leading slash)
                "",          # interval (default)
                "",          # timeout (default)
                "y",         # re-run to correct
                "",          # name (pre-filled)
                "",          # version (pre-filled)
                "",          # image (still unset)
                "",          # port (pre-filled)
                "",          # environment (pre-filled)
                "",          # replicas (pre-filled)
                "",          # labels (pre-filled, finish)
                "/healthz",  # health path corrected
                "",          # interval (pre-filled)
                "",          # timeout (pre-filled)
            ]) + "\n"

            writer = io.StringIO()
            code = run_interactive_wizard(
                "service",
                output_dir=tmpdir,
                output_format="yaml",
                reader=io.StringIO(inputs),
                writer=writer,
            )
            self.assertEqual(code, 0)
            self.assertIn("pre-filled", writer.getvalue())
            content = (Path(tmpdir) / "service.yaml").read_text(encoding="utf-8")
            self.assertIn("name: auth-svc", content)
            self.assertIn("port: 8080", content)

    def test_wizard_retry_can_be_declined(self):
        inputs = "auth-svc\n\n\n8080\n\n\n\nhealthz\n\n\nn\n"
        writer = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            code = run_interactive_wizard(
                "service",
                output_dir=tmpdir,
                output_format="yaml",
                reader=io.StringIO(inputs),
                writer=writer,
            )
        self.assertEqual(code, 1)
        self.assertIn("Aborted", writer.getvalue())

    def test_wizard_aborts_cleanly_on_end_of_input(self):
        writer = io.StringIO()
        code = run_interactive_wizard(
            "service",
            output_format="yaml",
            reader=io.StringIO(""),  # immediate EOF
            writer=writer,
        )
        self.assertEqual(code, 1)
        self.assertIn("Input ended", writer.getvalue())
