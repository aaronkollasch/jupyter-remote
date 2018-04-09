import unittest
try:
    from unittest import mock
except ImportError:
    import mock
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from jupyter_remote.jupyter_remote import JupyterRemote
from tests.test_pysectools import MockStringIO


class TestJupyterRemote(unittest.TestCase):
    @mock.patch('os.isatty')
    @mock.patch('sys.stdout', new=MockStringIO())
    def test_jupyter_remote_init(self, isatty):
        isatty.return_value = True
        self.assertIsInstance(JupyterRemote(), JupyterRemote)
