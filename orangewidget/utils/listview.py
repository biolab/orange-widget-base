from typing import Iterable, Optional
import warnings

from AnyQt.QtWidgets import QListView, QLineEdit, QStyle
from AnyQt.QtGui import QResizeEvent
from AnyQt.QtCore import (
    Qt,
    QAbstractItemModel,
    QModelIndex,
    QSortFilterProxyModel,
    QItemSelection,
    QSize,
    QItemSelectionModel,
)

from orangewidget.utils.itemmodels import signal_blocking


class ListViewFilter(QListView):
    """
    A QListView with implicit and transparent row filtering.
    """

    def __init__(
            self,
            *args,
            model: Optional[QAbstractItemModel] = None,
            proxy: Optional[QSortFilterProxyModel] = None,
            preferred_size: Optional[QSize] = None,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.__selection = QItemSelection()
        self.__search = QLineEdit(self, placeholderText="Filter...")
        self.__search.textEdited.connect(self.__on_text_edited)
        self.__preferred_size = preferred_size
        self.__layout()
        self.setMinimumHeight(100)

        if proxy is None:
            proxy = QSortFilterProxyModel(
                self, filterCaseSensitivity=Qt.CaseInsensitive
            )
        assert isinstance(proxy, QSortFilterProxyModel)
        super().setModel(proxy)
        self.set_source_model(model)
        self.selectionModel().selectionChanged.connect(self.__on_sel_changed)

    def __on_sel_changed(
            self,
            selected: QItemSelection,
            deselected: QItemSelection
    ):
        selected = self.model().mapSelectionToSource(selected)
        deselected = self.model().mapSelectionToSource(deselected)
        self.__selection.merge(selected, QItemSelectionModel.Select)
        self.__selection.merge(deselected, QItemSelectionModel.Deselect)
        self.__select()

    def __on_text_edited(self, string: str):
        with signal_blocking(self.selectionModel()):
            self.model().setFilterFixedString(string)
            self.__select()

    def __select(self):
        selection = self.model().mapSelectionFromSource(self.__selection)
        self.selectionModel().select(selection,
                                     QItemSelectionModel.ClearAndSelect)

    def setModel(self, _):
        raise TypeError("The model cannot be changed. "
                        "Use set_source_model() instead.")

    def set_source_model(self, model: QAbstractItemModel):
        self.model().setSourceModel(model)

    def source_model(self):
        return self.model().sourceModel()

    def updateGeometries(self):
        super().updateGeometries()
        self.__layout()

    def __layout(self):
        margins = self.viewportMargins()
        sh = self.__search.sizeHint()
        margins.setTop(sh.height())
        vscroll = self.verticalScrollBar()
        transient = self.style().styleHint(QStyle.SH_ScrollBar_Transient,
                                           None, vscroll)
        w = self.size().width()
        if vscroll.isVisibleTo(self) and not transient:
            w = w - vscroll.width() - 1
        self.__search.setGeometry(0, 0, w, sh.height())
        self.setViewportMargins(margins)

    def sizeHint(self) -> QSize:
        size = self.__preferred_size
        return size if size is not None else super().sizeHint()


class ListViewSearch(QListView):
    """
    An QListView with an implicit and transparent row filtering.
    """

    def __init__(self, *a, preferred_size=None, **ak):
        warnings.warn("ListViewSearch is deprecated and will be removed "
                      "in upcoming releases. Use ListViewFilter instead.",
                      DeprecationWarning)
        super().__init__(*a, **ak)
        self.__search = QLineEdit(self, placeholderText="Filter...")
        self.__search.textEdited.connect(self.__setFilterString)
        # Use an QSortFilterProxyModel for filtering. Note that this is
        # never set on the view, only its rows insertes/removed signals are
        # connected to observe an update row hidden state.
        self.__pmodel = QSortFilterProxyModel(
            self, filterCaseSensitivity=Qt.CaseInsensitive
        )
        self.__pmodel.rowsAboutToBeRemoved.connect(
            self.__filter_rowsAboutToBeRemoved
        )
        self.__pmodel.rowsInserted.connect(self.__filter_rowsInserted)
        self.__layout()
        self.preferred_size = preferred_size
        self.setMinimumHeight(100)

    def setFilterPlaceholderText(self, text: str):
        self.__search.setPlaceholderText(text)

    def filterPlaceholderText(self) -> str:
        return self.__search.placeholderText()

    def setFilterProxyModel(self, proxy: QSortFilterProxyModel) -> None:
        """
        Set an instance of QSortFilterProxyModel that will be used for filtering
        the model. The `proxy` must be a filtering proxy only; it MUST not sort
        the row of the model.
        The FilterListView takes ownership of the proxy.
        """
        self.__pmodel.rowsAboutToBeRemoved.disconnect(
            self.__filter_rowsAboutToBeRemoved
        )
        self.__pmodel.rowsInserted.disconnect(self.__filter_rowsInserted)
        self.__pmodel = proxy
        proxy.setParent(self)
        self.__pmodel.rowsAboutToBeRemoved.connect(
            self.__filter_rowsAboutToBeRemoved
        )
        self.__pmodel.rowsInserted.connect(self.__filter_rowsInserted)
        self.__pmodel.setSourceModel(self.model())
        self.__filter_reset()

    def filterProxyModel(self) -> QSortFilterProxyModel:
        return self.__pmodel

    def setModel(self, model: QAbstractItemModel) -> None:
        super().setModel(model)
        self.__pmodel.setSourceModel(model)
        self.__filter_reset()
        self.model().rowsInserted.connect(self.__model_rowInserted)
        self.model().modelReset.connect(self.__on_modelReset)

    def __on_modelReset(self):
        self.__filter_reset()
        self.__pmodel.setFilterFixedString("")
        self.__pmodel.setFilterFixedString(self.__search.text())

    def setRootIndex(self, index: QModelIndex) -> None:
        super().setRootIndex(index)
        self.__filter_reset()

    def __filter_reset(self):
        root = self.rootIndex()
        self.__filter(range(self.__pmodel.rowCount(root)))

    def __setFilterString(self, string: str):
        self.__pmodel.setFilterFixedString(string)

    def setFilterString(self, string: str):
        """Set the filter string."""
        self.__search.setText(string)
        self.__pmodel.setFilterFixedString(string)

    def filterString(self):
        """Return the filter string."""
        return self.__search.text()

    def __filter(self, rows: Iterable[int]) -> None:
        """Set hidden state for rows based on filter string"""
        root = self.rootIndex()
        pm = self.__pmodel
        for r in rows:
            self.setRowHidden(r, not pm.filterAcceptsRow(r, root))

    def __filter_set(self, rows: Iterable[int], state: bool):
        for r in rows:
            self.setRowHidden(r, state)

    def __filter_rowsAboutToBeRemoved(
        self, parent: QModelIndex, start: int, end: int
    ) -> None:
        fmodel = self.__pmodel
        mrange = QItemSelection(
            fmodel.index(start, 0, parent), fmodel.index(end, 0, parent)
        )
        mranges = fmodel.mapSelectionToSource(mrange)
        for mrange in mranges:
            self.__filter_set(range(mrange.top(), mrange.bottom() + 1), True)

    def __filter_rowsInserted(
        self, parent: QModelIndex, start: int, end: int
    ) -> None:
        fmodel = self.__pmodel
        mrange = QItemSelection(
            fmodel.index(start, 0, parent), fmodel.index(end, 0, parent)
        )
        mranges = fmodel.mapSelectionToSource(mrange)
        for mrange in mranges:
            self.__filter_set(range(mrange.top(), mrange.bottom() + 1), False)

    def __model_rowInserted(self, _, start: int, end: int) -> None:
        """
        Filter elements when inserted in list - proxy model's rowsAboutToBeRemoved
        is not called on elements that are hidden when inserting
        """
        self.__filter(range(start, end + 1))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)

    def updateGeometries(self) -> None:
        super().updateGeometries()
        self.__layout()

    def __layout(self):
        margins = self.viewportMargins()
        search = self.__search
        sh = search.sizeHint()
        size = self.size()
        margins.setTop(sh.height())
        vscroll = self.verticalScrollBar()
        style = self.style()
        transient = style.styleHint(QStyle.SH_ScrollBar_Transient, None, vscroll)
        w = size.width()
        if vscroll.isVisibleTo(self) and not transient:
            w = w - vscroll.width() - 1
        search.setGeometry(0, 0, w, sh.height())
        self.setViewportMargins(margins)

    def sizeHint(self):
        return (
            self.preferred_size
            if self.preferred_size is not None
            else super().sizeHint()
        )


def main():
    from itertools import cycle
    from AnyQt.QtCore import QStringListModel
    from AnyQt.QtWidgets import QApplication, QWidget, QVBoxLayout

    app = QApplication([])
    w = QWidget()
    w.setLayout(QVBoxLayout())
    lv = ListViewFilter()
    lv.setUniformItemSizes(True)
    w.layout().addWidget(lv)
    c = cycle(list(map(chr, range(ord("A"), ord("Z")))))
    s = [f"{next(c)}{next(c)}{next(c)}{next(c)}" for _ in range(50000)]
    model = QStringListModel(s)
    lv.set_source_model(model)
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
