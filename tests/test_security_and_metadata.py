from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pi_agent_bench
import pibench_db
import pibench_report
from pibench_sandbox import run_python_source
from scripts import public_release_audit


class ModelMetadataTests(unittest.TestCase):
    def test_pi_table_parser_accepts_model_ids_with_spaces(self) -> None:
        table = """provider     model        context  max-out  thinking  images
local-llama  Road Runner  131.1K   4.1K     yes       no
"""
        with mock.patch.object(pibench_db, "run_cmd", return_value=table):
            result = pibench_db.parse_pi_list_models("Road Runner")
        self.assertEqual(result["provider"], "local-llama")
        self.assertEqual(result["model_id"], "Road Runner")
        self.assertEqual(result["context"], "131.1K")
        self.assertEqual(result["max_out"], "4.1K")

    def test_explicit_server_path_must_name_a_real_llama_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wrong = Path(tmp) / "server"
            wrong.write_text("")
            model = {"metadata": {"llamaServerPath": str(wrong)}}
            self.assertIsNone(pibench_db.infer_llama_server_path("local-llama", {}, model, "model"))

            server = Path(tmp) / "llama-server"
            server.write_text("")
            model["metadata"]["llamaServerPath"] = str(server)
            self.assertEqual(
                pibench_db.infer_llama_server_path("local-llama", {}, model, "model"),
                str(server),
            )


@unittest.skipUnless(shutil.which("bwrap"), "Bubblewrap is not installed")
class GeneratedCodeSandboxTests(unittest.TestCase):
    def test_generated_code_cannot_read_host_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / "host-secret"
            secret.write_text("SHOULD_NOT_BE_VISIBLE")
            source = f"""from pathlib import Path
try:
    print(Path({str(secret)!r}).read_text())
except Exception as exc:
    print(type(exc).__name__)
"""
            proc = run_python_source(source)
            self.assertNotIn("SHOULD_NOT_BE_VISIBLE", proc.stdout)
            self.assertIn("FileNotFoundError", proc.stdout)

    def test_generated_code_cannot_write_host_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "escaped"
            source = f"""from pathlib import Path
try:
    Path({str(target)!r}).write_text("escaped")
except Exception as exc:
    print(type(exc).__name__)
"""
            proc = run_python_source(source)
            self.assertFalse(target.exists())
            self.assertIn("FileNotFoundError", proc.stdout)

    def test_generated_code_cannot_reach_loopback_network(self) -> None:
        source = """import socket
sock = socket.socket()
try:
    sock.connect(("127.0.0.1", 8080))
    print("NETWORK_OPEN")
except OSError:
    print("NETWORK_BLOCKED")
"""
        proc = run_python_source(source)
        self.assertIn("NETWORK_BLOCKED", proc.stdout)
        self.assertNotIn("NETWORK_OPEN", proc.stdout)

    def test_standard_library_and_stdin_work(self) -> None:
        proc = run_python_source(
            "import json, sys; print(json.dumps({'input': sys.stdin.read()}))",
            input_text="hello",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"input": "hello"', proc.stdout)


class ExtensionAttestationTests(unittest.TestCase):
    def make_agent_dir(self, root: Path, version: str = "0.3.1") -> Path:
        agent = root / "agent"
        extension = agent / "npm" / "node_modules" / "pi-antigravity"
        stream = extension / "src" / "stream"
        stream.mkdir(parents=True)
        (extension / "package.json").write_text(json.dumps({"version": version}))
        (stream / "stream.ts").write_text("\n".join(pi_agent_bench.ANTIGRAVITY_SOURCE_FRAGMENTS))
        return agent

    def test_attestation_follows_absolute_agent_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent_dir(Path(tmp))
            with mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(agent)}):
                result = pi_agent_bench.attest_antigravity_profile()
        self.assertEqual(result["antigravity_extension_version"], "0.3.1")
        self.assertEqual(result["antigravity_injection_sha256"], pi_agent_bench.ANTIGRAVITY_INJECTION_SHA256)

    def test_relative_agent_override_is_refused(self) -> None:
        with mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": "relative"}):
            with self.assertRaisesRegex(RuntimeError, "absolute path"):
                pi_agent_bench.attest_antigravity_profile()

    def test_wrong_extension_version_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent_dir(Path(tmp), version="0.4.1")
            with self.assertRaisesRegex(RuntimeError, "pinned"):
                pi_agent_bench.attest_antigravity_profile(agent)


class PublicExportSafetyTests(unittest.TestCase):
    def test_public_text_blocks_private_markers_and_escapes_formulas(self) -> None:
        self.assertEqual(pibench_report.public_text("=1+1"), "'=1+1")
        with self.assertRaises(ValueError):
            pibench_report.public_text("/" + "home/example/private")
        with self.assertRaises(ValueError):
            pibench_report.public_text("person@example.com")

    def test_public_url_strips_credentials_query_and_fragment(self) -> None:
        self.assertEqual(
            pibench_report.public_url("https://user" + ":pass@example.com/path?q=secret#fragment"),
            "https://example.com/path",
        )

    def test_public_url_refuses_private_and_non_http_hosts(self) -> None:
        for value in (
            "http://127.0.0.1/private",
            "http://localhost/private",
            "https://service.internal/path",
            "file:///tmp/report",
        ):
            self.assertEqual(pibench_report.public_url(value), "")

    def test_public_path_policy_rejects_raw_artifacts(self) -> None:
        self.assertTrue(public_release_audit.check_public_path("results/raw.json"))
        self.assertTrue(public_release_audit.check_public_path("weights/model.gguf"))
        self.assertFalse(public_release_audit.check_public_path("RESULTS.csv"))


if __name__ == "__main__":
    unittest.main()
