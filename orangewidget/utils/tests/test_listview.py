import unittest
from unittest.mock import Mock

from AnyQt.QtCore import QStringListModel, Qt, QSortFilterProxyModel
from AnyQt.QtTest import QTest
from AnyQt.QtWidgets import QLineEdit

from orangewidget.tests.base import GuiTest
from orangewidget.utils.itemmodels import PyListModel
from orangewidget.utils.listview import ListViewSearch, ListViewFilter


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

    def test_PyListModel(self):
        model = PyListModel()
        view = ListViewSearch()
        view.setFilterString("two")
        view.setRowHidden = Mock(side_effect=view.setRowHidden)
        view.setModel(model)
        view.setRowHidden.assert_not_called()
        model.wrap(["one", "two", "three", "four"])
        view.setRowHidden.assert_called()
        self.assertTrue(view.isRowHidden(0))
        self.assertFalse(view.isRowHidden(1))
        self.assertTrue(view.isRowHidden(2))
        self.assertTrue(view.isRowHidden(3))


class TestListViewFilter(GuiTest):
    def test_filter(self):
        model = PyListModel()
        view = ListViewFilter()
        view._ListViewFilter__search.textEdited.emit("two")
        view.model().setSourceModel(model)
        model.wrap(["one", "two", "three", "four"])
        self.assertEqual(view.model().rowCount(), 1)
        self.assertEqual(model.rowCount(), 4)

    def test_set_model(self):
        view = ListViewFilter()
        self.assertRaises(Exception, view.setModel, PyListModel())

    def test_set_source_model(self):
        model = PyListModel()
        view = ListViewFilter()
        view.set_source_model(model)
        self.assertIs(view.model().sourceModel(), model)
        self.assertIs(view.source_model(), model)

    def test_set_proxy(self):
        proxy = QSortFilterProxyModel()
        view = ListViewFilter(proxy=proxy)
        self.assertIs(view.model(), proxy)

    def test_set_proxy_raises(self):
        self.assertRaises(Exception, ListViewFilter, proxy=PyListModel())


if __name__ == "__main__":
    unittest.main()
