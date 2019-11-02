from AnyQt import QtWidgets
from AnyQt.QtCore import Qt

from orangewidget.utils import getdeepattr
from .utils import *


__all__ = ["checkBox", "checkButtonOffsetHint"]


def checkBox(widget, master, value, label, box=None,
             callback=None, getwidget=False, id_=None, labelWidth=None,
             disables=None, **misc):
    """
    A simple checkbox.

    :param widget: the widget into which the box is inserted
    :type widget: QWidget or None
    :param master: master widget
    :type master: OWBaseWidget or OWComponent
    :param value: the master's attribute with which the value is synchronized
    :type value:  str
    :param label: label
    :type label: str
    :param box: tells whether the widget has a border, and its label
    :type box: int or str or None
    :param callback: a function that is called when the check box state is
        changed
    :type callback: function
    :param getwidget: If set `True`, the callback function will get a keyword
        argument `widget` referencing the check box
    :type getwidget: bool
    :param id_: If present, the callback function will get a keyword argument
        `id` with this value
    :type id_: any
    :param labelWidth: the width of the label
    :type labelWidth: int
    :param disables: a list of widgets that are disabled if the check box is
        unchecked
    :type disables: list or QWidget or None
    :return: constructed check box; if is is placed within a box, the box is
        return in the attribute `box`
    :rtype: QCheckBox
    """
    if box:
        b = hBox(widget, box, addToLayout=False)
    else:
        b = widget
    cbox = QtWidgets.QCheckBox(label, b)

    if labelWidth:
        cbox.setFixedSize(labelWidth, cbox.sizeHint().height())
    cbox.setChecked(getdeepattr(master, value))

    connectControl(master, value, None, cbox.toggled[bool],
                   CallFrontCheckBox(cbox),
                   cfunc=callback and FunctionCallback(
                       master, callback, widget=cbox, getwidget=getwidget,
                       id=id_))
    if isinstance(disables, QtWidgets.QWidget):
        disables = [disables]
    cbox.disables = disables or []
    cbox.makeConsistent = Disabler(cbox, master, value)
    cbox.toggled[bool].connect(cbox.makeConsistent)
    cbox.makeConsistent(value)
    miscellanea(cbox, b, widget, **misc)
    return cbox


def checkButtonOffsetHint(button, style=None):
    QStyle = QtWidgets.QStyle
    option = QtWidgets.QStyleOptionButton()
    option.initFrom(button)
    if style is None:
        style = button.style()
    if isinstance(button, QtWidgets.QCheckBox):
        pm_spacing = QStyle.PM_CheckBoxLabelSpacing
        pm_indicator_width = QStyle.PM_IndicatorWidth
    else:
        pm_spacing = QStyle.PM_RadioButtonLabelSpacing
        pm_indicator_width = QStyle.PM_ExclusiveIndicatorWidth
    space = style.pixelMetric(pm_spacing, option, button)
    width = style.pixelMetric(pm_indicator_width, option, button)
    # TODO: add other styles (Maybe load corrections from .cfg file?)
    style_correction = {"macintosh (aqua)": -2, "macintosh(aqua)": -2,
                        "plastique": 1, "cde": 1, "motif": 1}
    return space + width + \
        style_correction.get(
            QtWidgets.QApplication.style().objectName().lower(), 0)


DISABLER = 1
HIDER = 2


class Disabler:
    def __init__(self, widget, master, valueName, propagateState=True,
                 type=DISABLER):
        self.widget = widget
        self.master = master
        self.valueName = valueName
        self.propagateState = propagateState
        self.type = type

    def __call__(self, *value):
        # If self.propagateState is True (default), then if check box is
        # disabled the related widgets will be disabled (even if the checkbox is
        # checked). If self.propagateState is False, the related widgets will be
        # disabled/enabled if check box is checked/clear, disregarding whether the
        # check box itself is enabled or not.
        currState = self.widget.isEnabled()
        if currState or not self.propagateState:
            if len(value):
                disabled = not value[0]
            else:
                disabled = not getdeepattr(self.master, self.valueName)
        else:
            disabled = True
        for w in self.widget.disables:
            if isinstance(w, tuple):
                if isinstance(w[0], int):
                    i = 1
                    if w[0] == -1:
                        disabled = not disabled
                else:
                    i = 0
                if self.type == DISABLER:
                    w[i].setDisabled(disabled)
                elif self.type == HIDER:
                    if disabled:
                        w[i].hide()
                    else:
                        w[i].show()
                if hasattr(w[i], "makeConsistent"):
                    w[i].makeConsistent()
            else:
                if self.type == DISABLER:
                    w.setDisabled(disabled)
                elif self.type == HIDER:
                    if disabled:
                        w.hide()
                    else:
                        w.show()


class CallFrontCheckBox(ControlledCallFront):
    def action(self, value):
        if value is not None:
            values = [Qt.Unchecked, Qt.Checked, Qt.PartiallyChecked]
            self.control.setCheckState(values[value])


