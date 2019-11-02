"""
Wrappers for controls used in widgets
"""
import math
import os
import itertools
import logging
from types import LambdaType
from collections import defaultdict

import pkg_resources

from AnyQt import QtWidgets, QtCore, QtGui
from AnyQt.QtCore import Qt, QEvent, QObject
from AnyQt.QtGui import QCursor, QColor
from AnyQt.QtWidgets import (
    QApplication, QStyle, QSizePolicy, QWidget, QLabel,
    QTableWidgetItem, QStyledItemDelegate, QTableView, QHeaderView,
    QScrollArea
)

from orangewidget.utils.buttons import VariableTextPushButton

from .utils import *
from .utils import _is_horizontal
from .button import *
from .checkbox import *
from .combobox import *
from .label import *
from .lineedit import *
from .radiobutton import *
from .slider import *
from .spin import *


log = logging.getLogger(__name__)

OrangeUserRole = itertools.count(Qt.UserRole)

LAMBDA_NAME = (f"_lambda_{i}" for i in itertools.count(1))


class TableView(QTableView):
    """An auxilliary table view for use with PyTableModel in control areas"""
    def __init__(self, parent=None, **kwargs):
        kwargs = dict(
            dict(showGrid=False,
                 sortingEnabled=True,
                 cornerButtonEnabled=False,
                 alternatingRowColors=True,
                 selectionBehavior=self.SelectRows,
                 selectionMode=self.ExtendedSelection,
                 horizontalScrollMode=self.ScrollPerPixel,
                 verticalScrollMode=self.ScrollPerPixel,
                 editTriggers=self.DoubleClicked | self.EditKeyPressed),
            **kwargs)
        super().__init__(parent, **kwargs)
        h = self.horizontalHeader()
        h.setCascadingSectionResizes(True)
        h.setMinimumSectionSize(-1)
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        v = self.verticalHeader()
        v.setVisible(False)
        v.setSectionResizeMode(QHeaderView.ResizeToContents)

    class BoldFontDelegate(QStyledItemDelegate):
        """Paints the text of associated cells in bold font.

        Can be used e.g. with QTableView.setItemDelegateForColumn() to make
        certain table columns bold, or if callback is provided, the item's
        model index is passed to it, and the item is made bold only if the
        callback returns true.

        Parameters
        ----------
        parent: QObject
            The parent QObject.
        callback: callable
            Accepts model index and returns True if the item is to be
            rendered in bold font.
        """
        def __init__(self, parent=None, callback=None):
            super().__init__(parent)
            self._callback = callback

        def paint(self, painter, option, index):
            """Paint item text in bold font"""
            if not callable(self._callback) or self._callback(index):
                option.font.setWeight(option.font.Bold)
            super().paint(painter, option, index)

        def sizeHint(self, option, index):
            """Ensure item size accounts for bold font width"""
            if not callable(self._callback) or self._callback(index):
                option.font.setWeight(option.font.Bold)
            return super().sizeHint(option, index)


def resource_filename(path):
    """
    Return a resource filename (package data) for path.
    """
    return pkg_resources.resource_filename(__name__, os.path.join("..", path))


class OWComponent:
    """
    Mixin for classes that contain settings and/or attributes that trigger
    callbacks when changed.

    The class initializes the settings handler, provides `__setattr__` that
    triggers callbacks, and provides `control` attribute for access to
    Qt widgets controling particular attributes.

    Callbacks are exploited by controls (e.g. check boxes, line edits,
    combo boxes...) that are synchronized with attribute values. Changing
    the value of the attribute triggers a call to a function that updates
    the Qt widget accordingly.

    The class is mixed into `widget.OWBaseWidget`, and must also be mixed into
    all widgets not derived from `widget.OWBaseWidget` that contain settings or
    Qt widgets inserted by function in `orangewidget.gui` module. See
    `OWScatterPlotGraph` for an example.
    """
    def __init__(self, widget=None):
        self.controlled_attributes = defaultdict(list)
        self.controls = ControlGetter(self)
        if widget is not None and widget.settingsHandler:
            widget.settingsHandler.initialize(self)

    def _reset_settings(self):
        """
        Copy default settings to instance's settings. This method can be
        called from OWWidget's reset_settings, but will mostly have to be
        followed by calling a method that updates the widget.
        """
        self.settingsHandler.reset_to_original(self)

    def connect_control(self, name, func):
        """
        Add `func` to the list of functions called when the value of the
        attribute `name` is set.

        If the name includes a dot, it is assumed that the part the before the
        first dot is a name of an attribute containing an instance of a
        component, and the call is transferred to its `conntect_control`. For
        instance, `calling `obj.connect_control("graph.attr_x", f)` is
        equivalent to `obj.graph.connect_control("attr_x", f)`.

        Args:
            name (str): attribute name
            func (callable): callback function
        """
        if "." in name:
            name, rest = name.split(".", 1)
            sub = getattr(self, name)
            sub.connect_control(rest, func)
        else:
            self.controlled_attributes[name].append(func)

    def __setattr__(self, name, value):
        """Set the attribute value and trigger any attached callbacks.

        For backward compatibility, the name can include dots, e.g.
        `graph.attr_x`. `obj.__setattr__('x.y', v)` is equivalent to
        `obj.x.__setattr__('x', v)`.

        Args:
            name (str): attribute name
            value (object): value to set to the member.
        """
        if "." in name:
            name, rest = name.split(".", 1)
            sub = getattr(self, name)
            setattr(sub, rest, value)
        else:
            super().__setattr__(name, value)
            # First check that the widget is not just being constructed
            if hasattr(self, "controlled_attributes"):
                for callback in self.controlled_attributes.get(name, ()):
                    callback(value)


