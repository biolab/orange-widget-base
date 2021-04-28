import os
import re
import tempfile
import unittest
from unittest.mock import patch

from AnyQt.QtCore import Qt, QRectF
from AnyQt.QtGui import QFont, QBrush, QPixmap, QColor, QIcon
from AnyQt.QtWidgets import QGraphicsScene

from orangewidget.report.owreport import OWReport, HAVE_REPORT
from orangewidget import gui
from orangewidget.utils.itemmodels import PyTableModel
from orangewidget.widget import OWBaseWidget
from orangewidget.tests.base import GuiTest


class TstWidget(OWBaseWidget):
    def send_report(self):
        self.report_caption("AA")


class TestReport(GuiTest):
    def test_report(self):
        count = 5
        rep = OWReport()
        for _ in range(count):
            widget = TstWidget()
            widget.create_report_html()
            rep.make_report(widget)
        self.assertEqual(rep.table_model.rowCount(), count)

    def test_report_table(self):
        rep = OWReport()
        model = PyTableModel([['x', 1, 2],
                              ['y', 2, 2]])
        model.setHorizontalHeaderLabels(['a', 'b', 'c'])

        model.setData(model.index(0, 0), Qt.AlignHCenter | Qt.AlignTop, Qt.TextAlignmentRole)
        model.setData(model.index(1, 0), QFont('', -1, QFont.Bold), Qt.FontRole)
        model.setData(model.index(1, 2), QBrush(Qt.red), Qt.BackgroundRole)

        view = gui.TableView()
        view.show()
        view.setModel(model)
        rep.report_table('Name', view)
        self.maxDiff = None
        self.assertEqual(
            rep.report_html,
            '<h2>Name</h2><table>\n'
            '<tr>'
            '<th style="color:black;border:0;background:transparent;'
            'text-align:left;vertical-align:middle;">a</th>'
            '<th style="color:black;border:0;background:transparent;'
            'text-align:left;vertical-align:middle;">b</th>'
            '<th style="color:black;border:0;background:transparent;'
            'text-align:left;vertical-align:middle;">c</th>'
            '</tr>'
            '<tr>'
            '<td style="color:black;border:0;background:transparent;'
            'text-align:center;vertical-align:top;">x</td>'
            '<td style="color:black;border:0;background:transparent;'
            'text-align:right;vertical-align:middle;">1</td>'
            '<td style="color:black;border:0;background:transparent;'
            'text-align:right;vertical-align:middle;">2</td>'
            '</tr>'
            '<tr>'
            '<td style="color:black;border:0;background:transparent;'
            'font-weight: bold;text-align:left;vertical-align:middle;">y</td>'
            '<td style="color:black;border:0;background:transparent;'
            'text-align:right;vertical-align:middle;">2</td>'
            '<td style="color:black;border:0;background:#ff0000;'
            'text-align:right;vertical-align:middle;">2</td>'
            '</tr></table>')

    def test_save_report_permission(self):
        """
        Permission Error may occur when trying to save report.
        GH-2147
        """
        rep = OWReport()
        filenames = ["f.report", "f.html"]
        for filename in filenames:
            with patch("orangewidget.report.owreport.open",
                       create=True, side_effect=PermissionError),\
                    patch("AnyQt.QtWidgets.QFileDialog.getSaveFileName",
                          return_value=(filename, 'Report (*.report)')),\
                    patch("AnyQt.QtWidgets.QMessageBox.exec_",
                          return_value=True), \
                    patch("orangewidget.report.owreport.log.error") as log:
                rep.save_report()
                log.assert_called()

    def test_save_report(self):
        rep = OWReport()
        widget = TstWidget()
        widget.create_report_html()
        rep.make_report(widget)
        temp_dir = tempfile.mkdtemp()
        temp_name = os.path.join(temp_dir, "f.report")
        try:
            with patch("AnyQt.QtWidgets.QFileDialog.getSaveFileName",
                       return_value=(temp_name, 'Report (*.report)')), \
                    patch("AnyQt.QtWidgets.QMessageBox.exec_",
                          return_value=True):
                rep.save_report()
        finally:
            os.remove(temp_name)
            os.rmdir(temp_dir)

    @patch("AnyQt.QtWidgets.QFileDialog.getSaveFileName",
           return_value=(False, 'HTML (*.html)'))
    def test_save_report_formats(self, mock):
        rep = OWReport()
        widget = TstWidget()
        widget.create_report_html()
        rep.make_report(widget)
        rep.report_view = False
        rep.save_report()
        formats = mock.call_args_list[-1][0][-1].split(';;')
        self.assertEqual(["Report (*.report)"], formats)
        rep.report_view = True
        rep.save_report()
        formats = mock.call_args_list[-1][0][-1].split(';;')
        self.assertEqual(['HTML (*.html)', 'PDF (*.pdf)', 'Report (*.report)'], formats)

    def test_show_webengine_warning_only_once(self):
        rep = OWReport()
        widget = TstWidget()
        with patch("AnyQt.QtWidgets.QMessageBox.critical", return_value=True) as p:
            widget.show_report()
            self.assertEqual(0 if HAVE_REPORT else 1, len(p.call_args_list))
            widget.show_report()
            self.assertEqual(0 if HAVE_REPORT else 1, len(p.call_args_list))

    def test_disable_saving_empty(self):
        """Test if save and print buttons are disabled on empty report"""
        rep = OWReport()
        self.assertFalse(rep.save_button.isEnabled())
        self.assertFalse(rep.print_button.isEnabled())
        widget = TstWidget()
        widget.create_report_html()
        rep.make_report(widget)
        self.assertTrue(rep.save_button.isEnabled())
        self.assertTrue(rep.print_button.isEnabled())

        rep.clear()
        self.assertFalse(rep.save_button.isEnabled())
        self.assertFalse(rep.print_button.isEnabled())

    def test_report_table_with_images(self):
        def basic_icon():
            pixmap = QPixmap(15, 15)
            pixmap.fill(QColor("red"))
            return QIcon(pixmap)

        def basic_scene():
            scene = QGraphicsScene()
            scene.addRect(QRectF(0, 0, 100, 100));
            return scene

        rep = OWReport()
        model = PyTableModel([['x', 1, 2]])
        model.setHorizontalHeaderLabels(['a', 'b', 'c'])

        model.setData(model.index(0, 1), basic_icon(), Qt.DecorationRole)
        model.setData(model.index(0, 2), basic_scene(), Qt.DisplayRole)

        view = gui.TableView()
        view.show()
        view.setModel(model)
        rep.report_table('Name', view)
        self.maxDiff = None
        pattern = re.compile(
            re.escape(
                '<h2>Name</h2><table>\n'
                '<tr>'
                '<th style="color:black;border:0;background:transparent;'
                'text-align:left;vertical-align:middle;">a</th>'
                '<th style="color:black;border:0;background:transparent;'
                'text-align:left;vertical-align:middle;">b</th>'
                '<th style="color:black;border:0;background:transparent;'
                'text-align:left;vertical-align:middle;">c</th>'
                '</tr>'
                '<tr>'
                '<td style="color:black;border:0;background:transparent;'
                'text-align:left;vertical-align:middle;">x</td>'
                '<td style="color:black;border:0;background:transparent;'
                'text-align:right;vertical-align:middle;">'
                '<img src="data:image/png;base64,'
            ) + '(.+)' + re.escape(  # any string for the icon
                '"/>1</td>'
                '<td style="color:black;border:0;background:transparent;'
                'text-align:right;vertical-align:middle;">'
            ) + '(.+)' + re.escape('</td></tr></table>')  # str for the scene
        )
        self.assertTrue(bool(pattern.match(rep.report_html)))


if __name__ == "__main__":
    unittest.main()
