import json
import unittest

from devconfig_gen import (
    Diagnostic,
    ProviderField,
    ProviderStep,
    describe_provider,
    diagnose_request,
)
from devconfig_gen.providers import JsonProvider, ServiceProvider


class TestProviderMetadata(unittest.TestCase):
    def test_describe_provider_returns_steps(self):
        steps = describe_provider("service")
        self.assertTrue(all(isinstance(step, ProviderStep) for step in steps))
        step_ids = [step.id for step in steps]
        self.assertEqual(step_ids, ["identity", "runtime", "metadata"])

    def test_provider_fields_expose_constraints(self):
        fields = {
            field.name: field
            for step in describe_provider("service")
            for field in step.fields
        }
        port = fields["service.port"]
        self.assertEqual(port.type, "integer")
        self.assertTrue(port.required)
        self.assertEqual((port.minimum, port.maximum), (1, 65535))
        self.assertEqual(fields["service.environment"].choices, ("development", "staging", "production"))

    def test_step_and_field_serialize_to_json_ready_dicts(self):
        step = ProviderStep(
            id="s",
            title="S",
            description="d",
            fields=(ProviderField("x", type="string", required=True, default="a"),),
        )
        data = step.as_dict()
        self.assertEqual(data["id"], "s")
        self.assertEqual(data["fields"][0]["name"], "x")
        self.assertTrue(data["fields"][0]["required"])
        json.dumps(data)

    def test_json_provider_has_schema(self):
        steps = JsonProvider().describe_schema()
        self.assertEqual(steps[0].id, "document")

    def test_diagnose_request_uses_structured_provider_output(self):
        diagnostics = diagnose_request(
            "service", context={"name": "web", "port": 99999, "extra": 1}
        )
        self.assertTrue(all(isinstance(item, Diagnostic) for item in diagnostics))
        fields = {item.field for item in diagnostics}
        self.assertIn("service.port", fields)
        self.assertIn("service.extra", fields)

    def test_diagnose_request_falls_back_to_messages(self):
        class Minimal:
            name = "minimal"

            def validate(self, request):
                return ("something is wrong",)

            def generate(self, request):  # pragma: no cover - not used here
                raise NotImplementedError

        from devconfig_gen.registry import ProviderRegistry

        registry = ProviderRegistry((Minimal(),))
        diagnostics = diagnose_request("minimal", registry=registry)
        self.assertEqual(diagnostics[0].message, "something is wrong")
        self.assertEqual(diagnostics[0].field, "")

    def test_builtin_providers_registered(self):
        from devconfig_gen.providers import EnvProvider

        from devconfig_gen.registry import default_registry

        self.assertEqual(default_registry.names(), ("env", "json", "service"))
        self.assertIsInstance(default_registry.get("service"), ServiceProvider)
        self.assertIsInstance(default_registry.get("env"), EnvProvider)


if __name__ == "__main__":
    unittest.main()
