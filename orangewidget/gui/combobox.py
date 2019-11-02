from logging import log

from AnyQt import QtWidgets
from AnyQt.QtCore import Qt

from orangewidget.utils import getdeepattr
from orangewidget.utils.combobox import ComboBox
from orangewidget.utils.itemmodels import PyListModel
from .utils import *
from .label import widgetLabel

__all__ = ["comboBox"]


def comboBox(widget, master, value, box=None, label=None, labelWidth=None,
             orientation=Qt.Vertical, items=(), callback=None,
             sendSelectedValue=None, emptyString=None, editable=False,
             contentsLength=None, maximumContentsLength=25,
             *, model=None, **misc):
    """
    Construct a combo box.

    The `value` attribute of the `master` contains the text or the
    index of the selected item.

    :param widget: the widget into which the box is inserted
    :type widget: QWidget or None
    :param master: master widget
    :type master: OWWidget or OWComponent
    :param value: the master's attribute with which the value is synchronized
    :type value:  str
    :param box: tells whether the widget has a border, and its label
    :type box: int or str or None
    :param orientation: tells whether to put the label above or to the left
    :type orientation: `Qt.Horizontal` (default), `Qt.Vertical` or
        instance of `QLayout`
    :param label: a label that is inserted into the box
    :type label: str
    :param labelWidth: the width of the label
    :type labelWidth: int
    :param callback: a function that is called when the value is changed
    :type callback: function
    :param items: items (optionally with data) that are put into the box
    :type items: tuple of str or tuples
    :param sendSelectedValue: decides whether the `value` contains the text
        of the selected item (`True`) or its index (`False`). If omitted
        (or `None`), the type will match the current value type, or index,
        if the current value is `None`.
    :type sendSelectedValue: bool or `None`
    :param emptyString: the string value in the combo box that gets stored as
        an empty string in `value`
    :type emptyString: str
    :param editable: a flag telling whether the combo is editable
    :type editable: bool
    :param int contentsLength: Contents character length to use as a
        fixed size hint. When not None, equivalent to::

            combo.setSizeAdjustPolicy(
                QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(contentsLength)
    :param int maximumContentsLength: Specifies the upper bound on the
        `sizeHint` and `minimumSizeHint` width specified in character
        length (default: 25, use 0 to disable)
    :rtype: QComboBox
    """
    if box or label:
        hb = widgetBox(widget, box, orientation, addToLayout=False)
        if label is not None:
            widgetLabel(hb, label, labelWidth)
    else:
        hb = widget

    combo = ComboBox(
        hb, maximumContentsLength=maximumContentsLength,
        editable=editable)

    if contentsLength is not None:
        combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(contentsLength)

    combo.box = hb
    combo.label = label
    for item in items:
        if isinstance(item, (tuple, list)):
            combo.addItem(*item)
        else:
            combo.addItem(str(item))

    if value:
        cindex = getdeepattr(master, value)
        if model is not None:
            combo.setModel(model)
        if isinstance(model, PyListModel):
            callfront = CallFrontComboBoxModel(combo, model)
            callfront.action(cindex)
            connectControl(
                master, value, callback, combo.activated[int],
                callfront,
                ValueCallbackComboModel(master, value, model))
        else:
            if isinstance(cindex, str):
                if items and cindex in items:
                    cindex = items.index(cindex)
                else:
                    cindex = 0
            if cindex > combo.count() - 1:
                cindex = 0
            combo.setCurrentIndex(cindex)
            if sendSelectedValue:
                connectControl(
                    master, value, callback, combo.activated[str],
                    CallFrontComboBox(combo, emptyString),
                    ValueCallbackCombo(master, value, emptyString))
            else:
                connectControl(
                    master, value, callback, combo.activated[int],
                    CallFrontComboBox(combo, emptyString))

    if misc.pop("valueType", False):
        log.warning("comboBox no longer accepts argument 'valueType'")
    miscellanea(combo, hb, widget, **misc)
    combo.emptyString = emptyString
    return combo


class ValueCallbackCombo(ValueCallback):
    def __init__(self, widget, attribute, emptyString=""):
        super().__init__(widget, attribute)
        self.emptyString = emptyString

    def __call__(self, value):
        if value == self.emptyString:
            value = ""
        return super().__call__(value)


class ValueCallbackComboModel(ValueCallback):
    def __init__(self, widget, attribute, model):
        super().__init__(widget, attribute)
        self.model = model

    def __call__(self, index):
        # Can't use super here since, it doesn't set `None`'s?!
        return self.acyclic_setattr(self.model[index])


class CallFrontComboBox(ControlledCallFront):
    def __init__(self, control, emptyString=""):
        super().__init__(control)
        self.emptyString = emptyString

    def action(self, value):
        def action_str():
            items = [combo.itemText(i) for i in range(combo.count())]
            try:
                index = items.index(value or self.emptyString)
            except ValueError:
                log.warning("Unable to set '{}' to '{}'; valid values are '{}'".
                            format(self.control, value, ", ".join(items)))
            else:
                self.control.setCurrentIndex(index)

        def action_int():
            if value < combo.count():
                combo.setCurrentIndex(value)
            else:
                log.warning("Unable to set '{}' to {}; largest index is {}".
                            format(combo, value, combo.count() - 1))

        combo = self.control
        if isinstance(value, int):
            action_int()
        else:
            action_str()


class CallFrontComboBoxModel(ControlledCallFront):
    def __init__(self, control, model):
        super().__init__(control)
        self.model = model

    def action(self, value):
        if value == "":  # the latter accomodates PyListModel
            value = None
        if value is None and None not in self.model:
            return  # e.g. values in half-initialized widgets
        if value in self.model:
            self.control.setCurrentIndex(self.model.indexOf(value))
            return
        if isinstance(value, str):
            for i, val in enumerate(self.model):
                if value == str(val):
                    self.control.setCurrentIndex(i)
                    return
        raise ValueError("Combo box does not contain item " + repr(value))
