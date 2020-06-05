import sys
from typing import List, Iterable, Tuple, Callable, Union, Dict
from functools import singledispatch

from AnyQt.QtCore import Qt, pyqtSignal as Signal
from AnyQt.QtGui import QFont, QFontDatabase
from AnyQt.QtWidgets import QDialog, QVBoxLayout, QComboBox, QCheckBox, \
    QDialogButtonBox, QSpinBox, QWidget, QGroupBox, QApplication, QFormLayout

from orangewidget import gui


class VisualSettingsDialog(QDialog):
    """
    A dialog for visual settings manipulation.

    Attributes
    ----------
    master : QWidget
        Parent widget.

    """
    setting_changed = Signal(object, object)

    def __init__(self, master: QWidget):
        super().__init__(master, windowTitle="Visual Settings")
        self.__controls: Dict[Tuple, Tuple[QWidget, Union[str, int, bool]]] = {}
        self.__changed_settings: Dict[Tuple, Union[str, int, bool]] = {}
        self.setting_changed.connect(self.__on_setting_changed)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.main_box = gui.vBox(self, box=None)  # type: QWidget

        buttons = QDialogButtonBox(
            orientation=Qt.Horizontal,
            standardButtons=QDialogButtonBox.Ok | QDialogButtonBox.Reset,
        )
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self.__reset)
        layout.addWidget(buttons)

    @property
    def changed_settings(self) -> Dict:
        """
        Keys (box, label, parameter) and values for changed settings.

        Returns
        -------
        settings : dict
        """
        return self.__changed_settings

    def __on_setting_changed(self, key: Tuple, value: Union[str, int, bool]):
        self.__changed_settings[key] = value

    def __reset(self):
        for key in self.__changed_settings:
            _set_control_value(*self.__controls[key])
        self.__changed_settings = {}

    def initialize(self, settings: Dict):
        """
        Initialize the dialog.

        Parameters
        ----------
        settings : Dict
            Collection of box names, label texts, initial control values
            and possible control values.
        """
        for box_name in settings:
            box = gui.vBox(self.main_box, box=box_name)
            form = QFormLayout()
            form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            form.setLabelAlignment(Qt.AlignLeft)
            box.layout().addLayout(form)
            for label, values in settings[box_name].items():
                self.__add_box(form, box_name, label, values)
        self.main_box.adjustSize()

    def __add_box(self, form: QFormLayout, box_name: str,
                  label: str, settings: Dict):
        box = gui.hBox(None, box=None)
        for parameter, (values, default_value) in settings.items():
            key = (box_name, label, parameter)
            control = _add_control(default_value, values, box,
                                   key, self.setting_changed)
            self.__controls[key] = (control, default_value)
        form.addRow(f"{label}:", box)

    def show_dlg(self):
        """ Open the dialog. """
        self.show()
        self.raise_()
        self.activateWindow()


@singledispatch
def _add_control(*_):
    raise NotImplementedError


@_add_control.register(str)
def _(value: str, values: List[str], parent: QGroupBox, key: Tuple[str],
      signal: Callable) -> QComboBox:
    combo = QComboBox()
    combo.addItems(values)
    combo.setCurrentText(value)
    parent.layout().addWidget(combo)
    combo.currentTextChanged.connect(lambda text: signal.emit(key, text))
    return combo


@_add_control.register(int)
def _(value: int, values: Iterable[int], parent: QGroupBox, key: Tuple[str],
      signal: Callable) -> QSpinBox:
    spin = QSpinBox(minimum=values.start, maximum=values.stop,
                    singleStep=values.step, value=value)
    parent.layout().addWidget(spin)
    spin.valueChanged.connect(lambda val: signal.emit(key, val))
    return spin


@_add_control.register(bool)
def _(value: int, _, parent: QGroupBox, key: Tuple[str],
      signal: Callable) -> QCheckBox:
    check = QCheckBox(text=f"{key[-1]} ", checked=value)
    parent.layout().addWidget(check)
    check.stateChanged.connect(lambda val: signal.emit(key, bool(val)))
    return check


@singledispatch
def _set_control_value(*_):
    raise NotImplementedError


@_set_control_value.register(QComboBox)
def _(combo: QComboBox, value: str):
    combo.setCurrentText(value)


@_set_control_value.register(QSpinBox)
def _(spin: QSpinBox, value: int):
    spin.setValue(value)


@_set_control_value.register(QCheckBox)
def _(spin: QCheckBox, value: bool):
    spin.setChecked(value)


if __name__ == "__main__":
    from collections import OrderedDict
    from AnyQt.QtWidgets import QPushButton

    app = QApplication(sys.argv)
    w = QDialog()
    w.setFixedSize(400, 200)

    _items = ["Foo", "Bar", "Baz", "Foo Bar", "Foo Baz", "Bar Baz"]
    _settings = OrderedDict({
        "Box 1": OrderedDict(
            {
                "Item 1": OrderedDict({
                    "Parameter 1": (_items[:10], _items[0]),
                    "Parameter 2": (_items[:10], _items[0]),
                    "Parameter 3": (range(4, 20), 5)
                }),
                "Item 2": OrderedDict({
                    "Parameter 1": (_items[:10], _items[1]),
                    "Parameter 2": (range(4, 20), 6),
                    "Parameter 3": (range(4, 20), 7)
                }),
                "Item 3": OrderedDict({
                    "Parameter 1": (_items[:10], _items[1]),
                    "Parameter 2": (range(4, 20), 8)
                }),
            }),
        "Box 2": OrderedDict(
            {
                "Item 1": OrderedDict({
                    "Parameter 1": (_items[:10], _items[0]),
                    "Parameter 2": (None, True)
                }),
                "Item 2": OrderedDict({
                    "Parameter 1": (_items[:10], _items[1]),
                    "Parameter 2": (None, False)
                }),
                "Item 3": OrderedDict({
                    "Parameter 1": (None, False),
                    "Parameter 2": (None, True)
                }),
                "Item 4": OrderedDict({
                    "Parameter 1": (_items[:10], _items[0]),
                    "Parameter 2": (None, False)
                }),
                "Item 5": OrderedDict({
                    "Parameter 1": (_items[:10], _items[1]),
                    "Parameter 2": (None, False)
                }),
                "Item 6": OrderedDict({
                    "Parameter 1": (None, False),
                    "Parameter 2": (None, False)
                }),
            }),
    })

    dlg = VisualSettingsDialog(w)
    dlg.initialize(_settings)
    dlg.setting_changed.connect(lambda *res: print(*res))
    dlg.finished.connect(lambda res: print(res, dlg.changed_settings))

    btn = QPushButton(w)
    btn.setText("Open dialog")
    btn.clicked.connect(dlg.show_dlg)

    w.show()
    sys.exit(app.exec_())
