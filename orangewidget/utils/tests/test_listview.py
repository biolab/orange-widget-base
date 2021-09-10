import unittest

from AnyQt.QtCore import QStringListModel, Qt
from AnyQt.QtTest import QTest
from AnyQt.QtWidgets import QLineEdit

from orangewidget.tests.base import GuiTest
from orangewidget.utils.listview import ListViewSearch


class TestListViewSearch(GuiTest):
    def setUp(self) -> None:
        super().setUp()
        self.lv = ListViewSearch()
        s = ["one", "two", "three", "four"]
        model = QStringListModel(s)
        self.lv.setModel(model)

    def tearDown(self) -> None:
        super().tearDown()
        self.lv.deleteLater()
        self.lv = None

    def test_list_view(self):
        num_items = 4
        self.assertEqual(num_items, self.lv.model().rowCount())

        filter_row = self.lv.findChild(QLineEdit)
        filter_row.grab()
        self.lv.grab()

        QTest.keyClick(filter_row, Qt.Key_E, delay=-1)
        self.assertListEqual(
            [False, True, False, True],
            [self.lv.isRowHidden(i) for i in range(num_items)],
        )
        QTest.keyClick(filter_row, Qt.Key_Backspace)
        self.assertListEqual(
            [False] * 4, [self.lv.isRowHidden(i) for i in range(num_items)]
        )
        QTest.keyClick(filter_row, Qt.Key_F)
        self.assertListEqual(
            [True, True, True, False],
            [self.lv.isRowHidden(i) for i in range(num_items)],
        )
        QTest.keyClick(filter_row, Qt.Key_Backspace)
        QTest.keyClick(filter_row, Qt.Key_T)
        self.assertListEqual(
            [True, False, False, True],
            [self.lv.isRowHidden(i) for i in range(num_items)],
        )
        QTest.keyClick(filter_row, Qt.Key_H)
        self.assertListEqual(
            [True, True, False, True],
            [self.lv.isRowHidden(i) for i in range(num_items)],
        )

    def test_insert_new_value(self):
        num_items = 4
        filter_row = self.lv.findChild(QLineEdit)
        filter_row.grab()
        self.lv.grab()

        QTest.keyClick(filter_row, Qt.Key_E, delay=-1)
        self.assertListEqual(
            [False, True, False, True],
            [self.lv.isRowHidden(i) for i in range(num_items)],
        )

        model = self.lv.model()
        if model.insertRow(model.rowCount()):
            index = model.index(model.rowCount() - 1, 0)
            model.setData(index, "six")

        self.assertListEqual(
            [False, True, False, True, True],
            [self.lv.isRowHidden(i) for i in range(num_items + 1)],
        )

    def test_empty(self):
        self.lv.setModel(QStringListModel([]))
        self.assertEqual(0, self.lv.model().rowCount())

        filter_row = self.lv.findChild(QLineEdit)
        filter_row.grab()
        self.lv.grab()

        QTest.keyClick(filter_row, Qt.Key_T)
        QTest.keyClick(filter_row, Qt.Key_Backspace)


if __name__ == "__main__":
    unittest.main()