def auto_commit(widget, master, value, label, auto_label=None, box=True,
                checkbox_label=None, orientation=None, commit=None,
                callback=None, **misc):
    """
    Add a commit button with auto-commit check box.

    When possible, use auto_apply or auto_send instead of auto_commit.

    The widget must have a commit method and a setting that stores whether
    auto-commit is on.

    The function replaces the commit method with a new commit method that
    checks whether auto-commit is on. If it is, it passes the call to the
    original commit, otherwise it sets the dirty flag.

    The checkbox controls the auto-commit. When auto-commit is switched on, the
    checkbox callback checks whether the dirty flag is on and calls the original
    commit.

    Important! Do not connect any signals to the commit before calling
    auto_commit.

    :param widget: the widget into which the box with the button is inserted
    :type widget: QWidget or None
    :param value: the master's attribute which stores whether the auto-commit
        is on
    :type value:  str
    :param master: master widget
    :type master: OWBaseWidget or OWComponent
    :param label: The button label
    :type label: str
    :param auto_label: The label used when auto-commit is on; default is
        `label + " Automatically"`
    :type auto_label: str
    :param commit: master's method to override ('commit' by default)
    :type commit: function
    :param callback: function to call whenever the checkbox's statechanged
    :type callback: function
    :param box: tells whether the widget has a border, and its label
    :type box: int or str or None
    :return: the box
    """
    def checkbox_toggled():
        if getattr(master, value):
            btn.setText(auto_label)
            btn.setEnabled(False)
            if dirty:
                do_commit()
        else:
            btn.setText(label)
            btn.setEnabled(True)
        if callback:
            callback()

    def unconditional_commit():
        nonlocal dirty
        if getattr(master, value):
            do_commit()
        else:
            dirty = True

    def do_commit():
        nonlocal dirty
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            commit()
            dirty = False
        finally:
            QApplication.restoreOverrideCursor()

    dirty = False
    commit = commit or getattr(master, 'commit')
    commit_name = next(LAMBDA_NAME) if isinstance(commit, LambdaType) else commit.__name__
    setattr(master, 'unconditional_' + commit_name, commit)

    if not auto_label:
        if checkbox_label:
            auto_label = label
        else:
            auto_label = label.title() + " Automatically"
    if isinstance(box, QWidget):
        b = box
    else:
        if orientation is None:
            orientation = Qt.Vertical if checkbox_label else Qt.Horizontal
        b = widgetBox(widget, box=box, orientation=orientation,
                      addToLayout=False)
        b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    b.checkbox = cb = checkBox(b, master, value, checkbox_label,
                               callback=checkbox_toggled, tooltip=auto_label)
    if _is_horizontal(orientation):
        b.layout().addSpacing(10)
    cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    b.button = btn = VariableTextPushButton(
        b, text=label, textChoiceList=[label, auto_label], clicked=do_commit)
    if b.layout() is not None:
        b.layout().addWidget(b.button)

    if not checkbox_label:
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    checkbox_toggled()
    setattr(master, commit_name, unconditional_commit)
    misc['addToLayout'] = misc.get('addToLayout', True) and \
                          not isinstance(box, QtWidgets.QWidget)
    miscellanea(b, widget, widget, **misc)
    return b


