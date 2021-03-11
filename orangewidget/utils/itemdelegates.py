from datetime import date, datetime
from functools import partial
from itertools import filterfalse
from types import MappingProxyType as MappingProxy
from typing import (
    Sequence, Any, Mapping, Dict, TypeVar, Type, Optional, Container, Tuple
)

import numpy as np

from AnyQt.QtCore import (
    Qt, QObject, QAbstractItemModel, QModelIndex, QPersistentModelIndex, Slot,
    QLocale, QRect, QPointF,
)
from AnyQt.QtGui import (
    QFont, QFontMetrics, QPalette, QColor, QBrush, QIcon, QPixmap, QImage,
    QPainter, QStaticText, QTransform, QPen
)
from AnyQt.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, \
    QApplication, QStyle

from orangewidget.utils.cache import LRUCache

A = TypeVar("A")


def item_data(
        index: QModelIndex, roles: Sequence[int]
) -> Dict[int, Any]:
    """Query `index` for all `roles` and return them as a mapping"""
    model = index.model()
    datagetter = partial(model.data, index)
    values = map(datagetter, roles)
    return dict(zip(roles, values))


class ModelItemCache(QObject):
    """
    An item data cache for accessing QAbstractItemModel.data

    >>> cache = ModelItemCache()
    >>> cache.itemData(index, (Qt.DisplayRole, Qt.DecorationRole))
    {0: ...

    """
    __slots__ = ("__model", "__cache_data")

    def __init__(self, *args, maxsize=100 * 200, **kwargs):
        super().__init__(*args, **kwargs)
        self.__model: Optional[QAbstractItemModel] = None
        self.__cache_data: 'LRUCache[QPersistentModelIndex, Any]' = LRUCache(maxsize)

    def __connect_helper(self, model: QAbstractItemModel) -> None:
        model.dataChanged.connect(self.invalidate)
        model.layoutAboutToBeChanged.connect(self.invalidate)
        model.modelAboutToBeReset.connect(self.invalidate)
        model.rowsAboutToBeInserted.connect(self.invalidate)
        model.rowsAboutToBeRemoved.connect(self.invalidate)
        model.rowsAboutToBeMoved.connect(self.invalidate)
        model.columnsAboutToBeInserted.connect(self.invalidate)
        model.columnsAboutToBeRemoved.connect(self.invalidate)
        model.columnsAboutToBeMoved.connect(self.invalidate)

    def __disconnect_helper(self, model: QAbstractItemModel) -> None:
        model.dataChanged.disconnect(self.invalidate)
        model.layoutAboutToBeChanged.disconnect(self.invalidate)
        model.modelAboutToBeReset.disconnect(self.invalidate)
        model.rowsAboutToBeInserted.disconnect(self.invalidate)
        model.rowsAboutToBeRemoved.disconnect(self.invalidate)
        model.rowsAboutToBeMoved.disconnect(self.invalidate)
        model.columnsAboutToBeInserted.disconnect(self.invalidate)
        model.columnsAboutToBeRemoved.disconnect(self.invalidate)
        model.columnsAboutToBeMoved.disconnect(self.invalidate)

    def setModel(self, model: QAbstractItemModel) -> None:
        if model is self.__model:
            return
        if self.__model is not None:
            self.__disconnect_helper(self.__model)
            self.__model = None
        self.__model = model
        self.__cache_data.clear()
        if model is not None:
            self.__connect_helper(model)

    def model(self) -> Optional[QAbstractItemModel]:
        return self.__model

    @Slot()
    def invalidate(self) -> None:
        """Invalidate all cached data."""
        self.__cache_data.clear()

    def itemData(
            self, index: QModelIndex, roles: Sequence[int]
    ) -> Mapping[int, Any]:
        """
        Return item data from `index` for `roles`.

        The returned mapping is a read only view of *all* data roles accessed
        for the index through this caching interface. It will contain at least
        data for `roles`, but can also contain other ones.
        """
        model = index.model()
        if model is not self.__model:
            self.setModel(model)
        # NOTE: QPersistentModelIndex's hash changes when it is invalidated;
        # it must be purged from __cache_data before that (`__connect_helper`)
        key = QPersistentModelIndex(index)
        try:
            item = self.__cache_data[key]
        except KeyError:
            data = item_data(index, roles)
            view = MappingProxy(data)
            self.__cache_data[key] = data, view
        else:
            data, view = item
            queryroles = tuple(filterfalse(data.__contains__, roles))
            if queryroles:
                data.update(item_data(index, queryroles))
        return view

    def data(self, index: QModelIndex, role: int) -> Any:
        """Return item data for `index` and `role`"""
        model = index.model()
        if model is not self.__model:
            self.setModel(model)
        key = QPersistentModelIndex(index)
        try:
            item = self.__cache_data[key]
        except KeyError:
            data = item_data(index, (role,))
            view = MappingProxy(data)
            self.__cache_data[key] = data, view
        else:
            data, view = item
            if role not in data:
                data[role] = model.data(index, role)
        return data[role]


