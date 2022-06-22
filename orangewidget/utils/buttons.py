from itertools import product
from typing import Union, List, NamedTuple, Optional, Sequence

from AnyQt.QtWidgets import (
    QPushButton, QAbstractButton, QFocusFrame, QStyle, QStylePainter,
    QStyleOptionButton, QWidget
)
from AnyQt.QtGui import (
    QPalette, QIcon, QPaintEvent, QPainter, QPaintEngine, QTextItem,
    QPaintDevice, QFontMetrics, QPaintEngineState, QBrush,
    QPen, QFont, QImage
)
from AnyQt.QtCore import Qt, QSize, QEvent, QPointF, QPoint, QRectF, QSizeF
from AnyQt.QtCore import Signal, Property


class VariableTextPushButton(QPushButton):
    """
    QPushButton subclass with an sizeHint method to better support settable
    variable width button text.

    Use this class instead of the QPushButton when the button will
    switch the text dynamically while displayed.
    """
    def __init__(self, *args, textChoiceList=[], **kwargs):
        super().__init__(*args, **kwargs)
        self.__textChoiceList = list(textChoiceList)

    def setTextChoiceList(self, textList):
        """
        Set the list of all `text` string to use for size hinting.

        Parameters
        ----------
        textList : List[str]
            A list of all different `text` properties that will/can be set on
            the push button. This list is used to derive a suitable sizeHint
            for the widget.
        """
        self.__textChoiceList = textList
        self.updateGeometry()

    def textChoiceList(self):
        return list(self.__textChoiceList)

    def sizeHint(self):
        """
        Reimplemented from `QPushButton.sizeHint`.

        Returns
        -------
        sh : QSize
        """
        sh = super().sizeHint()
        option = QStyleOptionButton()
        self.initStyleOption(option)
        sh_ = button_options_text_options_size(
            option, self.__textChoiceList, self.style(), self
        )
        return sh.expandedTo(sh_)


def button_options_text_options_size(
        option: QStyleOptionButton,
        textchoices: Sequence[str],
        style: QStyle,
        widget: Optional[QWidget] = None,
) -> QSize:
    option = QStyleOptionButton(option)
    fm = option.fontMetrics
    if option.iconSize.isValid():
        icsize = option.iconSize
        icsize.setWidth(icsize.width() + 4)
    else:
        icsize = QSize()
    sh = QSize()
    for text in textchoices:
        option.text = text
        size = fm.size(Qt.TextShowMnemonic, text)
        if not icsize.isNull():
            size.setWidth(size.width() + icsize.width())
            size.setHeight(max(size.height(), icsize.height()))
        sh_ = sh.expandedTo(
            style.sizeFromContents(QStyle.CT_PushButton, option, size, widget)
        )
        sh.setWidth(max(sh.width(), sh_.width()))
        sh.setHeight(max(sh.height(), sh_.height()))
    return sh


class ApplyButton(VariableTextPushButton):
    def __init__(self, *args, **kwargs):
        self.__modified = False
        super().__init__(*args, **kwargs)

    def setModified(self, state: bool) -> None:
        if self.__modified != state:
            self.__modified = state
            self.update()
            self.modifiedChanged.emit(state)

    def modified(self) -> bool:
        return self.__modified

    modifiedChanged = Signal(bool)
    modified_ = Property(bool, modified, setModified, notify=modifiedChanged)

    def sizeHint(self):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        style = self.style()
        texts = self.textChoiceList()
        sh = button_options_text_options_size(
            option, texts, style, self
        )
        texts_ex = [f"{text} {sym}" for text, sym in product(texts, ("➔", "✓"))]
        sh_ = button_options_text_options_size(
            option, texts_ex, style, self
        )
        sh.setWidth(max(sh_.width(), sh.width()))
        return sh

    def paintEvent(self, event: QPaintEvent) -> None:
        option = QStyleOptionButton()
        self.initStyleOption(option)
        modified = self.modified()
        symb = "➔" if modified else "✓"
        font = self.font()
        font.setItalic(modified)
        option.fontMetrics = QFontMetrics(font)
        style = self.style()
        p = QPainter(self)
        p.setFont(font)
        style.drawControl(QStyle.CE_PushButtonBevel, option, p, self)
        if not option.text:
            return
        # We could just paint the QStyle.CE_PushButtonLabel with the `{symb}`
        # appended, but that changes te text height and as such the positioning
        # i.e. it changes the text's baseline which looks bad on state
        # transitions.
        # So draw the QStyle.CE_PushButton element (original) onto a
        # fake painter to record the position and color of the text by the
        # native style. MacOS style and possibly other (stylesheet, ...) can
        # paint button text in alternative colors depending on the state.
        # E.g. MacOS paints the text white (on blue) when the button is the
        # default/autoDefault. Also, the color can change when pressed, ...
        pe = _FakePaintEngine()
        pd = _FakePaintDevice(pe, option.rect.size())
        p_ = QPainter(pd)
        p_.setFont(font)
        style.drawControl(QStyle.CE_PushButton, option, p_, self)
        p_.end()
        rect = QRectF()
        te = pe.text_items
        if not te:
            return

        # The symbol element to insert at the end
        last = te[-1].replace(text=symb)
        w = QFontMetrics(last.font).horizontalAdvance(last.text)
        # move all the items by half symbol width left
        te = [ti.replace(pos=ti.pos - QPointF(w/2, 0)) for ti in te]
        last = last.replace(pos=last.pos + QPointF(last.width + w/2, 0))
        for ti in (*te, last):
            rect = rect.united(
                QRectF(ti.pos, QSizeF(ti.width, ti.ascent + ti.descent)))
            p.setPen(ti.pen)
            p.setBrush(ti.brush)
            p.setFont(ti.font)
            p.drawText(ti.pos, ti.text)
        return


