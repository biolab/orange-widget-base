import os
import unittest
from unittest.mock import Mock
from tempfile import NamedTemporaryFile

from orangewidget.utils.filedialogs import RecentPath, open_filename_dialog


class TestRecentPath(unittest.TestCase):
    def test_resolve(self):
        temp_file = NamedTemporaryFile(dir=os.getcwd(), delete=False)
        file_name = temp_file.name
        temp_file.close()
        base_name = os.path.basename(file_name)
        try:
            recent_path = RecentPath(
                os.path.join("temp/datasets", base_name), "",
                os.path.join("datasets", base_name)
            )
            search_paths = [("basedir", os.getcwd())]
            self.assertIsNotNone(recent_path.resolve(search_paths))
        finally:
            os.remove(file_name)


class TestOpenFilenameDialog(unittest.TestCase):
    def test_empty_filter(self):
        class ABCFormat:
            EXTENSIONS = ('.abc', '.jkl')
            DESCRIPTION = 'abc file'
            PRIORITY = 30

        name, file_format, file_filter = open_filename_dialog(
            ".", "", [ABCFormat],
            dialog=Mock(return_value=("foo.xyz", "")))
        self.assertEqual(name, "foo.xyz")
        self.assertEqual(file_format, None)
        self.assertEqual(file_filter, None)


if __name__ == "__main__":
    unittest.main()
