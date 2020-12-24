import operator
from weakref import WeakKeyDictionary
from typing import TypeVar, Sequence, Optional, Callable, Any

T = TypeVar("T")


def index_of(
        seq: Sequence[T],
        el: T,
        eq: Callable[[T, T], bool] = operator.eq,
) -> Optional[int]:
    """
    Return index of `el` in `seq` where equality is defined by `eq`.

    Return `None` if not found.
    """
    for i, e in enumerate(seq):
        if eq(el, e):
            return i
    return None


class WeakKeyDefaultDict(WeakKeyDictionary):
    """
    A `WeakKeyDictionary` that also acts like a :class:`collections.defaultdict`
    """
    default_factory: Callable[[], Any]

    def __init__(self, default_factory: Callable[[], Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            value = super().__getitem__(key)
        except KeyError:
            value = self.default_factory()
            self.__setitem__(key, value)
        return value
