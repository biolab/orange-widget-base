import warnings
import contextlib

from AnyQt import QtWidgets
from AnyQt.QtCore import Qt


__all__ = [
    "miscellanea", "setLayout", "separator", "rubber",
    "widgetBox", "hBox", "vBox", "indentedBox",
    "connectControl", "ControlGetter",
    "ControlledCallback", "ValueCallback", "FunctionCallback",
    "ControlledCallFront"
]


def miscellanea(control, box, parent,
                addToLayout=True, stretch=0, sizePolicy=None, addSpace=False,
                disabled=False, tooltip=None, **kwargs):
    """
    Helper function that sets various properties of the widget using a common
    set of arguments.

    The function
    - sets the `control`'s attribute `box`, if `box` is given and `control.box`
    is not yet set,
    - attaches a tool tip to the `control` if specified,
    - disables the `control`, if `disabled` is set to `True`,
    - adds the `box` to the `parent`'s layout unless `addToLayout` is set to
    `False`; the stretch factor can be specified,
    - adds the control into the box's layout if the box is given (regardless
    of `addToLayout`!)
    - sets the size policy for the box or the control, if the policy is given,
    - adds space in the `parent`'s layout after the `box` if `addSpace` is set
    and `addToLayout` is not `False`.

    If `box` is the same as `parent` it is set to `None`; this is convenient
    because of the way complex controls are inserted.

    Unused keyword arguments are assumed to be properties; with this `gui`
    function mimic the behaviour of PyQt's constructors. For instance, if
    `gui.lineEdit` is called with keyword argument `sizePolicy=some_policy`,
    `miscallenea` will call `control.setSizePolicy(some_policy)`.

    :param control: the control, e.g. a `QCheckBox`
    :type control: QWidget
    :param box: the box into which the widget was inserted
    :type box: QWidget or None
    :param parent: the parent into whose layout the box or the control will be
        inserted
    :type parent: QWidget
    :param addSpace: the amount of space to add after the widget
    :type addSpace: bool or int
    :param disabled: If set to `True`, the widget is initially disabled
    :type disabled: bool
    :param addToLayout: If set to `False` the widget is not added to the layout
    :type addToLayout: bool
    :param stretch: the stretch factor for this widget, used when adding to
        the layout (default: 0)
    :type stretch: int
    :param tooltip: tooltip that is attached to the widget
    :type tooltip: str or None
    :param sizePolicy: the size policy for the box or the control
    :type sizePolicy: QtWidgets.QSizePolicy
    """
    for prop, val in kwargs.items():
        if prop == "sizePolicy":
            control.setSizePolicy(QtWidgets.QSizePolicy(*val))
        else:
            getattr(control, "set" + prop[0].upper() + prop[1:])(val)
    if disabled:
        # if disabled==False, do nothing; it can be already disabled
        control.setDisabled(disabled)
    if tooltip is not None:
        control.setToolTip(tooltip)
    if box is parent:
        box = None
    elif box and box is not control and not hasattr(control, "box"):
        control.box = box
    if box and box.layout() is not None and \
            isinstance(control, QtWidgets.QWidget) and \
            box.layout().indexOf(control) == -1:
        box.layout().addWidget(control)
    if sizePolicy is not None:
        if isinstance(sizePolicy, tuple):
            sizePolicy = QtWidgets.QSizePolicy(*sizePolicy)
        (box or control).setSizePolicy(sizePolicy)
    if addToLayout and parent and parent.layout() is not None:
        parent.layout().addWidget(box or control, stretch)
        _addSpace(parent, addSpace)


def _is_horizontal(orientation):
    if isinstance(orientation, str):
        warnings.warn("string literals for orientation are deprecated",
                      DeprecationWarning)
    elif isinstance(orientation, bool):
        warnings.warn("boolean values for orientation are deprecated",
                      DeprecationWarning)
    return (orientation == Qt.Horizontal or
            orientation == 'horizontal' or
            not orientation)


