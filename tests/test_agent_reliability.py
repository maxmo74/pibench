from __future__ import annotations

import unittest

import pi_agent_reliability_bench as reliability


def assistant_event(text: str, stop_reason: str = "stop") -> dict:
    return {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "stopReason": stop_reason,
            "content": [{"type": "text", "text": text}],
        },
    }


class ReliabilityEventAnalysisTests(unittest.TestCase):
    def analyze(self, events: list[dict], semantic: bool = True, **kwargs) -> dict:
        return reliability.analyze_events(
            events,
            returncode=kwargs.get("returncode", 0),
            timed_out=kwargs.get("timed_out", False),
            wall_s=1.0,
            semantic_check=lambda _text: {"fixture_answer": semantic},
        )

    def test_normal_tool_use_and_final_answer_pass(self) -> None:
        events = [
            assistant_event("I will inspect the relevant configuration once.", "toolUse"),
            {"type": "tool_execution_start", "toolName": "read", "args": {"path": "service/app.py"}},
            assistant_event(
                "The health check probes port 8080 while the service listens on port 9000. "
                "Update the health-check URL to port 9000 so both configurations agree."
            ),
        ]
        result = self.analyze(events)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["metrics"]["tool_calls"], 1)
        self.assertEqual(result["metrics"]["non_normal_stop_reasons"], [])

    def test_duplicate_tool_call_fails_gate(self) -> None:
        call = {"type": "tool_execution_start", "toolName": "read", "args": {"path": "README.md"}}
        result = self.analyze([
            assistant_event("Checking the documentation before deciding what evidence is available.", "toolUse"),
            call,
            assistant_event("I will check that exact documentation one more time before answering.", "toolUse"),
            call,
            assistant_event(
                "The available documentation is insufficient to establish an exact cause. "
                "Provide the rotated incident log and corresponding service metrics."
            ),
        ])
        self.assertFalse(result["passed"])
        self.assertIn("no_duplicate_tools", result["failed_gates"])
        self.assertEqual(result["metrics"]["duplicate_tool_uses"], 1)

    def test_repeated_output_block_fails_gate(self) -> None:
        repeated = (
            "This investigation is still continuing because the same evidence has not changed at all. "
            "The model should stop rather than restating this identical paragraph again."
        )
        result = self.analyze([assistant_event("\n".join([repeated] * 4))])
        self.assertFalse(result["passed"])
        self.assertIn("no_repeated_lines", result["failed_gates"])
        self.assertIn("no_repeated_text_blocks", result["failed_gates"])

    def test_timeout_and_missing_final_fail(self) -> None:
        result = self.analyze([], returncode=-1, timed_out=True)
        self.assertFalse(result["passed"])
        self.assertIn("process_completed", result["failed_gates"])
        self.assertIn("normal_final", result["failed_gates"])

    def test_semantic_failure_is_separate_from_loop_safety(self) -> None:
        result = self.analyze([
            assistant_event(
                "The run completed cleanly without repetition, but this deliberately generic answer "
                "does not identify the fixture's expected root cause or minimal correction."
            )
        ], semantic=False)
        self.assertFalse(result["passed"])
        self.assertIn("semantic_checks", result["failed_gates"])
        self.assertTrue(result["gates"]["no_duplicate_tools"])
        self.assertTrue(result["gates"]["no_repeated_text_blocks"])


class ReliabilityFixtureTests(unittest.TestCase):
    def test_context_preamble_stays_below_linux_single_argument_limit(self) -> None:
        encoded = reliability.context_preamble().encode()
        self.assertGreater(len(encoded), 100_000)
        self.assertLess(len(encoded), 125_000)

    def test_focus_semantic_check_requires_cause_and_fix(self) -> None:
        answer = (
            "syncNavigationState runs after every document click and derives aria-selected from "
            "document.activeElement. Focusing the hamburger therefore clears the tab state. "
            "Use the stable active class instead, or limit synchronization to a tab click."
        )
        self.assertTrue(all(reliability.check_focus_state(answer).values()))
        self.assertFalse(all(reliability.check_focus_state("It is probably a CSS problem.").values()))

    def test_missing_evidence_check_rewards_stopping(self) -> None:
        answer = (
            "The exact cause cannot be determined from these files. The rotated worker.log.1 and "
            "incident-window queue metrics are missing, so obtain those artifacts before diagnosing."
        )
        self.assertTrue(all(reliability.check_missing_evidence(answer).values()))


if __name__ == "__main__":
    unittest.main()
