from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


RUNNER = Path(__file__).resolve().parents[1] / "run-validation-step.sh"


class RunValidationStepTest(unittest.TestCase):
    def test_interrupt_records_terminal_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "evidence"
            process = subprocess.Popen(
                [
                    RUNNER,
                    output_dir,
                    "interrupted-step",
                    "artifact.log",
                    "--",
                    "bash",
                    "-lc",
                    "printf ready; exec sleep 30",
                ],
                start_new_session=True,
            )
            try:
                artifact = output_dir / "artifact.log"
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if artifact.exists() and "ready" in artifact.read_text():
                        break
                    time.sleep(0.01)
                else:
                    self.fail("recorded child command did not become ready")

                os.killpg(process.pid, signal.SIGINT)
                self.assertEqual(process.wait(timeout=5), 130)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)

            steps = [
                json.loads(line)
                for line in (output_dir / "steps.jsonl").read_text().splitlines()
            ]
            self.assertEqual(len(steps), 1)
            self.assertEqual(steps[0]["name"], "interrupted-step")
            self.assertEqual(steps[0]["exit_code"], 130)
            transcript = output_dir / "command-transcript.log"
            self.assertIn("END interrupted-step exit=130", transcript.read_text())


if __name__ == "__main__":
    unittest.main()