def setLayout(widget, layout):
    """
    Set the layout of the widget.

    If `layout` is given as `Qt.Vertical` or `Qt.Horizontal`, the function
    sets the layout to :obj:`~QVBoxLayout` or :obj:`~QVBoxLayout`.

    :param widget: the widget for which the layout is being set
    :type widget: QWidget
    :param layout: layout
    :type layout: `Qt.Horizontal`, `Qt.Vertical` or instance of `QLayout`
    """
    if not isinstance(layout, QtWidgets.QLayout):
        if _is_horizontal(layout):
            layout = QtWidgets.QHBoxLayout()
        else:
            layout = QtWidgets.QVBoxLayout()
    widget.setLayout(layout)


def _addSpace(widget, space):
    """
    A helper function that adds space into the widget, if requested.
    The function is called by functions that have the `addSpace` argument.

    :param widget: Widget into which to insert the space
    :type widget: QWidget
    :param space: Amount of space to insert. If False, the function does
        nothing. If the argument is an `int`, the specified space is inserted.
        Otherwise, the default space is inserted by calling a :obj:`separator`.
    :type space: bool or int
    """
    if space:
        if type(space) == int:  # distinguish between int and bool!
            separator(widget, space, space)
        else:
            separator(widget)


def separator(widget, width=4, height=4):
    """
    Add a separator of the given size into the widget.

    :param widget: the widget into whose layout the separator is added
    :type widget: QWidget
    :param width: width of the separator
    :type width: int
    :param height: height of the separator
    :type height: int
    :return: separator
    :rtype: QWidget
    """
    sep = QtWidgets.QWidget(widget)
    if widget is not None and widget.layout() is not None:
        widget.layout().addWidget(sep)
    sep.setFixedSize(width, height)
    return sep


def rubber(widget):
    """
    Insert a stretch 100 into the widget's layout
    """
    widget.layout().addStretch(100)


def widgetBox(widget, box=None, orientation=Qt.Vertical, margin=None, spacing=4,
              **misc):
    """
    Construct a box with vertical or horizontal layout, and optionally,
    a border with an optional label.

    If the widget has a frame, the space after the widget is added unless
    explicitly disabled.

    :param widget: the widget into which the box is inserted
    :type widget: QWidget or None
    :param box: tells whether the widget has a border, and its label
    :type box: int or str or None
    :param orientation: orientation of the box
    :type orientation: `Qt.Horizontal`, `Qt.Vertical` or instance of `QLayout`
    :param sizePolicy: The size policy for the widget (default: None)
    :type sizePolicy: :obj:`~QtWidgets.QSizePolicy`
    :param margin: The margin for the layout. Default is 7 if the widget has
        a border, and 0 if not.
    :type margin: int
    :param spacing: Spacing within the layout (default: 4)
    :type spacing: int
    :return: Constructed box
    :rtype: QGroupBox or QWidget
    """
    if box:
        b = QtWidgets.QGroupBox(widget)
        if isinstance(box, str):
            b.setTitle(" " + box.strip() + " ")
        if margin is None:
            margin = 7
    else:
        b = QtWidgets.QWidget(widget)
        b.setContentsMargins(0, 0, 0, 0)
        if margin is None:
            margin = 0
    setLayout(b, orientation)
    b.layout().setSpacing(spacing)
    b.layout().setContentsMargins(margin, margin, margin, margin)
    misc.setdefault('addSpace', bool(box))
    miscellanea(b, None, widget, **misc)
    return b


def hBox(*args, **kwargs):
    return widgetBox(orientation=Qt.Horizontal, *args, **kwargs)


def vBox(*args, **kwargs):
    return widgetBox(orientation=Qt.Vertical, *args, **kwargs)


def indentedBox(widget, sep=20, orientation=Qt.Vertical, **misc):
    """
    Creates an indented box. The function can also be used "on the fly"::

        gui.checkBox(gui.indentedBox(box), self, "spam", "Enable spam")

    To align the control with a check box, use :obj:`checkButtonOffsetHint`::

        gui.hSlider(gui.indentedBox(self.interBox), self, "intervals")

    :param widget: the widget into which the box is inserted
    :type widget: QWidget
    :param sep: Indent size (default: 20)
    :type sep: int
    :param orientation: orientation of the inserted box
    :type orientation: `Qt.Vertical` (default), `Qt.Horizontal` or
            instance of `QLayout`
    :return: Constructed box
    :rtype: QGroupBox or QWidget
    """
    outer = hBox(widget, spacing=0)
    separator(outer, sep, 0)
    indented = widgetBox(outer, orientation=orientation)
    miscellanea(indented, outer, widget, **misc)
    indented.box = outer
    return indented


