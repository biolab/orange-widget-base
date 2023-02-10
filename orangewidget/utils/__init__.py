import enum
import inspect
from typing import Union, Iterator, Optional

import sys
import warnings
from operator import attrgetter

from AnyQt.QtCore import QObject, QRect, QSize, QPoint, QTextBoundaryFinder


def progress_bar_milestones(count, iterations=100):
    return set([int(i*count/float(iterations)) for i in range(iterations)])


_NOTSET = object()


def deepgetattr(obj, attr, default=_NOTSET):
    """Works exactly like getattr(), except that attr can be a nested attribute
    (e.g. "attr1.attr2.attr3").
    """
    try:
        return attrgetter(attr)(obj)
    except AttributeError:
        if default is _NOTSET:
            raise
        return default


def getdeepattr(obj, attr, *arg, **kwarg):
    if isinstance(obj, dict):
        return obj.get(attr)
    return deepgetattr(obj, attr, *arg, **kwarg)


def to_html(str):
    return str.replace("<=", "&#8804;").replace(">=", "&#8805;").\
        replace("<", "&#60;").replace(">", "&#62;").replace("=\\=", "&#8800;")

getHtmlCompatibleString = to_html


def dumpObjectTree(obj, _indent=0):
    """
    Dumps Qt QObject tree. Aids in debugging internals.
    See also: QObject.dumpObjectTree()
    """
    assert isinstance(obj, QObject)
    print('{indent}{type} "{name}"'.format(indent=' ' * (_indent * 4),
                                           type=type(obj).__name__,
                                           name=obj.objectName()),
          file=sys.stderr)
    for child in obj.children():
        dumpObjectTree(child, _indent + 1)


def getmembers(obj, predicate=None):
    """Return all the members of an object in a list of (name, value) pairs sorted by name.

    Behaves like inspect.getmembers. If a type object is passed as a predicate,
    only members of that type are returned.
    """

    if isinstance(predicate, type):
        def mypredicate(x):
            return isinstance(x, predicate)
    else:
        mypredicate = predicate
    return inspect.getmembers(obj, mypredicate)


class DeprecatedSignal:
    def __init__(self, actual_signal, *args,
                 warning_text='Deprecated', emit_callback=None, **kwargs):
        self.signal = actual_signal
        self.warning_text = warning_text
        self.emit_callback = emit_callback

    def emit(self, *args, **kwargs):
        warnings.warn(
            self.warning_text,
            DeprecationWarning, stacklevel=2
        )
        if self.emit_callback:
            self.emit_callback(*args, **kwargs)
        return self.signal.emit(*args, **kwargs)

    def __getattr__(self, item):
        return self.__signal.item


def enum_as_int(value: Union[int, enum.Enum]) -> int:
    """
    Return a `enum.Enum` value as an `int.

    This is function intended for extracting underlying Qt5/6 enum
    values specifically with PyQt6 where most Qt enums are represented
    with `enum.Enum` and lose their numerical value.

    >>> from PyQt6.QtCore import Qt
    >>> enum_as_int(Qt.Alignment.AlignLeft)
    1
    """
    if isinstance(value, enum.Enum):
        return int(value.value)
    else:
        return int(value)


def dropdown_popup_geometry(
        size: QSize, origin: QRect, screen: QRect, preferred_direction="down"
) -> QRect:
    """
    Move/constrain the geometry for a drop down popup.

    Parameters
    ----------
    size : QSize
        The base popup size if not constrained.
    origin : QRect
        The origin rect from which the popup extends (in screen coords.).
    screen : QRect
        The available screen geometry into which the popup must fit.
    preferred_direction : str
        'up' or 'down'

    Returns
    -------
    geometry: QRect
        Constrained drop down list geometry to fit into screen
    """
    if preferred_direction == "down":
        # if the popup  geometry extends bellow the screen and there is more
        # room above the popup origin ...
        geometry = QRect(origin.bottomLeft() + QPoint(0, 1), size)
        if geometry.bottom() > screen.bottom() \
                and origin.center().y() > screen.center().y():
            # ...flip the rect about the origin so it extends upwards
            geometry.moveBottom(origin.top() - 1)
    elif preferred_direction == "up":
        geometry = QRect(origin.topLeft() - QPoint(0, 1 + size.height()), size)
        if geometry.top() < screen.top() \
                and origin.center().y() < screen.center().y():
            # ... flip, extend down
            geometry.moveTop(origin.bottom() - 1)
    else:
        raise ValueError(f"Invalid 'preferred_direction' ({preferred_direction})")

    # fixup horizontal position if it extends outside the screen
    if geometry.left() < screen.left():
        geometry.moveLeft(screen.left())
    if geometry.right() > screen.right():
        geometry.moveRight(screen.right())

    # bounded by screen geometry
    return geometry.intersected(screen)


def graphemes(text: str) -> Iterator[str]:
    """
    Return an iterator over grapheme clusters of text
    """
    # match internal QString encoding
    text_encoded = text.encode("utf-16-le")
    finder = QTextBoundaryFinder(QTextBoundaryFinder.Grapheme, text)
    start = 0
    while True:
        pos = finder.toNextBoundary()
        if pos == -1:
            return
        yield text_encoded[start*2: pos*2].decode("utf-16-le")
        start = pos


def grapheme_slice(text: str, start: int = 0, end: int = None) -> str:
    """
    Return a substring of text counting grapheme clusters not codepoints.
    """
    if start < 0 or (end is not None and end < 0):
        raise ValueError("negative start or end")

    s = 0
    slice_start: Optional[int] = None
    slice_end: Optional[int] = None
    for i, g in enumerate(graphemes(text)):
        if i == start:
            slice_start = s
        if i + 1 == end:
            slice_end = s + len(g)
            break
        s += len(g)
    if slice_start is None:
        return ""
    if slice_end is None:
        slice_end = len(text)
    return text[slice_start: slice_end]
