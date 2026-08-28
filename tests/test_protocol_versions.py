import unittest

import pi_agent_bench
import pi_agent_bench_v5


class ProtocolVersionTest(unittest.TestCase):
    def test_runners_have_distinct_versions(self):
        self.assertEqual(4, pi_agent_bench.BENCHMARK_PROTOCOL_VERSION)
        self.assertEqual(5, pi_agent_bench_v5.BENCHMARK_PROTOCOL_VERSION)


if __name__ == "__main__":
    unittest.main()
