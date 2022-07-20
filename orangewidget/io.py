import os
import sys
import tempfile
from collections import OrderedDict

from AnyQt import QtGui, QtCore, QtSvg, QtWidgets
from AnyQt.QtCore import QMarginsF, Qt, QRectF, QPointF, QRect
from AnyQt.QtGui import QPalette
from AnyQt.QtWidgets import (
    QGraphicsScene, QGraphicsView, QApplication
)

from orangewidget.utils.matplotlib_export import scene_code

try:
    from orangewidget.utils.webview import WebviewWidget
except ImportError:
    WebviewWidget = None

__all__ = [
    "ImgFormat", "Compression", "PngFormat", "ClipboardFormat", "SvgFormat",
    "MatplotlibPDFFormat", "MatplotlibFormat", "PdfFormat",
]


class Compression:
    """Supported compression extensions"""
    GZIP = '.gz'
    BZIP2 = '.bz2'
    XZ = '.xz'
    all = (GZIP, BZIP2, XZ)


class _Registry(type):
    """Metaclass that registers subtypes."""
    def __new__(mcs, name, bases, attrs):
        cls = type.__new__(mcs, name, bases, attrs)
        if not hasattr(cls, 'registry'):
            cls.registry = OrderedDict()
        else:
            cls.registry[name] = cls
        return cls

    def __iter__(cls):
        return iter(cls.registry)

    def __str__(cls):
        if cls in cls.registry.values():
            return cls.__name__
        return '{}({{{}}})'.format(cls.__name__, ', '.join(cls.registry))


def effective_background(scene: QGraphicsScene, view: QGraphicsView):
    background = scene.backgroundBrush()
    if background.style() != Qt.NoBrush:
        return background
    background = view.backgroundBrush()
    if background.style() != Qt.NoBrush:
        return background
    viewport = view.viewport()
    role = viewport.backgroundRole()
    if role != QPalette.NoRole:
        return viewport.palette().brush(role)
    return viewport.palette().brush(QPalette.Window)


class classproperty(property):
    def __get__(self, instance, class_):
        return self.fget(class_)