def cast_(type_: Type[A], value: Any) -> Optional[A]:
    # similar but not quite the same as qvariant_cast
    if value is None:
        return value
    if type(value) is type_:  # pylint: disable=unidiomatic-typecheck
        return value
    try:
        return type_(value)
    except Exception:  # pylint: disable=broad-except  # pragma: no cover
        return None


# QStyleOptionViewItem.Feature aliases as python int. Feature.__ior__
# implementation is slower then int.__ior__
_QStyleOptionViewItem_HasDisplay = int(QStyleOptionViewItem.HasDisplay)
_QStyleOptionViewItem_HasCheckIndicator = int(QStyleOptionViewItem.HasCheckIndicator)
_QStyleOptionViewItem_HasDecoration = int(QStyleOptionViewItem.HasDecoration)


def init_style_option(
        delegate: QStyledItemDelegate,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        data: Mapping[int, Any],
        roles: Optional[Container[int]] = None,
) -> None:
    """
    Like `QStyledItemDelegate.initStyleOption` but fill in the fields from
    `data` mapping. If `roles` is not `None` init the `option` for the
    specified `roles` only.
    """
    # pylint: disable=too-many-branches
    option.styleObject = None
    option.index = index
    if roles is None:
        roles = data
    features = 0
    if Qt.DisplayRole in roles:
        value = data.get(Qt.DisplayRole)
        if value is not None:
            option.text = delegate.displayText(value, option.locale)
            features |= _QStyleOptionViewItem_HasDisplay
    if Qt.FontRole in roles:
        value = data.get(Qt.FontRole)
        font = cast_(QFont, value)
        if font is not None:
            font = font.resolve(option.font)
            option.font = font
            option.fontMetrics = QFontMetrics(option.font)
    if Qt.ForegroundRole in roles:
        value = data.get(Qt.ForegroundRole)
        foreground = cast_(QBrush, value)
        if foreground is not None:
            option.palette.setBrush(QPalette.Text, foreground)
    if Qt.BackgroundRole in roles:
        value = data.get(Qt.BackgroundRole)
        background = cast_(QBrush, value)
        if background is not None:
            option.backgroundBrush = background
    if Qt.TextAlignmentRole in roles:
        value = data.get(Qt.TextAlignmentRole)
        alignment = cast_(int, value)
        if alignment is not None:
            option.displayAlignment = Qt.Alignment(alignment)
    if Qt.CheckStateRole in roles:
        state = data.get(Qt.CheckStateRole)
        if state is not None:
            features |= _QStyleOptionViewItem_HasCheckIndicator
            state = cast_(int, state)
            if state is not None:
                option.checkState = state
    if Qt.DecorationRole in roles:
        value = data.get(Qt.DecorationRole)
        if value is not None:
            features |= _QStyleOptionViewItem_HasDecoration
        if isinstance(value, QIcon):
            option.icon = value
        elif isinstance(value, QColor):
            pix = QPixmap(option.decorationSize)
            pix.fill(value)
            option.icon = QIcon(pix)
        elif isinstance(value, QPixmap):
            option.icon = QIcon(value)
            option.decorationSize = (value.size() / value.devicePixelRatio()).toSize()
        elif isinstance(value, QImage):
            pix = QPixmap.fromImage(value)
            option.icon = QIcon(value)
            option.decorationSize = (pix.size() / pix.devicePixelRatio()).toSize()
    option.features |= features


