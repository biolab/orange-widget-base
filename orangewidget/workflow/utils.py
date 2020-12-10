import operator
from typing import TypeVar, Sequence, Optional, Callable

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
