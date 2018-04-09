import unittest

from jupyter_remote.config_manager import generate_config_file


class TestConfigManager(unittest.TestCase):
    def test_generate_config(self):
        self.assertIsInstance(
            generate_config_file("/tmp"),
            str
        )