class ImgFormat(metaclass=_Registry):
    PRIORITY = sys.maxsize

    @staticmethod
    def _get_buffer(size, filename):
        raise NotImplementedError

    @staticmethod
    def _get_target(source):
        return QtCore.QRectF(0, 0, source.width(), source.height())

    @classmethod
    def _setup_painter(cls, scene, painter, source_rect, buffer):
        pass

    @staticmethod
    def _save_buffer(buffer, filename):
        raise NotImplementedError

    @staticmethod
    def _get_exporter():
        raise NotImplementedError

    @staticmethod
    def _export(self, exporter, filename):
        raise NotImplementedError

    @classmethod
    def write_image(cls, filename, object):
        def save_pyqtgraph():
            scene = object.scene()
            scenerect = scene.sceneRect()   #preserve scene bounding rectangle
            view = scene.views()[0]
            viewrect = view.sceneRect()
            scene.setSceneRect(viewrect)
            backgroundbrush = scene.backgroundBrush()  #preserve scene background brush
            brush = effective_background(scene, view)
            scene.setBackgroundBrush(brush)
            exporter = cls._get_exporter()
            cls._export(exporter(scene), filename)
            scene.setBackgroundBrush(backgroundbrush)  # reset scene background brush
            scene.setSceneRect(scenerect)   # reset scene bounding rectangle

        def save_scene():
            views = object.views()
            if not views:
                # It is unusual for scene not to be viewed - except in tests
                # We still try to get ratio for (any) screen, otherwise
                # assume 1 (the only consequence is lower resolution)
                try:
                    ratio = QApplication.primaryScreen().devicePixelRatio()
                except:  # pylint: disable=broad-except
                    ratio = 1
                rect = object.itemsBoundingRect()
                _render(rect, ratio, rect.size())
                return

            # Pick the first view. If there's a widget with multiple views that
            # cares which one is used, it must set graph_name to view, not scene
            view = views[0]
            ratio = views[0].devicePixelRatio()
            rect = view.sceneRect()
            target_rect = view.mapFromScene(rect).boundingRect()
            source_rect = QRect(
                int(target_rect.x()), int(target_rect.y()),
                int(target_rect.width()), int(target_rect.height()))
            _render(source_rect, ratio, target_rect.size(), view)

        def save_widget():
            _render(object.rect(), object.devicePixelRatio(), object.size())

        def _render(source_rect, pixel_ratio, size, renderer=object):
            buffer_size = size + type(size)(30, 30)
            try:
                buffer = cls._get_buffer(buffer_size, filename, pixel_ratio)
            except TypeError:  # backward compatibility (with what?)
                buffer = cls._get_buffer(buffer_size, filename)

            painter = QtGui.QPainter()
            painter.begin(buffer)
            painter.setRenderHints(QtGui.QPainter.Antialiasing
                                   | QtGui.QPainter.LosslessImageRendering)
            cls._setup_painter(
                painter, object,
                QRectF(0, 0, buffer_size.width(), buffer_size.height()), buffer)
            try:
                renderer.render(
                    painter,
                    QRectF(15, 15, size.width(), size.height()),
                    source_rect)
            except TypeError:
                # QWidget.render() takes different params
                renderer.render(painter, QPointF(15, 15))
            painter.end()
            cls._save_buffer(buffer, filename)

        try:
            save_pyqtgraph()
        except:
            if isinstance(object, QGraphicsScene):
                save_scene()
            else:
                save_widget()

    @classmethod
    def write(cls, filename, scene):
        if type(scene) == dict:
            scene = scene['scene']
        cls.write_image(filename, scene)

    @classproperty
    def img_writers(cls):  # type: () -> Mapping[str, Type[ImgFormat]]
        formats = OrderedDict()
        for format in sorted(cls.registry.values(), key=lambda x: x.PRIORITY):
            for ext in getattr(format, 'EXTENSIONS', []):
                # Only adds if not yet registered
                formats.setdefault(ext, format)
        return formats

    graph_writers = img_writers

    @classproperty
    def formats(cls):
        return cls.registry.values()