class _FakePaintDevice(QImage):
    def __init__(self, engine, size):
        super().__init__(size, QImage.Format_ARGB32)
        self._paintEngine = engine

    def paintEngine(self) -> QPaintEngine:
        return self._paintEngine


class _FakePaintEngine(QPaintEngine):
    """A paint engine to collect text items as they would be drawn"""
    class TItem(NamedTuple):
        """Text item as it would be drawn by the paint engine"""
        text: str
        font: QFont
        pos: QPointF
        width: float
        ascent: float
        descent: float
        pen: QPen
        brush: QBrush

        def replace(self, **kwargs):
            return self._replace(**kwargs)

    text_items: List[TItem]

    def __init__(self):
        super().__init__()
        self.text_items = []
        self.pen = QPen()
        self.brush = QBrush()

    def type(self):
        return QPaintEngine.Raster

    def begin(self, pdev: QPaintDevice) -> bool:
        return True

    def end(self) -> bool:
        return True

    def updateState(self, state: QPaintEngineState) -> None:
        self.pen = QPen(state.pen())
        self.brush = QBrush(state.brush())

    def drawTextItem(self, p: Union[QPointF, QPoint], textItem: QTextItem) -> None:
        self.text_items.append(
            _FakePaintEngine.TItem(
                textItem.text(), QFont(textItem.font()), QPointF(p),
                textItem.width(), textItem.ascent(), textItem.descent(),
                self.pen, self.brush
            )
        )

    def drawPixmap(self, r: QRectF, pm: 'QPixmap', sr: QRectF) -> None:
        pass

    def drawPolygon(self, points, mode):
        pass


class SimpleButton(QAbstractButton):
    """
    A simple icon button widget.
    """
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.__focusframe = None

    def focusInEvent(self, event):
        # reimplemented
        event.accept()
        if self.__focusframe is None:
            self.__focusframe = QFocusFrame(self)
            self.__focusframe.setWidget(self)
            palette = self.palette()
            palette.setColor(QPalette.WindowText,
                             palette.color(QPalette.Highlight))
            self.__focusframe.setPalette(palette)

    def focusOutEvent(self, event):
        # reimplemented
        event.accept()
        if self.__focusframe is not None:
            self.__focusframe.hide()
            self.__focusframe.deleteLater()
            self.__focusframe = None

    def event(self, event):
        if event.type() == QEvent.Enter or event.type() == QEvent.Leave:
            self.update()
        return super().event(event)

    def sizeHint(self):
        # reimplemented
        self.ensurePolished()
        iconsize = self.iconSize()
        icon = self.icon()
        if not icon.isNull():
            iconsize = icon.actualSize(iconsize)
        return iconsize

    def minimumSizeHint(self):
        # reimplemented
        return self.sizeHint()

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        option.initFrom(self)
        option.text = ""
        option.icon = self.icon()
        option.iconSize = self.iconSize()
        option.features = QStyleOptionButton.Flat
        if self.isDown():
            option.state |= QStyle.State_Sunken
            painter.drawPrimitive(QStyle.PE_PanelButtonBevel, option)

        if not option.icon.isNull():
            if option.state & QStyle.State_Active:
                mode = (QIcon.Active if option.state & QStyle.State_MouseOver
                        else QIcon.Normal)
            else:
                mode = QIcon.Disabled
            if self.isChecked():
                state = QIcon.On
            else:
                state = QIcon.Off
            option.icon.paint(painter, option.rect, Qt.AlignCenter, mode, state)
