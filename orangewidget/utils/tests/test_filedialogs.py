import sys

import os
import unittest
from unittest.mock import Mock
from tempfile import NamedTemporaryFile

from orangewidget.utils.filedialogs import RecentPath, open_filename_dialog, \
    unambiguous_paths


class TestUtils(unittest.TestCase):
    def test_unambiguous_paths(self):
        paths = [
            "asd.txt",
            "abc/def/ghi.txt",
            "abc/def/jkl.txt",
            "abc/xyz/jkl.txt",
            "abc/xyz/rty/qwe.txt",
            "abd/xyz/rty/qwe.txt",
            "abe/xyz/rty/qwe.txt",
        ]

        paths = [t.replace("/", os.path.sep, 1) for t in paths]

        def test(exp, **kwargs):
            self.assertEqual(unambiguous_paths(paths, **kwargs),
                             [t.replace("/", os.path.sep) for t in exp])

        test(["asd.txt",
              "ghi.txt",
              "def/jkl.txt",
              "xyz/jkl.txt",
              "abc/xyz/rty/qwe.txt",
              "abd/xyz/rty/qwe.txt",
              "abe/xyz/rty/qwe.txt"])

        test(["asd.txt",
              "def/ghi.txt",
              "def/jkl.txt",
              "xyz/jkl.txt",
              "abc/xyz/rty/qwe.txt",
              "abd/xyz/rty/qwe.txt",
              "abe/xyz/rty/qwe.txt"], minlevel=2)

        test(["asd.txt",
              "abc/def/ghi.txt",
              "abc/def/jkl.txt",
              "abc/xyz/jkl.txt",
              "abc/xyz/rty/qwe.txt",
              "abd/xyz/rty/qwe.txt",
              "abe/xyz/rty/qwe.txt"], minlevel=3)

        test(["asd.txt",
              "abc/def/ghi.txt",
              "abc/def/jkl.txt",
              "abc/xyz/jkl.txt",
              "abc/xyz/rty/qwe.txt",
              "abd/xyz/rty/qwe.txt",
              "abe/xyz/rty/qwe.txt"], minlevel=4)

        # For simplicity, omit this test on Windows; if it works on Posix paths,
        # it works on Windows, too.
        if os.path.sep == "/":
            t = ["abc/def/ghi.txt", "abc/def/ghi.txt"]
            self.assertEqual(unambiguous_paths(t), t)

    if sys.platform == "win32":
        ptch1 = ptch2 = ptch3 = lambda x: x
    else:
        # This test is intended for Windows, but for easier testing of a test
        # on non-Windows machine, we patch it to make it work on others
        ptch1 = unittest.mock.patch("os.path.sep", "/")
        ptch2 = unittest.mock.patch("os.path.altsep", "\\")
        ptch3 = unittest.mock.patch(
            "os.path.join",
            lambda *args, oj=os.path.join: oj(*args).replace("/", "\\"))
    @ptch1
    @ptch2
    @ptch3
    def test_unambiguous_paths_windows(self):
        paths = ["C:\\Documents/Newsletters\\Summer2018.pdf",
                 "D:\\Documents/Newsletters\\Summer2018.pdf"]
        self.assertEqual(unambiguous_paths(paths),
                         ["C:\\Documents\\Newsletters\\Summer2018.pdf",
                          "D:\\Documents\\Newsletters\\Summer2018.pdf"]
                         )

        paths = ["C:\\abc\\def\\Summer2018.pdf",
                 "C:\\abc\\deg\\Summer2018.pdf"]
        self.assertEqual(unambiguous_paths(paths),
                         ["def\\Summer2018.pdf",
                          "deg\\Summer2018.pdf", ]
                         )

        paths = ["C:\\deg\\Summer2018.pdf",
                 "D:\\deg\\Summer2018.pdf"]
        self.assertEqual(unambiguous_paths(paths),
                         ["C:\\deg\\Summer2018.pdf",
                          "D:\\deg\\Summer2018.pdf", ]
                         )


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