class PngFormat(ImgFormat):
    EXTENSIONS = ('.png',)
    DESCRIPTION = 'Portable Network Graphics'
    PRIORITY = 50

    @staticmethod
    def _get_buffer(size, filename, ratio=1):
        img = QtGui.QPixmap(int(size.width() * ratio),
                            int(size.height() * ratio))
        img.setDevicePixelRatio(ratio)
        return img

    @classmethod
    def _setup_painter(cls, painter, object, source_rect, buffer):
        if isinstance(object, (QGraphicsScene, QGraphicsView)):
            brush = object.backgroundBrush()
            if brush.style() == QtCore.Qt.NoBrush:
                brush = QtGui.QBrush(object.palette().color(QtGui.QPalette.Base))
        else:
            brush = QtGui.QBrush(QtCore.Qt.white)
        painter.fillRect(source_rect, brush)

    @staticmethod
    def _save_buffer(buffer, filename):
        buffer.save(filename, "png")

    @staticmethod
    def _get_exporter():
        from pyqtgraph.exporters.ImageExporter import ImageExporter
        from pyqtgraph import functions as fn

        # Use devicePixelRatio
        class PngExporter(ImageExporter):
            def __init__(self, item):
                super().__init__(item)
                if isinstance(item, QGraphicsScene):
                    self.ratio = item.views()[0].devicePixelRatio()
                else:
                    # Let's hope it's a view or another QWidget
                    self.ratio = item.devicePixelRatio()

            # Copied verbatim from super;
            # changes are in three lines that define self.png
            def export(self, fileName=None, toBytes=False, copy=False):
                if fileName is None and not toBytes and not copy:
                    filter = self.getSupportedImageFormats()
                    self.fileSaveDialog(filter=filter)
                    return

                w = int(self.params['width'])
                h = int(self.params['height'])
                if w == 0 or h == 0:
                    raise Exception(
                        "Cannot export image with size=0 (requested "
                        "export size is %dx%d)" % (w, h))

                targetRect = QtCore.QRect(0, 0, w, h)
                sourceRect = self.getSourceRect()

                self.png = QtGui.QImage(w * self.ratio, h * self.ratio,
                                        QtGui.QImage.Format.Format_ARGB32)
                self.png.fill(self.params['background'])
                self.png.setDevicePixelRatio(self.ratio)

                ## set resolution of image:
                origTargetRect = self.getTargetRect()
                resolutionScale = targetRect.width() / origTargetRect.width()
                # self.png.setDotsPerMeterX(self.png.dotsPerMeterX() * resolutionScale)
                # self.png.setDotsPerMeterY(self.png.dotsPerMeterY() * resolutionScale)

                painter = QtGui.QPainter(self.png)
                # dtr = painter.deviceTransform()
                try:
                    self.setExportMode(True, {
                        'antialias': self.params['antialias'],
                        'background': self.params['background'],
                        'painter': painter,
                        'resolutionScale': resolutionScale})
                    painter.setRenderHint(
                        QtGui.QPainter.RenderHint.Antialiasing,
                        self.params['antialias'])
                    self.getScene().render(painter, QtCore.QRectF(targetRect),
                                           QtCore.QRectF(sourceRect))
                finally:
                    self.setExportMode(False)
                painter.end()

                if self.params['invertValue']:
                    bg = fn.ndarray_from_qimage(self.png)
                    if sys.byteorder == 'little':
                        cv = slice(0, 3)
                    else:
                        cv = slice(1, 4)
                    mn = bg[..., cv].min(axis=2)
                    mx = bg[..., cv].max(axis=2)
                    d = (255 - mx) - mn
                    bg[..., cv] += d[..., np.newaxis]

                if copy:
                    QtWidgets.QApplication.clipboard().setImage(self.png)
                elif toBytes:
                    return self.png
                else:
                    return self.png.save(fileName)

        return PngExporter

    @staticmethod
    def _export(exporter, filename):
        buffer = exporter.export(toBytes=True)
        buffer.save(filename, "png")


class ClipboardFormat(PngFormat):
    EXTENSIONS = ()
    DESCRIPTION = 'System Clipboard'
    PRIORITY = 50

    @staticmethod
    def _save_buffer(buffer, _):
        QApplication.clipboard().setPixmap(buffer)

    @staticmethod
    def _export(exporter, _):
        exporter.export(copy=True)


class SvgFormat(ImgFormat):
    EXTENSIONS = ('.svg',)
    DESCRIPTION = 'Scalable Vector Graphics'
    PRIORITY = 100

    @staticmethod
    def _get_buffer(size, filename):
        buffer = QtSvg.QSvgGenerator()
        buffer.setResolution(int(QApplication.primaryScreen().logicalDotsPerInch()))
        buffer.setFileName(filename)
        buffer.setViewBox(QtCore.QRectF(0, 0, size.width(), size.height()))
        return buffer

    @staticmethod
    def _save_buffer(buffer, filename):
        dev = buffer.outputDevice()
        if dev is not None:
            dev.flush()
        pass

    @staticmethod
    def _get_exporter():
        from pyqtgraph.exporters.SVGExporter import SVGExporter
        return SVGExporter

    @staticmethod
    def _export(exporter, filename):
        if isinstance(exporter.item, QGraphicsScene):
            scene = exporter.item
            params = exporter.parameters()
            brush = effective_background(scene, scene.views()[0])
            params.param("background").setValue(brush.color())
        exporter.export(filename)

    @classmethod
    def write_image(cls, filename, scene):
        # WebviewWidget exposes its SVG contents more directly;
        # no need to go via QPainter if we can avoid it
        svg = None
        if WebviewWidget is not None and isinstance(scene, WebviewWidget):
            try:
                svg = scene.svg()
            except (ValueError, IOError):
                pass
        if svg is None:
            super().write_image(filename, scene)
            svg = open(filename).read()
        svg = svg.replace(
            "<svg ",
            '<svg style="image-rendering:optimizeSpeed;image-rendering:pixelated" ')
        with open(filename, 'w') as f:
            f.write(svg)


