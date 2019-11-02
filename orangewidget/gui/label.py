import re

from AnyQt import QtWidgets
from AnyQt.QtCore import Qt

from .utils import *

__all__ = ["label", "widgetLabel"]


__re_label = re.compile(r"(^|[^%])%\((?P<value>[a-zA-Z]\w*)\)")


class CallFrontLabel:
    def __init__(self, control, label, master):
        self.control = control
        self.label = label
        self.master = master

    def __call__(self, *_):
        self.control.setText(self.label % self.master.__dict__)


def label(widget, master, label, labelWidth=None, box=None,
          orientation=Qt.Vertical, **misc):
    """
    Construct a label that contains references to the master widget's
    attributes; when their values change, the label is updated.

    Argument :obj:`label` is a format string following Python's syntax
    (see the corresponding Python documentation): the label's content is
    rendered as `label % master.__dict__`. For instance, if the
    :obj:`label` is given as "There are %(mm)i monkeys", the value of
    `master.mm` (which must be an integer) will be inserted in place of
    `%(mm)i`.

    :param widget: the widget into which the box is inserted
    :type widget: QWidget or None
    :param master: master widget
    :type master: OWBaseWidget or OWComponent
    :param label: The text of the label, including attribute names
    :type label: str
    :param labelWidth: The width of the label (default: None)
    :type labelWidth: int
    :param orientation: layout of the inserted box
    :type orientation: `Qt.Vertical` (default), `Qt.Horizontal` or
        instance of `QLayout`
    :return: label
    :rtype: QLabel
    """
    if box:
        b = widgetBox(widget, box, orientation, addToLayout=False)
    else:
        b = widget

    lbl = QtWidgets.QLabel("", b)
    reprint = CallFrontLabel(lbl, label, master)
    for mo in __re_label.finditer(label):
        master.connect_control(mo.group("value"), reprint)
    reprint()
    if labelWidth:
        lbl.setFixedSize(labelWidth, lbl.sizeHint().height())
    miscellanea(lbl, b, widget, **misc)
    return lbl


def widgetLabel(widget, label="", labelWidth=None, **misc):
    """
    Construct a simple, constant label.

    :param widget: the widget into which the box is inserted
    :type widget: QWidget or None
    :param label: The text of the label (default: None)
    :type label: str
    :param labelWidth: The width of the label (default: None)
    :type labelWidth: int
    :return: Constructed label
    :rtype: QLabel
    """
    lbl = QtWidgets.QLabel(label, widget)
    if labelWidth:
        lbl.setFixedSize(labelWidth, lbl.sizeHint().height())
    miscellanea(lbl, None, widget, **misc)
    return lbl