def auto_send(widget, master, value="auto_send", **kwargs):
    """
    Convenience function that creates an auto_commit box,
    for widgets that send selected data (as opposed to applying changes).

    :param widget: the widget into which the box with the button is inserted
    :type widget: QWidget or None
    :param master: master widget
    :type master: OWBaseWidget or OWComponent
    :param value: the master's attribute which stores whether the auto-commit (default 'auto_send')
    :type value:  str
    :return: the box
    """
    return auto_commit(widget, master, value, "Send Selection", "Send Automatically", **kwargs)


def auto_apply(widget, master, value="auto_apply", **kwargs):
    """
    Convenience function that creates an auto_commit box,
    for widgets that apply changes (as opposed to sending a selection).

    :param widget: the widget into which the box with the button is inserted
    :type widget: QWidget or None
    :param master: master widget
    :type master: OWBaseWidget or OWComponent
    :param value: the master's attribute which stores whether the auto-commit (default 'auto_apply')
    :type value:  str
    :return: the box
    """
    return auto_commit(widget, master, value, "Apply", "Apply Automatically", **kwargs)


##############################################################################
# some table related widgets


# noinspection PyShadowingBuiltins
class tableItem(QTableWidgetItem):
    def __init__(self, table, x, y, text, editType=None, backColor=None,
                 icon=None, type=QTableWidgetItem.Type):
        super().__init__(type)
        if icon:
            self.setIcon(QtGui.QIcon(icon))
        if editType is not None:
            self.setFlags(editType)
        else:
            self.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable |
                          Qt.ItemIsSelectable)
        if backColor is not None:
            self.setBackground(QtGui.QBrush(backColor))
        # we add it this way so that text can also be int and sorting will be
        # done properly (as integers and not as text)
        self.setData(Qt.DisplayRole, text)
        table.setItem(x, y, self)


BarRatioRole = next(OrangeUserRole)  # Ratio for drawing distribution bars
BarBrushRole = next(OrangeUserRole)  # Brush for distribution bar

SortOrderRole = next(OrangeUserRole)  # Used for sorting


class BarItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent, brush=QtGui.QBrush(QtGui.QColor(255, 170, 127)),
                 scale=(0.0, 1.0)):
        super().__init__(parent)
        self.brush = brush
        self.scale = scale

    def paint(self, painter, option, index):
        if option.widget is not None:
            style = option.widget.style()
        else:
            style = QApplication.style()

        style.drawPrimitive(
            QStyle.PE_PanelItemViewRow, option, painter,
            option.widget)
        style.drawPrimitive(
            QStyle.PE_PanelItemViewItem, option, painter,
            option.widget)

        rect = option.rect
        val = index.data(Qt.DisplayRole)
        if isinstance(val, float):
            minv, maxv = self.scale
            val = (val - minv) / (maxv - minv)
            painter.save()
            if option.state & QStyle.State_Selected:
                painter.setOpacity(0.75)
            painter.setBrush(self.brush)
            painter.drawRect(
                rect.adjusted(1, 1, - rect.width() * (1.0 - val) - 2, -2))
            painter.restore()


class IndicatorItemDelegate(QtWidgets.QStyledItemDelegate):
    IndicatorRole = next(OrangeUserRole)

    def __init__(self, parent, role=IndicatorRole, indicatorSize=2):
        super().__init__(parent)
        self.role = role
        self.indicatorSize = indicatorSize

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        rect = option.rect
        indicator = index.data(self.role)

        if indicator:
            painter.save()
            painter.setRenderHints(QtGui.QPainter.Antialiasing)
            painter.setBrush(QtGui.QBrush(Qt.black))
            painter.drawEllipse(rect.center(),
                                self.indicatorSize, self.indicatorSize)
            painter.restore()


