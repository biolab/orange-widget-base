import gc
import ntpath
import pathlib

import os
import unittest
from unittest.mock import Mock, patch
from tempfile import NamedTemporaryFile

from AnyQt.QtCore import QSettings, QCoreApplication

from orangewidget.utils.filedialogs import RecentPath, open_filename_dialog, \
    unambiguous_paths, _check_init, LocalRecentPathsWidgetMixin, \
    LocalRecentPathsWComboMixin, RecentPathsWidgetMixin
from orangewidget.tests.base import GuiTest, WidgetTest
from orangewidget.widget import OWBaseWidget


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

    @unittest.mock.patch("pathlib.Path", pathlib.PureWindowsPath)
    @unittest.mock.patch("os.path.join", ntpath.join)
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

    def test_check_init(self):
        class A:
            _init_called = False

            def __init__(self):
                self._init_called = True

            @_check_init
            def f(self):
                pass

        class NoInit(A):
            pass

        class InitCalled(A):
            def __init__(self):
                # pylint: disable=useless-parent-delegation
                super().__init__()

        class InitNotCalled(A):
            def __init__(self):
                # pylint: disable=super-init-not-called
                pass

        NoInit().f()
        InitCalled().f()
        self.assertRaises(RuntimeError, InitNotCalled().f)


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

    def test_store_restore(self):
        path = RecentPath("temp/datasets/foo.txt", "temp", "datasets/foo.txt",
                          "FOO", "Sheet 1", ".txt")
        s = path.to_list()
        restored = RecentPath.from_list(s)
        self.assertIsInstance(restored, RecentPath)
        self.assertEqual(path.abspath, restored.abspath)
        self.assertEqual(path.relpath, restored.relpath)
        self.assertEqual(path.title, restored.title)
        self.assertEqual(path.sheet, restored.sheet)
        self.assertEqual(path.file_format, restored.file_format)

        path = RecentPath("temp/datasets/foo.txt", "temp", "datasets/foo.txt")
        s = path.to_list()
        restored = RecentPath.from_list(s)
        self.assertIsInstance(restored, RecentPath)


class TestRecentPathsWidgetMixinBase(unittest.TestCase):
    def test_recent_paths_limit(self):
        class A(LocalRecentPathsWidgetMixin):
            active_path = ""

            def workflowEnv(_):
                return {"basedir": "/home/luna/datasets"}


        a = A()
        for i in range(20):
            a.add_path(f"temp/datasets/foo{i}.txt")

        paths = a.recent_paths
        self.assertEqual(len(paths), 15)
        self.assertTrue(paths[0].abspath.endswith("temp/datasets/foo19.txt"))
        self.assertTrue(paths[-1].abspath.endswith("temp/datasets/foo5.txt"))


class TestRecentPathsWidgetMixin(WidgetTest):
    class A(RecentPathsWidgetMixin, OWBaseWidget):
        name = "A"
        active_path = ""

        def workflowEnv(_):
            return {"basedir": "/home/luna/datasets"}

    def test_deprecation_warning(self):
        with patch.object(self.A, "_relocate_recent_files"):
            self.assertWarns(DeprecationWarning, self.A)

    def test_last_path(self):
        a = self.A()
        self.assertIsNone(a.last_path())

        a.add_path("temp/datasets/foo.txt")
        self.assertTrue(a.last_path().endswith("temp/datasets/foo.txt"))

        a.add_path("temp/datasets/bar.txt")
        self.assertTrue(a.last_path().endswith("temp/datasets/bar.txt"))

    def test_relocate_recent_files(self):

        paths = [
            RecentPath("temp/datasets/foo.txt", "temp", "datasets/foo.txt"),
            RecentPath("temp/datasets/bar.txt", "temp", "datasets/bar.txt")
        ]
        with patch.object(self.A, "_relocated_recent_files", Mock(return_value=paths)):
            a = self.A()
            rp = a.recent_paths
            a._relocate_recent_files()
            self.assertEqual(rp, paths)
            self.assertIsNot(a.recent_paths, paths)