class MatplotlibFormat:
    # not registered as a FileFormat as it only works with scatter plot
    EXTENSIONS = ('.py',)
    DESCRIPTION = 'Python Code (with Matplotlib)'
    PRIORITY = 300

    @classmethod
    def write_image(cls, filename, scene):
        code = scene_code(scene) + "\n\nplt.show()"
        with open(filename, "wt") as f:
            f.write(code)

    @classmethod
    def write(cls, filename, scene):
        if type(scene) == dict:
            scene = scene['scene']
        cls.write_image(filename, scene)


class MatplotlibPDFFormat(MatplotlibFormat):
    EXTENSIONS = ('.pdf',)
    DESCRIPTION = 'Portable Document Format (from Matplotlib)'
    PRIORITY = 200

    @classmethod
    def write_image(cls, filename, scene):
        import matplotlib
        with matplotlib.rc_context({"backend": "pdf"}):
            code = scene_code(scene) + "\n\nplt.savefig({})".format(repr(filename))
            exec(code, {})  # will generate a pdf


if QtCore.QT_VERSION >= 0x050C00:  # Qt 5.12+

    class PdfFormat(ImgFormat):
        EXTENSIONS = ('.pdf', )
        DESCRIPTION = 'Portable Document Format'
        PRIORITY = 110

        @staticmethod
        def _get_buffer(size, filename):
            buffer = QtGui.QPdfWriter(filename)
            dpi = int(QApplication.primaryScreen().logicalDotsPerInch())
            buffer.setResolution(dpi)
            buffer.setPageMargins(QMarginsF(0, 0, 0, 0))
            pagesize = QtCore.QSizeF(size.width(), size.height()) / dpi * 25.4
            buffer.setPageSize(QtGui.QPageSize(pagesize, QtGui.QPageSize.Millimeter))
            return buffer

        @staticmethod
        def _save_buffer(buffer, filename):
            pass

        @staticmethod
        def _get_exporter():
            from orangewidget.utils.PDFExporter import PDFExporter
            return PDFExporter

        @staticmethod
        def _export(exporter, filename):
            exporter.export(filename)

else:

    # older Qt version have PdfWriter bugs and are handled through SVG

    class PdfFormat(ImgFormat):
        EXTENSIONS = ('.pdf', )
        DESCRIPTION = 'Portable Document Format'
        PRIORITY = 110

        @classmethod
        def write_image(cls, filename, scene):
            # export via svg to temp file then print that
            # NOTE: can't use NamedTemporaryFile with delete = True
            # (see https://bugs.python.org/issue14243)
            fd, tmpname = tempfile.mkstemp(suffix=".svg")
            os.close(fd)
            try:
                SvgFormat.write_image(tmpname, scene)
                with open(tmpname, "rb") as f:
                    svgcontents = f.read()
            finally:
                os.unlink(tmpname)

            svgrend = QtSvg.QSvgRenderer(QtCore.QByteArray(svgcontents))
            vbox = svgrend.viewBox()
            if not vbox.isValid():
                size = svgrend.defaultSize()
            else:
                size = vbox.size()
            writer = QtGui.QPdfWriter(filename)
            pagesize = QtGui.QPageSize(QtCore.QSizeF(size) * 0.282,
                                       QtGui.QPageSize.Millimeter)
            writer.setPageSize(pagesize)
            painter = QtGui.QPainter(writer)
            svgrend.render(painter)
            painter.end()
            del svgrend
            del painter