def connectControl(master, value, f, signal,
                   cfront, cback=None, cfunc=None, fvcb=None):
    cback = cback or value and ValueCallback(master, value, fvcb)
    if cback:
        if signal:
            signal.connect(cback)
        cback.opposite = cfront
        if value and cfront:
            master.connect_control(value, cfront)
    cfunc = cfunc or f and FunctionCallback(master, f)
    if cfunc:
        if signal:
            signal.connect(cfunc)
        cfront.opposite = tuple(x for x in (cback, cfunc) if x)
    return cfront, cback, cfunc


class ControlGetter:
    """
    Provide access to GUI elements based on their corresponding attributes
    in widget.

    Every widget has an attribute `controls` that is an instance of this
    class, which uses the `controlled_attributes` dictionary to retrieve the
    control (e.g. `QCheckBox`, `QComboBox`...) corresponding to the attribute.
    For `OWComponents`, it returns its controls so that subsequent
    `__getattr__` will retrieve the control.
    """
    def __init__(self, widget):
        self.widget = widget

    def __getattr__(self, name):
        widget = self.widget
        callfronts = widget.controlled_attributes.get(name, None)
        if callfronts is None:
            # This must be an OWComponent
            try:
                return getattr(widget, name).controls
            except AttributeError:
                raise AttributeError(
                    "'{}' is not an attribute related to a gui element or "
                    "component".format(name))
        else:
            return callfronts[0].control


@contextlib.contextmanager
def disable_opposite(obj):
    opposite = getattr(obj, "opposite", None)
    if opposite:
        opposite.disabled += 1
        try:
            yield
        finally:
            if opposite:
                opposite.disabled -= 1


class ControlledCallback:
    def __init__(self, widget, attribute, f=None):
        self.widget = widget
        self.attribute = attribute
        self.func = f
        self.disabled = 0
        if isinstance(widget, dict):
            return  # we can't assign attributes to dict
        if not hasattr(widget, "callbackDeposit"):
            widget.callbackDeposit = []
        widget.callbackDeposit.append(self)

    def acyclic_setattr(self, value):
        if self.disabled:
            return
        if self.func:
            if self.func in (int, float) and (
                    not value or isinstance(value, str) and value in "+-"):
                value = self.func(0)
            else:
                value = self.func(value)
        with disable_opposite(self):
            if isinstance(self.widget, dict):
                self.widget[self.attribute] = value
            else:
                setattr(self.widget, self.attribute, value)


class ValueCallback(ControlledCallback):
    # noinspection PyBroadException
    def __call__(self, value):
        if value is None:
            return
        self.acyclic_setattr(value)


class FunctionCallback:
    def __init__(self, master, f, widget=None, id=None, getwidget=False):
        self.master = master
        self.widget = widget
        self.func = f
        self.id = id
        self.getwidget = getwidget
        if hasattr(master, "callbackDeposit"):
            master.callbackDeposit.append(self)
        self.disabled = 0

    def __call__(self, *value):
        if not self.disabled and value is not None:
            kwds = {}
            if self.id is not None:
                kwds['id'] = self.id
            if self.getwidget:
                kwds['widget'] = self.widget
            if isinstance(self.func, list):
                for func in self.func:
                    func(**kwds)
            else:
                self.func(**kwds)


class ControlledCallFront:
    def __init__(self, control):
        self.control = control
        self.disabled = 0

    def action(self, *_):
        pass

    def __call__(self, *args):
        if not self.disabled:
            opposite = getattr(self, "opposite", None)
            if opposite:
                try:
                    for op in opposite:
                        op.disabled += 1
                    self.action(*args)
                finally:
                    for op in opposite:
                        op.disabled -= 1
            else:
                self.action(*args)
