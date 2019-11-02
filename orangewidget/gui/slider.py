import math

from AnyQt import QtWidgets
from AnyQt.QtCore import Qt, QObject, pyqtSignal as Signal, QTimer

from orangewidget.utils import getdeepattr
from .utils import *
from .label import widgetLabel


__all__ = ["hSlider", "labeledSlider", "valueSlider",
           "FloatSlider"]


class DelayedNotification(QObject):
    """
    A proxy for successive calls/signals that emits a signal
    only when there are no calls for a given time.

    Also allows for mechanism that prevents successive equivalent calls:
    ff values are passed to the "changed" method, a signal is only emitted
    if the last passed values differ from the last passed values at the
    previous emission.
    """
    notification = Signal()

    def __init__(self, parent=None, timeout=500):
        super().__init__(parent=parent)
        self.timeout = timeout
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.notify_immediately)
        self._did_notify = False  # if anything was sent at all
        self._last_value = None  # last value passed to changed
        self._last_notified = None  # value at the last notification

    def changed(self, *args):
        self._last_value = args
        self._timer.start(self.timeout)

    def notify_immediately(self):
        self._timer.stop()
        if self._did_notify and self._last_notified == self._last_value:
            return
        self._last_notified = self._last_value
        self._did_notify = True
        self.notification.emit()


def hSlider(widget, master, value, box=None, minValue=0, maxValue=10, step=1,
            callback=None, callback_finished=None, label=None, labelFormat=" %d", ticks=False,
            divideFactor=1.0, vertical=False, createLabel=True, width=None,
            intOnly=True, **misc):
    """
    Construct a slider.

    :param widget: the widget into which the box is inserted
    :type widget: QWidget or None
    :param master: master widget
    :type master: OWBaseWidget or OWComponent
    :param value: the master's attribute with which the value is synchronized
    :type value:  str
    :param box: tells whether the widget has a border, and its label
    :type box: int or str or None
    :param label: a label that is inserted into the box
    :type label: str
    :param callback: a function that is called when the value is changed
    :type callback: function
    :param callback_finished: a function that is called when the slider value
        stopped changing for at least 500 ms or when the slider is released
    :type callback_finished: function
    :param minValue: minimal value
    :type minValue: int or float
    :param maxValue: maximal value
    :type maxValue: int or float
    :param step: step size
    :type step: int or float
    :param labelFormat: the label format; default is `" %d"`
    :type labelFormat: str
    :param ticks: if set to `True`, ticks are added below the slider
    :type ticks: bool
    :param divideFactor: a factor with which the displayed value is divided
    :type divideFactor: float
    :param vertical: if set to `True`, the slider is vertical
    :type vertical: bool
    :param createLabel: unless set to `False`, labels for minimal, maximal
        and the current value are added to the widget
    :type createLabel: bool
    :param width: the width of the slider
    :type width: int
    :param intOnly: if `True`, the slider value is integer (the slider is
        of type :obj:`QSlider`) otherwise it is float
        (:obj:`FloatSlider`, derived in turn from :obj:`QSlider`).
    :type intOnly: bool
    :rtype: :obj:`QSlider` or :obj:`FloatSlider`
    """
    sliderBox = hBox(widget, box, addToLayout=False)
    if label:
        widgetLabel(sliderBox, label)
    sliderOrient = Qt.Vertical if vertical else Qt.Horizontal
    if intOnly:
        slider = QtWidgets.QSlider(sliderOrient, sliderBox)
        slider.setRange(minValue, maxValue)
        if step:
            slider.setSingleStep(step)
            slider.setPageStep(step)
            slider.setTickInterval(step)
        signal = slider.valueChanged[int]
    else:
        slider = FloatSlider(sliderOrient, minValue, maxValue, step)
        signal = slider.valueChangedFloat[float]
    sliderBox.layout().addWidget(slider)
    slider.setValue(getdeepattr(master, value))
    if width:
        slider.setFixedWidth(width)
    if ticks:
        slider.setTickPosition(Qt.Widgets.QSlider.TicksBelow)
        slider.setTickInterval(ticks)

    if createLabel:
        label = QtWidgets.QLabel(sliderBox)
        sliderBox.layout().addWidget(label)
        label.setText(labelFormat % minValue)
        width1 = label.sizeHint().width()
        label.setText(labelFormat % maxValue)
        width2 = label.sizeHint().width()
        label.setFixedSize(max(width1, width2), label.sizeHint().height())
        txt = labelFormat % (getdeepattr(master, value) / divideFactor)
        label.setText(txt)
        label.setLbl = lambda x: \
            label.setText(labelFormat % (x / divideFactor))
        signal.connect(label.setLbl)

    connectControl(master, value, callback, signal, CallFrontHSlider(slider))

    if callback_finished:
        dn = DelayedNotification(slider, timeout=500)
        dn.notification.connect(callback_finished)
        signal.connect(dn.changed)
        slider.sliderReleased.connect(dn.notify_immediately)

    miscellanea(slider, sliderBox, widget, **misc)
    return slider


