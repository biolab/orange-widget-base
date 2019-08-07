import os
import unittest
from unittest.mock import Mock

from AnyQt.QtWidgets import QFileDialog

from orangewidget.utils.filedialogs import format_filter
from orangewidget.utils.saveplot import save_plot
from orangewidget.widget import OWBaseWidget


class TestSavePlot(unittest.TestCase):
    def setUp(self):
        QFileDialog.getSaveFileName = Mock(return_value=[None, None])
        self.filters = [format_filter(f) for f in OWBaseWidget.graph_writers]

    def test_save_plot(self):
        save_plot(None, OWBaseWidget.graph_writers)
        QFileDialog.getSaveFileName.assert_called_once_with(
            None, "Save as...", os.path.expanduser("~"),
            ";;".join(self.filters), self.filters[0]
        )

    def test_save_plot_default_filename(self):
        save_plot(None, OWBaseWidget.graph_writers, filename="temp.txt")
        path = os.path.join(os.path.expanduser("~"), "temp.txt")
        QFileDialog.getSaveFileName.assert_called_once_with(
            None, "Save as...", path,
            ";;".join(self.filters), self.filters[0]
        )
