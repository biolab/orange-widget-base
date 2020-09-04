from typing import Iterable

from PyQt5.QtWidgets import QListView, QLineEdit
from PyQt5.QtGui import QResizeEvent
from PyQt5.QtCore import (
    Qt,
    QAbstractItemModel,
    QModelIndex,
    QSortFilterProxyModel,
    QItemSelection,
)


class ListViewSearch(QListView):
    """
    An QListView with an implicit and transparent row filtering.
    """

    def __init__(self, *a, preferred_size=None, **ak):
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

    def setRootIndex(self, index: QModelIndex) -> None:
        super().setRootIndex(index)
        self.__filter_reset()

    def __filter_reset(self):
        root = self.rootIndex()
        pm = self.__pmodel
        for i in range(self.__pmodel.rowCount(root)):
            self.setRowHidden(i, not pm.filterAcceptsRow(i, root))

    def __setFilterString(self, string: str):
        self.__pmodel.setFilterFixedString(string)

    def setFilterString(self, string: str):
        """Set the filter string."""
        self.__search.setText(string)
        self.__pmodel.setFilterFixedString(string)

    def filterString(self):
        """Return the filter string."""
        return self.__search.text()

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
        w = size.width()
        if vscroll.isVisibleTo(self):
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
    from PyQt5.QtCore import QStringListModel
    from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout

    app = QApplication([])
    w = QWidget()
    w.setLayout(QVBoxLayout())
    lv = ListViewSearch()
    lv.setUniformItemSizes(True)
    w.layout().addWidget(lv)
    c = cycle(list(map(chr, range(ord("A"), ord("Z")))))
    s = [f"{next(c)}{next(c)}{next(c)}{next(c)}" for _ in range(50000)]
    model = QStringListModel(s)
    lv.setModel(model)
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