def labeledSlider(widget, master, value, box=None,
                  label=None, labels=(), labelFormat=" %d", ticks=False,
                  callback=None, vertical=False, width=None, **misc):
    """
    Construct a slider with labels instead of numbers.

    :param widget: the widget into which the box is inserted
    :type widget: QWidget or None
    :param master: master widget
    :type master: OWBaseWidget or OWComponent
    :param value: the master's attribute with which the value is synchronized
    :type value:  str
    :param box: tells whether the widget has a border, and its label
    :type box: int or str or None
    :param label: a label that is inserted into the box
    :type label: str
    :param labels: labels shown at different slider positions
    :type labels: tuple of str
    :param callback: a function that is called when the value is changed
    :type callback: function

    :param ticks: if set to `True`, ticks are added below the slider
    :type ticks: bool
    :param vertical: if set to `True`, the slider is vertical
    :type vertical: bool
    :param width: the width of the slider
    :type width: int
    :rtype: :obj:`QSlider`
    """
    sliderBox = hBox(widget, box, addToLayout=False)
    if label:
        widgetLabel(sliderBox, label)
    sliderOrient = Qt.Vertical if vertical else Qt.Horizontal
    slider = QtWidgets.QSlider(sliderOrient, sliderBox)
    slider.ogValue = value
    slider.setRange(0, len(labels) - 1)
    slider.setSingleStep(1)
    slider.setPageStep(1)
    slider.setTickInterval(1)
    sliderBox.layout().addWidget(slider)
    slider.setValue(labels.index(getdeepattr(master, value)))
    if width:
        slider.setFixedWidth(width)
    if ticks:
        slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        slider.setTickInterval(ticks)

    max_label_size = 0
    slider.value_label = value_label = QtWidgets.QLabel(sliderBox)
    value_label.setAlignment(Qt.AlignRight)
    sliderBox.layout().addWidget(value_label)
    for lb in labels:
        value_label.setText(labelFormat % lb)
        max_label_size = max(max_label_size, value_label.sizeHint().width())
    value_label.setFixedSize(max_label_size, value_label.sizeHint().height())
    value_label.setText(getdeepattr(master, value))
    if isinstance(labelFormat, str):
        value_label.set_label = lambda x: \
            value_label.setText(labelFormat % x)
    else:
        value_label.set_label = lambda x: value_label.setText(labelFormat(x))
    slider.valueChanged[int].connect(value_label.set_label)

    connectControl(master, value, callback, slider.valueChanged[int],
                   CallFrontLabeledSlider(slider, labels),
                   CallBackLabeledSlider(slider, master, labels))

    miscellanea(slider, sliderBox, widget, **misc)
    return slider


