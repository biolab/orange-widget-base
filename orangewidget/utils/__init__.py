import inspect
import sys
from operator import attrgetter

from AnyQt.QtCore import QObject


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