class LinkStyledItemDelegate(QStyledItemDelegate):
    LinkRole = next(OrangeUserRole)

    def __init__(self, parent):
        super().__init__(parent)
        self.mousePressState = QtCore.QModelIndex(), QtCore.QPoint()
        parent.entered.connect(self.onEntered)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QtCore.QSize(size.width(), max(size.height(), 20))

    def linkRect(self, option, index):
        if option.widget is not None:
            style = option.widget.style()
        else:
            style = QApplication.style()

        text = self.displayText(index.data(Qt.DisplayRole),
                                QtCore.QLocale.system())
        self.initStyleOption(option, index)
        textRect = style.subElementRect(
            QStyle.SE_ItemViewItemText, option, option.widget)

        if not textRect.isValid():
            textRect = option.rect
        margin = style.pixelMetric(
            QStyle.PM_FocusFrameHMargin, option, option.widget) + 1
        textRect = textRect.adjusted(margin, 0, -margin, 0)
        font = index.data(Qt.FontRole)
        if not isinstance(font, QtGui.QFont):
            font = option.font

        metrics = QtGui.QFontMetrics(font)
        elideText = metrics.elidedText(text, option.textElideMode,
                                       textRect.width())
        return metrics.boundingRect(textRect, option.displayAlignment,
                                    elideText)

    def editorEvent(self, event, model, option, index):
        if event.type() == QtCore.QEvent.MouseButtonPress and \
                self.linkRect(option, index).contains(event.pos()):
            self.mousePressState = (QtCore.QPersistentModelIndex(index),
                                    QtCore.QPoint(event.pos()))

        elif event.type() == QtCore.QEvent.MouseButtonRelease:
            link = index.data(LinkRole)
            if not isinstance(link, str):
                link = None

            pressedIndex, pressPos = self.mousePressState
            if pressedIndex == index and \
                    (pressPos - event.pos()).manhattanLength() < 5 and \
                    link is not None:
                import webbrowser
                webbrowser.open(link)
            self.mousePressState = QtCore.QModelIndex(), event.pos()

        elif event.type() == QtCore.QEvent.MouseMove:
            link = index.data(LinkRole)
            if not isinstance(link, str):
                link = None

            if link is not None and \
                    self.linkRect(option, index).contains(event.pos()):
                self.parent().viewport().setCursor(Qt.PointingHandCursor)
            else:
                self.parent().viewport().setCursor(Qt.ArrowCursor)

        return super().editorEvent(event, model, option, index)

    def onEntered(self, index):
        link = index.data(LinkRole)
        if not isinstance(link, str):
            link = None
        if link is None:
            self.parent().viewport().setCursor(Qt.ArrowCursor)

    def paint(self, painter, option, index):
        link = index.data(LinkRole)
        if not isinstance(link, str):
            link = None

        if link is not None:
            if option.widget is not None:
                style = option.widget.style()
            else:
                style = QApplication.style()
            style.drawPrimitive(
                QStyle.PE_PanelItemViewRow, option, painter,
                option.widget)
            style.drawPrimitive(
                QStyle.PE_PanelItemViewItem, option, painter,
                option.widget)

            text = self.displayText(index.data(Qt.DisplayRole),
                                    QtCore.QLocale.system())
            textRect = style.subElementRect(
                QStyle.SE_ItemViewItemText, option, option.widget)
            if not textRect.isValid():
                textRect = option.rect
            margin = style.pixelMetric(
                QStyle.PM_FocusFrameHMargin, option, option.widget) + 1
            textRect = textRect.adjusted(margin, 0, -margin, 0)
            elideText = QtGui.QFontMetrics(option.font).elidedText(
                text, option.textElideMode, textRect.width())
            painter.save()
            font = index.data(Qt.FontRole)
            if not isinstance(font, QtGui.QFont):
                font = option.font
            painter.setFont(font)
            if option.state & QStyle.State_Selected:
                color = option.palette.highlightedText().color()
            else:
                color = option.palette.link().color()
            painter.setPen(QtGui.QPen(color))
            painter.drawText(textRect, option.displayAlignment, elideText)
            painter.restore()
        else:
            super().paint(painter, option, index)


LinkRole = LinkStyledItemDelegate.LinkRole