def valueSlider(widget, master, value, box=None, label=None,
                values=(), labelFormat=" %d", ticks=False,
                callback=None, vertical=False, width=None, **misc):
    """
    Construct a slider with different values.

    :param widget: the widget into which the box is inserted
    :type widget: QWidget or None
    :param master: master widget
    :type master: OWBaseWidget or OWComponent
    :param value: the master's attribute with which the value is synchronized
    :type value:  str
    :param box: tells whether the widget has a border, and its label
    :type box: int or str or None
    :param label: a label that is inserted into the box
    :type label: str
    :param values: values at different slider positions
    :type values: list of int
    :param labelFormat: label format; default is `" %d"`; can also be a function
    :type labelFormat: str or func
    :param callback: a function that is called when the value is changed
    :type callback: function

    :param ticks: if set to `True`, ticks are added below the slider
    :type ticks: bool
    :param vertical: if set to `True`, the slider is vertical
    :type vertical: bool
    :param width: the width of the slider
    :type width: int
    :rtype: :obj:`QSlider`
    """
    if isinstance(labelFormat, str):
        labelFormat = lambda x, f=labelFormat: f % x

    sliderBox = hBox(widget, box, addToLayout=False)
    if label:
        widgetLabel(sliderBox, label)
    slider_orient = Qt.Vertical if vertical else Qt.Horizontal
    slider = QtWidgets.QSlider(slider_orient, sliderBox)
    slider.ogValue = value
    slider.setRange(0, len(values) - 1)
    slider.setSingleStep(1)
    slider.setPageStep(1)
    slider.setTickInterval(1)
    sliderBox.layout().addWidget(slider)
    slider.setValue(values.index(getdeepattr(master, value)))
    if width:
        slider.setFixedWidth(width)
    if ticks:
        slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        slider.setTickInterval(ticks)

    max_label_size = 0
    slider.value_label = value_label = QtWidgets.QLabel(sliderBox)
    value_label.setAlignment(Qt.AlignRight)
    sliderBox.layout().addWidget(value_label)
    for lb in values:
        value_label.setText(labelFormat(lb))
        max_label_size = max(max_label_size, value_label.sizeHint().width())
    value_label.setFixedSize(max_label_size, value_label.sizeHint().height())
    value_label.setText(labelFormat(getdeepattr(master, value)))
    value_label.set_label = lambda x: value_label.setText(labelFormat(values[x]))
    slider.valueChanged[int].connect(value_label.set_label)

    connectControl(master, value, callback, slider.valueChanged[int],
                   CallFrontLabeledSlider(slider, values),
                   CallBackLabeledSlider(slider, master, values))

    miscellanea(slider, sliderBox, widget, **misc)
    return slider


class CallBackLabeledSlider:
    def __init__(self, control, widget, lookup):
        self.control = control
        self.widget = widget
        self.lookup = lookup
        self.disabled = False

    def __call__(self, *_):
        if not self.disabled and self.control.ogValue is not None:
            self.widget.__setattr__(self.control.ogValue,
                                    self.lookup[self.control.value()])


class CallFrontHSlider(ControlledCallFront):
    def action(self, value):
        if value is not None:
            self.control.setValue(value)


class CallFrontLabeledSlider(ControlledCallFront):
    def __init__(self, control, lookup):
        super().__init__(control)
        self.lookup = lookup

    def action(self, value):
        if value is not None:
            self.control.setValue(self.lookup.index(value))


class CallFrontLogSlider(ControlledCallFront):
    def action(self, value):
        if value is not None:
            if value < 1e-30:
                print("unable to set %s to %s (value too small)" %
                      (self.control, value))
            else:
                self.control.setValue(math.log10(value))


class FloatSlider(QtWidgets.QSlider):
    """
    Slider for continuous values.

    The slider is derived from `QtGui.QSlider`, but maps from its discrete
    numbers to the desired continuous interval.
    """
    valueChangedFloat = Signal(float)

    def __init__(self, orientation, min_value, max_value, step, parent=None):
        super().__init__(orientation, parent)
        self.setScale(min_value, max_value, step)
        self.valueChanged[int].connect(self._send_value)

    def _update(self):
        self.setSingleStep(1)
        if self.min_value != self.max_value:
            self.setEnabled(True)
            self.setMinimum(int(round(self.min_value / self.step)))
            self.setMaximum(int(round(self.max_value / self.step)))
        else:
            self.setEnabled(False)

    def _send_value(self, slider_value):
        value = min(max(slider_value * self.step, self.min_value),
                    self.max_value)
        self.valueChangedFloat.emit(value)

    def setValue(self, value):
        """
        Set current value. The value is divided by `step`

        Args:
            value: new value
        """
        super().setValue(int(round(value / self.step)))

    def setScale(self, minValue, maxValue, step=0):
        """
        Set slider's ranges (compatibility with qwtSlider).

        Args:
            minValue (float): minimal value
            maxValue (float): maximal value
            step (float): step
        """
        if minValue >= maxValue:
            ## It would be more logical to disable the slider in this case
            ## (self.setEnabled(False))
            ## However, we do nothing to keep consistency with Qwt
            # TODO If it's related to Qwt, remove it
            return
        if step <= 0 or step > (maxValue - minValue):
            if isinstance(maxValue, int) and isinstance(minValue, int):
                step = 1
            else:
                step = float(minValue - maxValue) / 100.0
        self.min_value = float(minValue)
        self.max_value = float(maxValue)
        self.step = step
        self._update()

    def setRange(self, minValue, maxValue, step=1.0):
        """
        Set slider's ranges (compatibility with qwtSlider).

        Args:
            minValue (float): minimal value
            maxValue (float): maximal value
            step (float): step
        """
        # For compatibility with qwtSlider
        # TODO If it's related to Qwt, remove it
        self.setScale(minValue, maxValue, step)
