import unittest


class ImportTests(unittest.TestCase):
    def test_local_modules_import_without_external_runtime(self):
        import chia_work.actions  # noqa: F401
        import chia_work.agentic_loop  # noqa: F401
        import chia_work.chia_adapter  # noqa: F401
        import chia_work.gemini_agent  # noqa: F401
        import chia_work.gemmini_adapter  # noqa: F401
        import chia_work.gemmini_mvin_mvout  # noqa: F401
        import chia_work.gemmini_sanity  # noqa: F401
        import chia_work.runner  # noqa: F401
        import chia_work.safety  # noqa: F401
        import chia_work.structured_log  # noqa: F401
        import chia_work.variants  # noqa: F401


if __name__ == "__main__":
    unittest.main()