class CachedDataItemDelegate(QStyledItemDelegate):
    """
    An QStyledItemDelegate with item model data caching.

    Parameters
    ----------
    roles: Sequence[int]
        A set of roles to query the model and fill the `QStyleOptionItemView`
        with. By specifying only a subset of the roles here the delegate can
        be speed up (e.g. if you know the model does not provide the relevant
        roles or you just want to ignore some of them).
    """
    __slots__ = ("roles", "__cache",)

    #: The default roles that are filled in initStyleOption
    DefaultRoles = (
        Qt.DisplayRole, Qt.TextAlignmentRole, Qt.FontRole, Qt.ForegroundRole,
        Qt.BackgroundRole, Qt.CheckStateRole, Qt.DecorationRole
    )

    def __init__(
            self, *args, roles: Sequence[int] = None, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        if roles is None:
            roles = self.DefaultRoles
        self.roles = tuple(roles)
        self.__cache = ModelItemCache(self)

    def cachedItemData(
            self, index: QModelIndex, roles: Sequence[int]
    ) -> Mapping[int, Any]:
        """
        Return a mapping of all roles for the index.

        .. note::
           The returned mapping contains at least `roles`, but will also
           contain all cached roles that were queried previously.
        """
        return self.__cache.itemData(index, roles)

    def cachedData(self, index: QModelIndex, role: int) -> Any:
        """Return the data for role from `index`."""
        return self.__cache.data(index, role)

    def initStyleOption(
            self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """
        Reimplemented.

        Use caching to query the model data. Also limit the roles queried
        from the model and filled in `option` to `self.roles`.
        """
        data = self.cachedItemData(index, self.roles)
        init_style_option(self, option, index, data, self.roles)


_Real = (float, np.float64, np.float32, np.float16)
_Integral = (int, np.integer)
_Number = _Integral + _Real
_String = (str, np.str_)
_DateTime = (date, datetime, np.datetime64)
_TypesAlignRight = _Number + _DateTime


class StyledItemDelegate(QStyledItemDelegate):
    """
    A `QStyledItemDelegate` subclass supporting a broader range of python
    and numpy types for display.

    E.g. supports `np.float*`, `np.(u)int`, `datetime.date`,
    `datetime.datetime`
    """
    def displayText(self, value: Any, locale: QLocale) -> str:
        """
        Reimplemented.
        """
        # NOTE: Maybe replace the if,elif with a dispatch a table
        if value is None:
            return ""
        elif type(value) is str:  # pylint: disable=unidiomatic-typecheck
            return value  # avoid copies
        elif isinstance(value, _Integral):
            return super().displayText(int(value), locale)
        elif isinstance(value, _Real):
            return super().displayText(float(value), locale)
        elif isinstance(value, _String):
            return str(value)
        elif isinstance(value, datetime):
            return value.isoformat(sep=" ")
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, np.datetime64):
            return self.displayText(value.astype(datetime), locale)
        return super().displayText(value, locale)


_Qt_AlignRight = int(Qt.AlignRight)
_Qt_AlignLeft = int(Qt.AlignLeft)
_Qt_AlignHCenter = int(Qt.AlignHCenter)
_Qt_AlignTop = int(Qt.AlignTop)
_Qt_AlignBottom = int(Qt.AlignBottom)
_Qt_AlignVCenter = int(Qt.AlignVCenter)

_StaticTextKey = Tuple[str, QFont, Qt.TextElideMode, int]
_PenKey = Tuple[str, int]
_State_Mask = int(QStyle.State_Selected | QStyle.State_Enabled |
                  QStyle.State_Active)


class DataDelegate(CachedDataItemDelegate, StyledItemDelegate):
    """
    A QStyledItemDelegate optimized for displaying fixed tabular data.

    This delegate will automatically display numeric and date/time values
    aligned to the right.

    Note
    ----
    Does not support text wrapping
    """
    __slots__ = (
        "__static_text_lru_cache", "__pen_lru_cache", "__style"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__static_text_lru_cache: LRUCache[_StaticTextKey, QStaticText]
        self.__static_text_lru_cache = LRUCache(100 * 200)
        self.__pen_lru_cache: LRUCache[_PenKey, QPen] = LRUCache(100)
        self.__style = None

    def initStyleOption(
            self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        data = self.cachedItemData(index, self.roles)
        init_style_option(self, option, index, data, self.roles)
        if data.get(Qt.TextAlignmentRole) is None \
                and Qt.TextAlignmentRole in self.roles \
                and isinstance(data.get(Qt.DisplayRole), _TypesAlignRight):
            option.displayAlignment = \
                (option.displayAlignment & ~Qt.AlignHorizontal_Mask) | \
                Qt.AlignRight

    def paint(
            self, painter: QPainter, option: QStyleOptionViewItem,
            index: QModelIndex
    ) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = option.widget
        style = QApplication.style() if widget is None else widget.style()
        # Keep ref to style wrapper. This is ugly, wrong but the wrapping of
        # C++ QStyle instance takes ~5% unless the wrapper already exists.
        self.__style = style
        text = opt.text
        opt.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)
        trect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, widget)
        opt.text = text
        self.drawViewItemText(style, painter, opt, trect)

    def drawViewItemText(
            self, style: QStyle, painter: QPainter,
            option: QStyleOptionViewItem, rect: QRect
    ) -> None:
        """
        Draw view item text in `rect` using `style` and `painter`.
        """
        margin = style.pixelMetric(
            QStyle.PM_FocusFrameHMargin, None, option.widget) + 1
        rect = rect.adjusted(margin, 0, -margin, 0)
        font = option.font
        st = self.__static_text_elided_cache(
            option.text, font, option.fontMetrics, option.textElideMode,
            rect.width()
        )
        tsize = st.size()
        textalign = int(option.displayAlignment)
        text_pos_x = text_pos_y = 0.0

        if textalign & _Qt_AlignLeft:
            text_pos_x = rect.left()
        elif textalign & _Qt_AlignRight:
            text_pos_x = rect.x() + rect.width() - tsize.width()
        elif textalign & _Qt_AlignHCenter:
            text_pos_x = rect.x() + rect.width() / 2 - tsize.width() / 2

        if textalign & _Qt_AlignVCenter:
            text_pos_y = rect.y() + rect.height() / 2 - tsize.height() / 2
        elif textalign & _Qt_AlignTop:
            text_pos_y = rect.top()
        elif textalign & _Qt_AlignBottom:
            text_pos_y = rect.top() + rect.height() - tsize.height()

        painter.setPen(self.__pen_cache(option.palette, option.state))
        painter.setFont(font)
        painter.drawStaticText(QPointF(text_pos_x, text_pos_y), st)

    def __static_text_elided_cache(
            self, text: str, font: QFont, fontMetrics: QFontMetrics,
            elideMode: Qt.TextElideMode, width: int
    ) -> QStaticText:
        """
        Return a `QStaticText` instance for depicting the text with the `font`
        """
        try:
            return self.__static_text_lru_cache[text, font, elideMode, width]
        except KeyError:
            text = fontMetrics.elidedText(text, elideMode, width)
            st = QStaticText(text)
            st.prepare(QTransform(), font)
            # take a copy of the font for cache key
            key = text, QFont(font), elideMode, width
            self.__static_text_lru_cache[key] = st
            return st

    def __pen_cache(self, palette: QPalette, state: QStyle.State) -> QPen:
        """Return a QPen from the `palette` for `state`."""
        # NOTE: This method exists mostly to avoid QPen, QColor (de)allocations.
        key = palette.cacheKey(), int(state) & _State_Mask
        try:
            return self.__pen_lru_cache[key]
        except KeyError:
            cgroup = QPalette.Normal if state & QStyle.State_Active else QPalette.Inactive
            cgroup = cgroup if state & QStyle.State_Enabled else QPalette.Disabled
            role = QPalette.HighlightedText if state & QStyle.State_Selected else QPalette.Text
            pen = QPen(palette.color(cgroup, role))
            self.__pen_lru_cache[key] = pen
            return pen
