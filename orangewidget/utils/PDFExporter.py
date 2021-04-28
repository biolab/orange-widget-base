from pyqtgraph.exporters.Exporter import Exporter

from AnyQt import QtCore
from AnyQt.QtWidgets import QGraphicsItem, QApplication
from AnyQt.QtGui import QPainter, QPdfWriter
from AnyQt.QtCore import QMarginsF, Qt, QSizeF, QRectF


class PDFExporter(Exporter):
    """A pdf exporter for pyqtgraph graphs. Based on pyqtgraph's
     ImageExporter.

     There is a bug in Qt<5.12 that makes Qt wrongly use a cosmetic pen
     (QTBUG-68537). Workaround: do not use completely opaque colors.

     There is also a bug in Qt<5.12 with bold fonts that then remain bold.
     To see it, save the OWNomogram output."""

    def __init__(self, item):
        Exporter.__init__(self, item)
        if isinstance(item, QGraphicsItem):
            scene = item.scene()
        else:
            scene = item
        bgbrush = scene.views()[0].backgroundBrush()
        bg = bgbrush.color()
        if bgbrush.style() == Qt.NoBrush:
            bg.setAlpha(0)
        self.background = bg

        # The following code is a workaround for a bug in pyqtgraph 1.1. The suggested
        # fix upstream was pyqtgraph/pyqtgraph#1458
        try:
            from pyqtgraph.graphicsItems.ViewBox.ViewBox import ChildGroup
            for item in self.getPaintItems():
                if isinstance(item, ChildGroup):
                    if item.flags() & QGraphicsItem.ItemClipsChildrenToShape:
                        item.setFlag(QGraphicsItem.ItemClipsChildrenToShape, False)
        except:  # pylint: disable=bare-except
            pass

    def export(self, filename=None):
        pw = QPdfWriter(filename)
        dpi = int(QApplication.primaryScreen().logicalDotsPerInch())
        pw.setResolution(dpi)
        pw.setPageMargins(QMarginsF(0, 0, 0, 0))
        pw.setPageSizeMM(QSizeF(self.getTargetRect().size()) / dpi * 25.4)
        painter = QPainter(pw)
        try:
            self.setExportMode(True, {'antialias': True,
                                      'background': self.background,
                                      'painter': painter})
            painter.setRenderHint(QPainter.Antialiasing, True)
            if QtCore.QT_VERSION >= 0x050D00:
                painter.setRenderHint(QPainter.LosslessImageRendering, True)
            self.getScene().render(painter,
                                   QRectF(self.getTargetRect()),
                                   QRectF(self.getSourceRect()))
        finally:
            self.setExportMode(False)
        painter.end()
