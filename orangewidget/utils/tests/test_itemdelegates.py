import unittest
from datetime import date, datetime

import numpy as np

from AnyQt.QtCore import Qt, QModelIndex, QLocale, QRect, QPoint
from AnyQt.QtGui import QStandardItemModel, QFont, QColor, QIcon, QImage, \
    QPainter
from AnyQt.QtWidgets import QStyleOptionViewItem, QTableView

from orangecanvas.gui.svgiconengine import SvgIconEngine
from orangewidget.tests.base import GuiTest
from orangewidget.utils.itemdelegates import ModelItemCache, \
    CachedDataItemDelegate, StyledItemDelegate, DataDelegate


def create_model(rows, columns):
    model = QStandardItemModel()
    model.setRowCount(rows)
    model.setColumnCount(columns)
    for i in range(rows):
        for j in range(columns):
            model.setItemData(
                model.index(i, j), {
                    Qt.DisplayRole: f"{i}x{j}",
                    Qt.UserRole: i * j,
                }
            )
    return model


class TestModelItemCache(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.model = create_model(10, 2)
        self.cache = ModelItemCache()

    def tearDown(self) -> None:
        del self.model
        del self.cache
        super().tearDown()

    def test_cache(self):
        model = self.model
        index = model.index(0, 0)
        res = self.cache.itemData(index, (Qt.DisplayRole, Qt.UserRole))
        self.assertEqual(res, {Qt.DisplayRole: "0x0", Qt.UserRole: 0})
        res = self.cache.itemData(index, (Qt.DisplayRole, Qt.UserRole,
                                          Qt.UserRole + 1))
        self.assertEqual(res, {Qt.DisplayRole: "0x0", Qt.UserRole: 0,
                               Qt.UserRole + 1: None})
        model.setData(index, "2", Qt.DisplayRole)
        res = self.cache.data(index, Qt.DisplayRole)
        self.assertEqual(res, "2")
        res = self.cache.data(index, Qt.UserRole + 2)
        self.assertIsNone(res)
        m1 = create_model(1, 1)
        res = self.cache.data(m1.index(0, 0), Qt.DisplayRole)
        self.assertEqual(res, "0x0")


class TestCachedDataItemDelegate(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.model = create_model(5, 2)
        self.delegate = CachedDataItemDelegate()

    def test_delegate(self):
        opt = QStyleOptionViewItem()
        index = self.model.index(0, 0)
        self.delegate.initStyleOption(opt, index)
        self.assertEqual(opt.text, "0x0")

        icon = QIcon(SvgIconEngine(b'<svg></svg>'))
        yellow = QColor(Qt.yellow)
        magenta = QColor(Qt.magenta)
        data = {
            Qt.DisplayRole: "AA",
            Qt.FontRole: QFont("Times New Roman"),
            Qt.TextAlignmentRole: Qt.AlignRight,
            Qt.CheckStateRole: Qt.Checked,
            Qt.DecorationRole: icon,
            Qt.ForegroundRole: yellow,
            Qt.BackgroundRole: magenta,
        }
        self.model.setItemData(index, data)
        self.delegate.initStyleOption(opt, index)
        self.assertEqual(opt.font.family(), QFont("Times New Roman").family())
        self.assertEqual(opt.displayAlignment, Qt.AlignRight)
        self.assertEqual(opt.backgroundBrush.color(), magenta)
        self.assertEqual(opt.palette.text().color(), yellow)
        self.assertFalse(opt.icon.isNull())
        self.assertEqual(opt.icon.cacheKey(), icon.cacheKey())

        res = self.delegate.cachedData(index, Qt.DisplayRole)
        self.assertEqual(res, "AA")
        res = self.delegate.cachedItemData(
            index, (Qt.DisplayRole, Qt.TextAlignmentRole)
        )
        self.assertIn(Qt.DisplayRole, res)
        self.assertIn(Qt.TextAlignmentRole, res)
        self.assertEqual(res[Qt.TextAlignmentRole], Qt.AlignRight)
        self.assertEqual(res[Qt.DisplayRole], "AA")


class TestStyledItemDelegate(unittest.TestCase):
    def test_display_text(self):
        delegate = StyledItemDelegate()
        locale = QLocale.c()
        displayText = lambda value: delegate.displayText(value, locale)
        self.assertEqual(displayText(None), "")
        self.assertEqual(displayText(1), "1")
        self.assertEqual(displayText(np.int64(1)), "1")
        self.assertEqual(displayText(np.int64(1)), "1")
        self.assertEqual(displayText(1.5), "1.5")
        self.assertEqual(displayText(np.float16(1.5)), "1.5")
        self.assertEqual(displayText("A"), "A")
        self.assertEqual(displayText(np.str_("A")), "A")

        self.assertEqual(displayText(date(1999, 12, 31)), "1999-12-31")
        self.assertEqual(displayText(datetime(1999, 12, 31, 23, 59, 59)),
                         "1999-12-31 23:59:59")

        self.assertEqual(displayText(np.datetime64(0, "s")),
                         "1970-01-01 00:00:00")


class TestDataDelegate(GuiTest):
    def setUp(self) -> None:
        super().setUp()
        self.view = QTableView()
        self.model = create_model(5, 2)
        self.delegate = DataDelegate(self.view)
        self.view.setItemDelegate(self.delegate)

    def tearDown(self) -> None:
        self.view.deleteLater()
        self.view = None
        self.model = None
        super().tearDown()

    def test_init_style_options(self):
        delegate = self.delegate
        model = self.model
        index = model.index(0, 0)
        model.setData(index, 1, Qt.DisplayRole)
        opt = QStyleOptionViewItem()
        delegate.initStyleOption(opt, index)
        self.assertEqual(opt.displayAlignment, Qt.AlignRight)
        model.setData(index, "A", Qt.DisplayRole)

        opt = QStyleOptionViewItem()
        delegate.initStyleOption(opt, index)
        self.assertEqual(opt.displayAlignment, Qt.AlignLeft)

    def test_paint(self):
        delegate = self.delegate
        model = self.model
        index = model.index(0, 0)
        model.setData(index, 1, Qt.DisplayRole)

        def paint_with_data(data):
            model.setItemData(index, data)
            opt = self.view.viewOptions()
            opt.rect = QRect(QPoint(0, 0), delegate.sizeHint(opt, index))
            delegate.initStyleOption(opt, index)
            img = QImage(opt.rect.size(), QImage.Format_ARGB32_Premultiplied)
            p = QPainter(img)
            try:
                delegate.paint(p, opt, index)
            finally:
                p.end()

        paint_with_data({Qt.DisplayRole: 1.0})
        paint_with_data({Qt.DisplayRole: "AA"})
        paint_with_data({Qt.DisplayRole: "AA",
                         Qt.TextAlignmentRole: Qt.AlignLeft | Qt.AlignTop})
        paint_with_data({Qt.DisplayRole: "AA",
                         Qt.TextAlignmentRole: Qt.AlignHCenter | Qt.AlignVCenter})
        paint_with_data({Qt.DisplayRole: "AA",
                         Qt.TextAlignmentRole: Qt.AlignRight | Qt.AlignBottom})
