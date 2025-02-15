# pylint: disable=all
from AnyQt.QtCore import Qt, QRect, QSize
from AnyQt.QtWidgets import QListView, QApplication, QProxyStyle, QStyle, QStyleFactory
from AnyQt.QtTest import QTest, QSignalSpy

from orangewidget.tests.base import GuiTest
from orangewidget.tests.utils import mouseMove, excepthook_catch

from orangewidget.utils import combobox


class StyleHintStyle(QProxyStyle):
    def styleHint(self, hint, option, widget=None, returnData=None) -> int:
        if hint == QStyle.SH_ComboBox_ListMouseTracking:
            return 1
        return super().styleHint(hint, option, widget, returnData)

    @staticmethod
    def create():
        return StyleHintStyle(QStyleFactory.create("fusion"))


class TestComboBoxSearch(GuiTest):
    def setUp(self):
        super().setUp()
        cb = combobox.ComboBoxSearch()
        cb.addItem("One")
        cb.addItem("Two")
        cb.addItem("Three")
        cb.insertSeparator(cb.count())
        cb.addItem("Four")
        self.cb = cb

    def tearDown(self):
        super().tearDown()
        self.cb.deleteLater()
        self.cb = None

    def test_combobox(self):
        cb = self.cb
        cb.grab()
        cb.showPopup()
        popup = cb.findChild(QListView)  # type: QListView
        # run through paint code for coverage
        popup.grab()
        cb.grab()

        model = popup.model()
        self.assertEqual(model.rowCount(), cb.count())
        QTest.keyClick(popup, Qt.Key_E)
        self.assertEqual(model.rowCount(), 2)
        QTest.keyClick(popup, Qt.Key_Backspace)
        self.assertEqual(model.rowCount(), cb.count())
        QTest.keyClick(popup, Qt.Key_F)
        self.assertEqual(model.rowCount(), 1)
        popup.setCurrentIndex(model.index(0, 0))
        spy = QSignalSpy(cb.activated[int])
        QTest.keyClick(popup, Qt.Key_Enter)

        self.assertEqual(spy[0], [4])
        self.assertEqual(cb.currentIndex(), 4)
        self.assertEqual(cb.currentText(), "Four")
        self.assertFalse(popup.isVisible())

    def test_combobox_navigation(self):
        cb = self.cb
        cb.setCurrentIndex(4)
        self.assertTrue(cb.currentText(), "Four")
        cb.showPopup()
        popup = cb.findChild(QListView)  # type: QListView
        self.assertEqual(popup.currentIndex().row(), 4)

        QTest.keyClick(popup, Qt.Key_Up)
        self.assertEqual(popup.currentIndex().row(), 2)
        QTest.keyClick(popup, Qt.Key_Escape)
        self.assertFalse(popup.isVisible())
        self.assertEqual(cb.currentIndex(), 4)
        cb.hidePopup()

    def test_click(self):
        interval = QApplication.doubleClickInterval()
        QApplication.setDoubleClickInterval(0)
        cb = self.cb
        spy = QSignalSpy(cb.activated[int])
        cb.showPopup()
        popup = cb.findChild(QListView)  # type: QListView
        model = popup.model()
        rect = popup.visualRect(model.index(2, 0))
        QTest.mouseRelease(
            popup.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center()
        )
        QApplication.setDoubleClickInterval(interval)
        self.assertEqual(len(spy), 1)
        self.assertEqual(spy[0], [2])
        self.assertEqual(cb.currentIndex(), 2)

    def test_focus_out(self):
        cb = self.cb
        cb.showPopup()
        popup = cb.findChild(QListView)
        # Activate some other window to simulate focus out
        w = QListView()
        w.show()
        w.activateWindow()
        w.hide()
        self.assertFalse(popup.isVisible())

    def test_track(self):
        cb = self.cb
        cb.setStyle(StyleHintStyle.create())
        cb.showPopup()
        popup = cb.findChild(QListView)  # type: QListView
        model = popup.model()
        rect = popup.visualRect(model.index(2, 0))
        mouseMove(popup.viewport(), rect.center())
        self.assertEqual(popup.currentIndex().row(), 2)
        cb.hidePopup()

    def test_kwargs_enabled_focus_out(self):
        # PyQt5's property via kwargs can invoke virtual overrides while still
        # not fully constructed
        with excepthook_catch(raise_on_exit=True):
            combobox.ComboBoxSearch(enabled=False)

    def test_popup_util(self):
        size = QSize(100, 400)
        screen = QRect(0, 0, 600, 600)
        g1 = combobox.dropdown_popup_geometry(
            size, QRect(200, 100, 100, 20), screen
        )
        self.assertEqual(g1, QRect(200, 120, 100, 400))
        g2 = combobox.dropdown_popup_geometry(
            size, QRect(-10, 0, 100, 20), screen
        )
        self.assertEqual(g2, QRect(0, 20, 100, 400))
        g3 = combobox.dropdown_popup_geometry(
            size, QRect(590, 0, 100, 20), screen
        )
        self.assertEqual(g3, QRect(600 - 100, 20, 100, 400))
        g4 = combobox.dropdown_popup_geometry(
            size, QRect(0, 500, 100, 20), screen
        )
        self.assertEqual(g4, QRect(0, 500 - 400, 100, 400))
