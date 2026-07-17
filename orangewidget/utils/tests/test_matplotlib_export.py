import unittest
from unittest.mock import Mock

from pyqtgraph.graphicsItems.ScatterPlotItem import ScatterPlotItem
from orangewidget.tests.base import GuiTest
from orangewidget.utils.matplotlib_export import scatterplot_code


class TestScatterplotCode(GuiTest):
    def setUp(self):
        self.item = ScatterPlotItem([1, 2, 3], [4, 5, 6])

    def test_export(self):
        # We can't really test the code (without assuming a particular format),
        # but we can at least check that it runs without error
        scatterplot_code(self.item)

        self.item.setSize([10, 20, 30])
        scatterplot_code(self.item)

        self.item.setPen([2, 2, 3])
        scatterplot_code(self.item)

        self.item.setBrush(["r", "g", "g"])
        scatterplot_code(self.item)

        self.item.setSymbol(["o", "o", "t"])
        scatterplot_code(self.item)


if __name__ == '__main__':
    unittest.main()
