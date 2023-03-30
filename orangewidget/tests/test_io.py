import os
import tempfile
import unittest
from unittest.mock import patch, Mock

import pyqtgraph
import pyqtgraph.exporters
from AnyQt.QtWidgets import QGraphicsScene, QGraphicsRectItem
from AnyQt.QtGui import QImage

from orangewidget.tests.base import GuiTest, named_file

from orangewidget import io as imgio


@unittest.skipUnless(hasattr(imgio, "PdfFormat"), "QPdfWriter not available")
class TestIO(GuiTest):
    def test_pdf(self):
        sc = QGraphicsScene()
        sc.addItem(QGraphicsRectItem(0, 0, 20, 20))
        fd, fname = tempfile.mkstemp()
        os.close(fd)
        try:
            imgio.PdfFormat.write_image(fname, sc)
        finally:
            os.unlink(fname)


class TestImgFormat(GuiTest):

    def test_pyqtgraph_exporter(self):
        graph = pyqtgraph.PlotWidget()
        with patch("orangewidget.io.ImgFormat._get_exporter",
                   Mock()) as mfn:
            with self.assertRaises(Exception):
                imgio.ImgFormat.write("", graph)
            self.assertEqual(1, mfn.call_count)  # run pyqtgraph exporter

    def test_other_exporter(self):
        sc = QGraphicsScene()
        sc.addItem(QGraphicsRectItem(0, 0, 3, 3))
        with patch("orangewidget.io.ImgFormat._get_exporter",
                   Mock()) as mfn:
            with self.assertRaises(Exception):
                imgio.ImgFormat.write("", sc)
            self.assertEqual(0, mfn.call_count)


class TestPng(GuiTest):

    def test_pyqtgraph(self):
        fd, fname = tempfile.mkstemp('.png')
        os.close(fd)
        graph = pyqtgraph.PlotWidget()
        try:
            imgio.PngFormat.write(fname, graph)
            im = QImage(fname)
            self.assertLess((200, 200), (im.width(), im.height()))
        finally:
            os.unlink(fname)

    def test_other(self):
        fd, fname = tempfile.mkstemp('.png')
        os.close(fd)
        sc = QGraphicsScene()
        sc.addItem(QGraphicsRectItem(0, 0, 3, 3))
        try:
            imgio.PngFormat.write(fname, sc)
            im = QImage(fname)
            # writer adds 15*2 of empty space
            # actual size depends upon ratio!
            #self.assertEqual((30+4, 30+4), (im.width(), im.height()))
        finally:
            os.unlink(fname)


class TestPdf(GuiTest):

    def test_pyqtgraph(self):
        fd, fname = tempfile.mkstemp('.pdf')
        os.close(fd)
        graph = pyqtgraph.PlotWidget()
        try:
            imgio.PdfFormat.write(fname, graph)
            with open(fname, "rb") as f:
                self.assertTrue(f.read().startswith(b'%PDF'))
            size_empty = os.path.getsize(fname)
        finally:
            os.unlink(fname)

        # does a ScatterPlotItem increases file size == is it drawn
        graph = pyqtgraph.PlotWidget()
        graph.addItem(pyqtgraph.ScatterPlotItem(x=list(range(100)), y=list(range(100))))
        try:
            imgio.PdfFormat.write(fname, graph)
            self.assertGreater(os.path.getsize(fname), size_empty + 5000)
        finally:
            os.unlink(fname)

        # does a PlotCurveItem increases file size == is it drawn
        graph = pyqtgraph.PlotWidget()
        graph.addItem(pyqtgraph.PlotCurveItem(x=list(range(100)), y=list(range(100))))
        try:
            imgio.PdfFormat.write(fname, graph)
            self.assertGreater(os.path.getsize(fname), size_empty + 600)
        finally:
            os.unlink(fname)

    def test_other(self):
        fd, fname = tempfile.mkstemp('.pdf')
        os.close(fd)
        sc = QGraphicsScene()
        sc.addItem(QGraphicsRectItem(0, 0, 3, 3))
        try:
            imgio.PdfFormat.write(fname, sc)
            with open(fname, "rb") as f:
                self.assertTrue(f.read().startswith(b'%PDF'))
        finally:
            os.unlink(fname)


class TestMatplotlib(GuiTest):
    def setUp(self):
        super().setUp()
        plt = pyqtgraph.PlotWidget()
        plt.addItem(pyqtgraph.ScatterPlotItem(
            x=[0.0, 0.1, 0.2, 0.3],
            y=[0.1, 0.2, 0.1, 0.2],
        ))
        self.plt = plt

    def tearDown(self):
        del self.plt
        super().tearDown()

    def test_python(self):
        with named_file("", suffix=".py") as fname:
            imgio.MatplotlibFormat.write(fname, self.plt.plotItem)
            with open(fname, "rt") as f:
                code = f.read()
            self.assertIn("plt.show()", code)
            self.assertIn("plt.scatter", code)
            # test if the runs
            exec(code.replace("plt.show()", ""), {})

    def test_pdf(self):

        with named_file("", suffix=".pdf") as fname:
            imgio.MatplotlibPDFFormat.write(fname, self.plt.plotItem)
            with open(fname, "rb") as f:
                code = f.read()
            self.assertTrue(code.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