class ColoredBarItemDelegate(QtWidgets.QStyledItemDelegate):
    """ Item delegate that can also draws a distribution bar
    """
    def __init__(self, parent=None, decimals=3, color=Qt.red):
        super().__init__(parent)
        self.decimals = decimals
        self.float_fmt = "%%.%if" % decimals
        self.color = QtGui.QColor(color)

    def displayText(self, value, locale=QtCore.QLocale()):
        if value is None or isinstance(value, float) and math.isnan(value):
            return "NA"
        if isinstance(value, float):
            return self.float_fmt % value
        return str(value)

    def sizeHint(self, option, index):
        font = self.get_font(option, index)
        metrics = QtGui.QFontMetrics(font)
        height = metrics.lineSpacing() + 8  # 4 pixel margin
        width = metrics.width(self.displayText(index.data(Qt.DisplayRole),
                                               QtCore.QLocale())) + 8
        return QtCore.QSize(width, height)

    def paint(self, painter, option, index):
        self.initStyleOption(option, index)
        text = self.displayText(index.data(Qt.DisplayRole))
        ratio, have_ratio = self.get_bar_ratio(option, index)

        rect = option.rect
        if have_ratio:
            # The text is raised 3 pixels above the bar.
            # TODO: Style dependent margins?
            text_rect = rect.adjusted(4, 1, -4, -4)
        else:
            text_rect = rect.adjusted(4, 4, -4, -4)

        painter.save()
        font = self.get_font(option, index)
        painter.setFont(font)

        if option.widget is not None:
            style = option.widget.style()
        else:
            style = QApplication.style()

        style.drawPrimitive(
            QStyle.PE_PanelItemViewRow, option, painter,
            option.widget)
        style.drawPrimitive(
            QStyle.PE_PanelItemViewItem, option, painter,
            option.widget)

        # TODO: Check ForegroundRole.
        if option.state & QStyle.State_Selected:
            color = option.palette.highlightedText().color()
        else:
            color = option.palette.text().color()
        painter.setPen(QtGui.QPen(color))

        align = self.get_text_align(option, index)

        metrics = QtGui.QFontMetrics(font)
        elide_text = metrics.elidedText(
            text, option.textElideMode, text_rect.width())
        painter.drawText(text_rect, align, elide_text)

        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        if have_ratio:
            brush = self.get_bar_brush(option, index)

            painter.setBrush(brush)
            painter.setPen(QtGui.QPen(brush, 1))
            bar_rect = QtCore.QRect(text_rect)
            bar_rect.setTop(bar_rect.bottom() - 1)
            bar_rect.setBottom(bar_rect.bottom() + 1)
            w = text_rect.width()
            bar_rect.setWidth(max(0, min(w * ratio, w)))
            painter.drawRoundedRect(bar_rect, 2, 2)
        painter.restore()

    def get_font(self, option, index):
        font = index.data(Qt.FontRole)
        if not isinstance(font, QtGui.QFont):
            font = option.font
        return font

    def get_text_align(self, _, index):
        align = index.data(Qt.TextAlignmentRole)
        if not isinstance(align, int):
            align = Qt.AlignLeft | Qt.AlignVCenter

        return align

    def get_bar_ratio(self, _, index):
        ratio = index.data(BarRatioRole)
        return ratio, isinstance(ratio, float)

    def get_bar_brush(self, _, index):
        bar_brush = index.data(BarBrushRole)
        if not isinstance(bar_brush, (QtGui.QColor, QtGui.QBrush)):
            bar_brush = self.color
        return QtGui.QBrush(bar_brush)


class HorizontalGridDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setPen(QColor(212, 212, 212))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()
        QStyledItemDelegate.paint(self, painter, option, index)


class VerticalLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self.setMaximumWidth(self.sizeHint().width() + 2)
        self.setMargin(4)

    def sizeHint(self):
        metrics = QtGui.QFontMetrics(self.font())
        rect = metrics.boundingRect(self.text())
        size = QtCore.QSize(rect.height() + self.margin(),
                            rect.width() + self.margin())
        return size

    def setGeometry(self, rect):
        super().setGeometry(rect)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = self.geometry()
        text_rect = QtCore.QRect(0, 0, rect.width(), rect.height())

        painter.translate(text_rect.bottomLeft())
        painter.rotate(-90)
        painter.drawText(
            QtCore.QRect(QtCore.QPoint(0, 0),
                         QtCore.QSize(rect.height(), rect.width())),
            Qt.AlignCenter, self.text())
        painter.end()


class VerticalItemDelegate(QStyledItemDelegate):
    # Extra text top/bottom margin.
    Margin = 6

    def __init__(self, extend=False):
        super().__init__()
        self._extend = extend  # extend text over cell borders

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        return QtCore.QSize(sh.height() + self.Margin * 2, sh.width())

    def paint(self, painter, option, index):
        option = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(option, index)

        if not option.text:
            return

        if option.widget is not None:
            style = option.widget.style()
        else:
            style = QApplication.style()
        style.drawPrimitive(
            QStyle.PE_PanelItemViewRow, option, painter,
            option.widget)
        cell_rect = option.rect
        itemrect = QtCore.QRect(0, 0, cell_rect.height(), cell_rect.width())
        opt = QtWidgets.QStyleOptionViewItem(option)
        opt.rect = itemrect
        textrect = style.subElementRect(
            QStyle.SE_ItemViewItemText, opt, opt.widget)

        painter.save()
        painter.setFont(option.font)

        if option.displayAlignment & (Qt.AlignTop | Qt.AlignBottom):
            brect = painter.boundingRect(
                textrect, option.displayAlignment, option.text)
            diff = textrect.height() - brect.height()
            offset = max(min(diff / 2, self.Margin), 0)
            if option.displayAlignment & Qt.AlignBottom:
                offset = -offset

            textrect.translate(0, offset)
            if self._extend and brect.width() > itemrect.width():
                textrect.setWidth(brect.width())

        painter.translate(option.rect.x(), option.rect.bottom())
        painter.rotate(-90)
        painter.drawText(textrect, option.displayAlignment, option.text)
        painter.restore()

