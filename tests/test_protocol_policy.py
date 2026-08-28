import unittest

import pi_agent_bench
import pi_agent_reliability_bench


class ProtocolPolicyTest(unittest.TestCase):
    def test_pi_upgrade_does_not_renumber_score_protocol(self):
        self.assertEqual(4, pi_agent_bench.BENCHMARK_PROTOCOL_VERSION)
        self.assertEqual("0.84.3", pi_agent_bench.REQUIRED_PI_VERSION)
        self.assertEqual("pi-agent-fixed-cwd", pi_agent_bench.CANONICAL_PROMPT_PROFILE)

    def test_reliability_runner_has_one_current_profile(self):
        self.assertEqual("pi-agent-reliability", pi_agent_reliability_bench.PROFILE)
        self.assertEqual("0.84.3", pi_agent_reliability_bench.REQUIRED_PI_VERSION)


if __name__ == "__main__":
    unittest.main()
