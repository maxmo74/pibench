from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pi_agent_bench
import pibench_db
import pibench_report
from pibench_sandbox import (
    BUBBLEWRAP,
    SEATBELT,
    SandboxUnavailable,
    backend_details,
    limit_gaps,
    resolve_backend,
    run_python_source,
    seatbelt_available,
)
from scripts import public_release_audit


def _sandbox_present() -> bool:
    try:
        resolve_backend()
    except SandboxUnavailable:
        return False
    return True


SANDBOX_PRESENT = _sandbox_present()
BACKEND = resolve_backend() if SANDBOX_PRESENT else None


class ModelMetadataTests(unittest.TestCase):
    def test_model_config_follows_isolated_agent_without_home_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            default_agent = home / ".pi/agent"
            default_agent.mkdir(parents=True)
            isolated = Path(tmp) / "isolated"
            isolated.mkdir()
            config = {"providers": {"fixture": {"models": [{"id": "test-model"}]}}}
            (default_agent / "models.json").write_text(json.dumps(config))
            with mock.patch.object(Path, "home", return_value=home):
                with mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": ""}):
                    result = pibench_db.read_models_config("fixture", "test-model")
                    self.assertEqual(result["config_path"], str(default_agent / "models.json"))
                with mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(isolated)}):
                    self.assertEqual(pibench_db.read_models_config("fixture", "test-model"), {})
                    (isolated / "models.json").write_text(json.dumps(config))
                    result = pibench_db.read_models_config("fixture", "test-model")
                    self.assertEqual(result["config_path"], str(isolated / "models.json"))

    def test_model_config_refuses_relative_agent_override(self) -> None:
        with mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": "relative"}):
            with self.assertRaisesRegex(RuntimeError, "absolute path"):
                pibench_db.read_models_config("fixture", "test-model")

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


@unittest.skipUnless(SANDBOX_PRESENT, "no sandbox backend (bwrap or macOS seatbelt) available")
class GeneratedCodeSandboxTests(unittest.TestCase):
    """Backend-agnostic containment tests.

    Assertions check the security property -- the secret is not visible and the
    file is not created -- rather than a specific exception type, because
    bubblewrap hides paths (FileNotFoundError) while seatbelt exposes them but
    denies access (PermissionError). Both satisfy the requirement.
    """

    def test_a_sandbox_backend_is_selected(self) -> None:
        self.assertIn(BACKEND, (BUBBLEWRAP, SEATBELT))

    def test_generated_code_cannot_read_host_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / "host-secret"
            secret.write_text("SHOULD_NOT_BE_VISIBLE")
            source = f"""from pathlib import Path
try:
    print(Path({str(secret)!r}).read_text())
except Exception as exc:
    print("READ_DENIED", type(exc).__name__)
"""
            proc = run_python_source(source)
            self.assertNotIn("SHOULD_NOT_BE_VISIBLE", proc.stdout)
            self.assertIn("READ_DENIED", proc.stdout)

    def test_generated_code_cannot_read_user_home(self) -> None:
        source = """import os
from pathlib import Path
home = Path.home()
try:
    names = [p.name for p in home.iterdir()]
    print("HOME_VISIBLE", names[:3])
except Exception as exc:
    print("HOME_HIDDEN", type(exc).__name__)
"""
        proc = run_python_source(source)
        self.assertNotIn("HOME_VISIBLE", proc.stdout)
        self.assertIn("HOME_HIDDEN", proc.stdout)

    def test_generated_code_cannot_write_host_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "escaped"
            source = f"""from pathlib import Path
try:
    Path({str(target)!r}).write_text("escaped")
except Exception as exc:
    print("WRITE_DENIED", type(exc).__name__)
"""
            proc = run_python_source(source)
            self.assertFalse(target.exists())
            self.assertIn("WRITE_DENIED", proc.stdout)

    def test_nested_subprocess_is_also_contained(self) -> None:
        source = """import subprocess
proc = subprocess.run(['/bin/cat', str(__import__('pathlib').Path.home() / '.ssh' / 'config')],
                      capture_output=True, text=True)
print('CHILD_RC', proc.returncode)
"""
        proc = run_python_source(source)
        self.assertIn("CHILD_RC 1", proc.stdout)

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


class SandboxProvenanceTests(unittest.TestCase):
    """The chosen backend must always be distinguishable in recorded results.

    Seatbelt is a weaker lane than bubblewrap, so a seatbelt-scored result must
    never be silently ranked against a bubblewrap-scored one.
    """

    def test_provenance_names_backend_and_isolation_strength(self) -> None:
        if not SANDBOX_PRESENT:
            self.skipTest("no sandbox backend available")
        details = backend_details()
        self.assertEqual(details["sandbox_backend"], BACKEND)
        self.assertIn(details["isolation_strength"], ("namespaces", "best-effort", "none"))

    @unittest.skipUnless(BACKEND == SEATBELT, "seatbelt backend not selected")
    def test_seatbelt_provenance_declares_its_weaknesses(self) -> None:
        details = backend_details()
        self.assertEqual(details["isolation_strength"], "best-effort")
        limitations = " ".join(details["sandbox_limitations"])
        for gap in ("mount namespace", "pid namespace", "not a security boundary"):
            self.assertIn(gap, limitations)

    @unittest.skipUnless(BACKEND == SEATBELT, "seatbelt backend not selected")
    def test_seatbelt_reports_unsupported_memory_limits(self) -> None:
        # macOS refuses finite RLIMIT_AS/RLIMIT_DATA; the gap must be visible,
        # not silently downgraded to "contained".
        self.assertIn("RLIMIT_AS", limit_gaps())
        self.assertIn(
            "no per-process memory cap",
            " ".join(backend_details()["sandbox_limitations"]),
        )

    def test_bubblewrap_is_preferred_over_seatbelt(self) -> None:
        if not seatbelt_available():
            self.skipTest("seatbelt not available on this host")
        with mock.patch.dict(os.environ, {"PATH": os.environ.get("PATH", "")}):
            with mock.patch("pibench_sandbox.shutil.which", lambda name: "/usr/bin/bwrap"):
                self.assertEqual(resolve_backend(), BUBBLEWRAP)

    def test_unsafe_fallback_reports_no_isolation(self) -> None:
        with mock.patch.dict(os.environ, {"PIBENCH_ALLOW_UNSANDBOXED_EXEC": "1"}):
            self.assertEqual(backend_details()["isolation_strength"], "none")


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

    def test_public_blob_rejects_bearer_and_npm_tokens(self) -> None:
        bearer = b"Authorization: " + b"Bearer " + b"a" * 32
        npm = b"npm" + b"_" + b"b" * 36
        self.assertTrue(public_release_audit.check_blob("example.txt", bearer))
        self.assertTrue(public_release_audit.check_blob("example.txt", npm))

    def test_database_reexport_uses_row_connection(self) -> None:
        csv_path = Path(__file__).resolve().parents[1] / "RESULTS.csv"
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "fixture.sqlite"
            sqlite3.connect(database).close()

            def fake_export(connection, output):
                self.assertIs(connection.row_factory, sqlite3.Row)
                shutil.copyfile(csv_path, output)

            with mock.patch.object(pibench_report, "export_public_csv", side_effect=fake_export):
                self.assertEqual(public_release_audit.audit_csv(csv_path, database), [])


if __name__ == "__main__":
    unittest.main()