##############################################################################
# progress bar management


class ProgressBar:
    def __init__(self, widget, iterations):
        self.iter = iterations
        self.widget = widget
        self.count = 0
        self.widget.progressBarInit()
        self.finished = False

    def __del__(self):
        if not self.finished:
            self.widget.progressBarFinished(processEvents=False)

    def advance(self, count=1):
        self.count += count
        self.widget.progressBarSet(int(self.count * 100 / max(1, self.iter)))

    def finish(self):
        self.finished = True
        self.widget.progressBarFinished()


##############################################################################

def tabWidget(widget):
    w = QtWidgets.QTabWidget(widget)
    if widget.layout() is not None:
        widget.layout().addWidget(w)
    return w


def createTabPage(tab_widget, name, widgetToAdd=None, canScroll=False):
    if widgetToAdd is None:
        widgetToAdd = vBox(tab_widget, addToLayout=0, margin=4)
    if canScroll:
        scrollArea = QtWidgets.QScrollArea()
        tab_widget.addTab(scrollArea, name)
        scrollArea.setWidget(widgetToAdd)
        scrollArea.setWidgetResizable(1)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    else:
        tab_widget.addTab(widgetToAdd, name)
    return widgetToAdd


def table(widget, rows=0, columns=0, selectionMode=-1, addToLayout=True):
    w = QtWidgets.QTableWidget(rows, columns, widget)
    if widget and addToLayout and widget.layout() is not None:
        widget.layout().addWidget(w)
    if selectionMode != -1:
        w.setSelectionMode(selectionMode)
    w.setHorizontalScrollMode(QtWidgets.QTableWidget.ScrollPerPixel)
    w.horizontalHeader().setSectionsMovable(True)
    return w


class VisibleHeaderSectionContextEventFilter(QtCore.QObject):
    def __init__(self, parent, itemView=None):
        super().__init__(parent)
        self.itemView = itemView

    def eventFilter(self, view, event):
        if not isinstance(event, QtGui.QContextMenuEvent):
            return False

        model = view.model()
        headers = [(view.isSectionHidden(i),
                    model.headerData(i, view.orientation(), Qt.DisplayRole))
                   for i in range(view.count())]
        menu = QtWidgets.QMenu("Visible headers", view)

        for i, (checked, name) in enumerate(headers):
            action = QtWidgets.QAction(name, menu)
            action.setCheckable(True)
            action.setChecked(not checked)
            menu.addAction(action)

            def toogleHidden(visible, section=i):
                view.setSectionHidden(section, not visible)
                if not visible:
                    return
                if self.itemView:
                    self.itemView.resizeColumnToContents(section)
                else:
                    view.resizeSection(section,
                                       max(view.sectionSizeHint(section), 10))

            action.toggled.connect(toogleHidden)
        menu.exec_(event.globalPos())
        return True


def toolButtonSizeHint(button=None, style=None):
    if button is None and style is None:
        style = QApplication.style()
    elif style is None:
        style = button.style()

    button_size = \
        style.pixelMetric(QStyle.PM_SmallIconSize) + \
        style.pixelMetric(QStyle.PM_ButtonMargin)
    return button_size


class VerticalScrollArea(QScrollArea):
    """
    A QScrollArea that can only scroll vertically because it never
    needs to scroll horizontally: it adapts its width to the contents.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.horizontalScrollBar().setEnabled(False)
        self.installEventFilter(self)  # to get LayoutRequest on this object

    def _set_width(self):
        scroll_bar_width = 0
        if self.verticalScrollBar().isVisible():
            scroll_bar_width = self.verticalScrollBar().width()
        self.setMinimumWidth(self.widget().minimumSizeHint().width() + scroll_bar_width)

    def eventFilter(self, receiver, event):
        if (receiver in (self, self.widget()) and event.type() == QEvent.Resize) \
                or (receiver is self and event.type() == QEvent.LayoutRequest):
            self._set_width()
        return super().eventFilter(receiver, event)

