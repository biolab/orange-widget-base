import pyqtgraph as pg

from orangewidget.tests.base import GuiTest
from orangewidget.utils.matplotlib_export import scatterplot_code


def add_intro(a):
    r = "import matplotlib.pyplot as plt\n" + \
        "from numpy import array\n" + \
        "plt.clf()"
    return r + a


class TestScatterPlot(GuiTest):
    def test_scatterplot_simple(self):
        plotWidget = pg.PlotWidget(background="w")
        scatterplot = pg.ScatterPlotItem()
        scatterplot.setData(x=[1, 2, 3], y=[3, 2, 1])
        plotWidget.addItem(scatterplot)
        code = scatterplot_code(scatterplot)
        self.assertIn("plt.scatter", code)
        exec(add_intro(code), {})