class TestLocalRecentPathsWidgetMixin(GuiTest):
    def setUp(self):
        self.orgName = QCoreApplication.organizationName()
        self.appName = QCoreApplication.applicationName()
        QCoreApplication.setOrganizationName("biolab.si")
        QCoreApplication.setApplicationName("OrangeTests")

        # Remove any settings that may be left from previous tests,
        # to ensure a clean state.
        self.remove_settings()

    def tearDown(self) -> None:
        self.remove_settings()

        # Probably unnecessary, but lets play it safe
        QCoreApplication.setApplicationName(self.orgName)
        QCoreApplication.setOrganizationName(self.orgName)

    def remove_settings(self):
        classes = self._create_classes()
        names = [class_._LocalRecentPathsWidgetMixin__setting_name()
                 for class_ in classes]
        # Ensure that class objects are garbage collected so that they will not
        # store QSettings in __del__ (if this is added in the future)
        del classes
        gc.collect()

        for name in names:
            QSettings().remove(name)

    def _create_classes(self):
        class BaseWidget:
            active_path = None

            def workflowEnv(_):
                return {"basedir": "/home/luna/datasets"}

        class AWidget(LocalRecentPathsWidgetMixin, BaseWidget):
            pass

        class AnotherWidget(LocalRecentPathsWidgetMixin, BaseWidget):
            DefaultRecentPaths = [
                RecentPath("temp/datasets/foo.txt", "temp", "datasets/foo.txt")]
            pass

        return AWidget, AnotherWidget

    def test_ensure_recent_paths(self):
        AWidget, AnotherWidget = self._create_classes()

        AWidget._relocate_recent_files = Mock()
        with patch("AnyQt.QtCore.QSettings.value", new=Mock(return_value=[
                RecentPath("temp/datasets/foo.txt", "temp", "datasets/foo.txt").to_list(),
                RecentPath("temp/datasets/bar.txt", "temp", "datasets/bar.txt").to_list()
                ])) as mvalue:
            a = AWidget()
            paths = AWidget.recent_paths
            self.assertEqual(len(paths), 2)
            self.assertIsInstance(paths[0], RecentPath)
            self.assertEqual(paths[0].abspath, "temp/datasets/foo.txt")
            self.assertEqual(paths[1].abspath, "temp/datasets/bar.txt")
            AWidget._relocate_recent_files.assert_called()

            paths = a.recent_paths
            self.assertEqual(len(paths), 2)
            self.assertIsInstance(paths[0], RecentPath)
            self.assertEqual(paths[0].abspath, "temp/datasets/foo.txt")
            self.assertEqual(paths[1].abspath, "temp/datasets/bar.txt")

            mvalue.reset_mock()
            AWidget()
            mvalue.assert_not_called()

        with patch("AnyQt.QtCore.QSettings.value", new=Mock(return_value=[])):
            n = AnotherWidget()
            self.assertEqual(AnotherWidget.recent_paths,
                             AnotherWidget.DefaultRecentPaths)
            self.assertEqual(n.recent_paths, AnotherWidget.DefaultRecentPaths)

    def test_add_store_restore_recent_paths(self):
        def store_and_sync(settings, name, value):
            orig_set(settings, name, value)
            settings.sync()

        orig_set = QSettings.setValue
        with patch("AnyQt.QtCore.QSettings.setValue", new=store_and_sync):
            AWidget, _ = self._create_classes()
            a = AWidget()

            a.add_path("temp/datasets/foo.txt")
            a.add_path("temp/datasets/bar.txt")

            AWidget, AnotherWidget = self._create_classes()
            paths = AWidget().recent_paths
            self.assertEqual(len(paths), 2)
            self.assertIsInstance(paths[0], RecentPath)
            self.assertTrue(paths[0].abspath.endswith("temp/datasets/bar.txt"))
            self.assertTrue(paths[1].abspath.endswith("temp/datasets/foo.txt"))

    def test_add_select_file(self):
        AWidget, _ = self._create_classes()
        a = AWidget()

        a.add_path("temp/datasets/foo.txt")
        a.add_path("temp/datasets/bar.txt")
        a.add_path("temp/datasets/baz.txt")

        sel = a.select_file(2)
        self.assertTrue(sel.abspath.endswith("temp/datasets/foo.txt"))
        self.assertEqual(["foo.txt", "baz.txt", "bar.txt"],
                         [path.basename for path in a.recent_paths])

        sel = a.select_file(1)
        self.assertTrue(sel.abspath.endswith("temp/datasets/baz.txt"))
        self.assertEqual(["baz.txt", "foo.txt", "bar.txt"],
                         [path.basename for path in a.recent_paths])

        sel = a.select_file(0)
        self.assertTrue(sel.abspath.endswith("temp/datasets/baz.txt"))
        self.assertEqual(["baz.txt", "foo.txt", "bar.txt"],
                         [path.basename for path in a.recent_paths])


