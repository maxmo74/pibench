import csv
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import pibench_db
import pibench_report
from scripts import public_release_audit


class PublicProtocolTests(unittest.TestCase):
    def test_point_export_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory, closing(
            pibench_db.connect(Path(directory) / "test.sqlite")
        ) as conn:
            conn.execute(
                "INSERT INTO runs(id,run_uuid,benchmark_name,benchmark_version,started_at,ended_at) "
                "VALUES(1,'test','challenge-candidate',1,'2026-01-01','2026-01-01')"
            )
            conn.execute(
                "INSERT INTO models(id,model_id,model_arg) VALUES(1,'test','test/test:low')"
            )
            artifacts = [{"filename": "test.gguf", "size_bytes": 123, "sha256": "a" * 64}]
            metadata = {
                "protocol_id": "challenge-v1",
                "model_files": artifacts,
                "model_size_bytes": 123,
                "not_public": "PRIVATE_VALUE_PLACEHOLDER",
            }
            conn.execute(
                "INSERT INTO run_models(id,run_id,model_id,inference_json) VALUES(1,1,1,?)",
                (json.dumps({"public_metadata": metadata}),),
            )
            task = pibench_db.upsert_task(
                conn, "challenge-v1/leases", "", "protocol-points", "coding"
            )
            pibench_db.insert_result(conn, 1, 1, task, {
                "ok": False, "score": 17.5, "total": 19, "wall_s": 1,
                "checks": {"public_metadata": {
                    "normal_completion": False, "artifact_score": 17.5,
                }},
            })
            conn.execute(
                "INSERT INTO public_run_metadata VALUES(1,?,?)",
                (json.dumps({"max_output_label": "16K"}), "published-schema-1"),
            )

            output = Path(directory) / "RESULTS.csv"
            pibench_report.export_public_csv(conn, output)
            with output.open() as stream:
                row = next(csv.DictReader(stream))

            self.assertEqual(row["csv_schema_version"], "2")
            self.assertEqual(float(row["run_weighted_score"]), 17.5)
            self.assertEqual(float(row["run_weighted_total"]), 19)
            self.assertEqual(row["protocol_id"], "challenge-v1")
            self.assertEqual(row["max_output"], "16K")
            self.assertIsNone(conn.execute(
                "SELECT max_output_label FROM models WHERE id=1"
            ).fetchone()[0])
            self.assertEqual(json.loads(row["model_files"]), artifacts)
            self.assertEqual(row["normal_completion"], "false")
            self.assertNotIn("PRIVATE_VALUE_PLACEHOLDER", output.read_text())
            self.assertEqual(public_release_audit.audit_csv(output, None), [])
            self.assertNotIn("test/test:low", pibench_report.generate(conn))

            row["model_files"] = json.dumps([{
                "filename": "../PRIVATE_PATH_PLACEHOLDER.gguf",
                "size_bytes": 123, "sha256": "a" * 64,
            }])
            with output.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=pibench_report.CSV_FIELDS)
                writer.writeheader()
                writer.writerow(row)
            self.assertTrue(public_release_audit.audit_csv(output, None))

    def test_private_metadata_refused(self):
        with self.assertRaises(ValueError):
            pibench_report.public_text({
                "filename": "/tmp/PRIVATE_PATH_PLACEHOLDER/model.gguf",
            })