class TestLocalRecentPathsWComboMixin(WidgetTest):
    def test_init(self):
        class A(LocalRecentPathsWComboMixin, OWBaseWidget):
            name = "A"

            DefaultRecentPaths = [
                RecentPath("temp/datasets/foo.txt", "temp", "datasets/foo.txt"),
                RecentPath("temp/datasets/bar.txt", "temp", "datasets/bar.txt")
            ]

        with patch("os.path.exists", new=Mock(return_value=True)):
            a = self.create_widget(A)
            self.assertEqual(a.recent_paths[0].basename, "foo.txt")

            b = self.create_widget(A, {"active_path": A.DefaultRecentPaths[1]})
            self.assertEqual(b.active_path.basename, "bar.txt")
            self.assertEqual(b.active_path.basename, "bar.txt")
            self.assertEqual(a.active_path.basename, "foo.txt")

    def test_merge_paths(self):
        class A(LocalRecentPathsWComboMixin, OWBaseWidget):
            name = "A"

        A.recent_paths = [
            RecentPath("temp/datasets/foo.txt", "temp", "datasets/foo.txt"),
            RecentPath("temp/datasets/bar.txt", "temp", "datasets/bar.txt")
        ]

        A.merge_paths([
            RecentPath("temp/datasets/foo.txt", "temp", "datasets/baz.txt"),
            RecentPath("temp/datasets/baz.txt", "temp", "datasets/foo.txt")
        ])

        self.assertEqual([path.basename for path in A.recent_paths],
                         ["foo.txt", "baz.txt", "bar.txt"])

        A.merge_paths([
            RecentPath(f"temp/datasets/foo{i}.txt", "temp", f"datasets/foo{i}.txt")
            for i in range(A.MAX_RECENT_PATHS - 1)])

        self.assertEqual(len(A.recent_paths), A.MAX_RECENT_PATHS)
        self.assertEqual(A.recent_paths[-1].basename, "foo.txt")
        self.assertEqual(A.recent_paths[0].basename, "foo0.txt")


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

    def test_add_all(self):
        class ABCFormat:
            EXTENSIONS = ('.abc', '.jkl')
            DESCRIPTION = 'abc file'
            PRIORITY = 30

        class DEFFormat:
            EXTENSIONS = ('.def', )
            DESCRIPTION = 'def file'
            PRIORITY = 40

        # Add all known extensions
        dialog = Mock(return_value=("foo.abc", ""))
        open_filename_dialog(".", "", [ABCFormat, DEFFormat], dialog=dialog)
        self.assertIn("(*.abc *.def *.jkl)", dialog.call_args[0][3])
        self.assertIn("(*.abc *.jkl)", dialog.call_args[0][3])
        self.assertIn("(*.def)", dialog.call_args[0][3])

        # Add all extensions (*.*)
        dialog = Mock(return_value=("foo.abc", ""))
        open_filename_dialog(".", "", [ABCFormat, DEFFormat],
                             add_all="*", dialog=dialog)
        self.assertIn("(*.*)", dialog.call_args[0][3])
        self.assertIn("(*.abc *.jkl)", dialog.call_args[0][3])
        self.assertIn("(*.def)", dialog.call_args[0][3])

        # Don't add any extensions
        dialog = Mock(return_value=("foo.abc", ""))
        open_filename_dialog(".", "", [ABCFormat, DEFFormat],
                             add_all=False, dialog=dialog)
        self.assertNotIn("(*.abc *.def *.jkl)", dialog.call_args[0][3])
        self.assertIn("(*.abc *.jkl)", dialog.call_args[0][3])
        self.assertIn("(*.def)", dialog.call_args[0][3])

        # With a single format, add all known extensions is ignored
        dialog = Mock(return_value=("foo.abc", ""))
        open_filename_dialog(".", "", [ABCFormat],
                             dialog=dialog)
        self.assertNotIn("(*.*)", dialog.call_args[0][3])
        self.assertEqual(dialog.call_args[0][3].count("(*.abc *.jkl)"), 1)

        # With a single format, add all extensions (*.*) still applies
        dialog = Mock(return_value=("foo.abc", ""))
        open_filename_dialog(".", "", [ABCFormat],
                             add_all="*", dialog=dialog)
        self.assertIn("(*.*)", dialog.call_args[0][3])
        self.assertIn("(*.abc *.jkl)", dialog.call_args[0][3])


if __name__ == "__main__":
    unittest.main()
