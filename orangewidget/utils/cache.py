from collections import OrderedDict
from collections.abc import MutableMapping
from typing import NamedTuple


class CacheInfo(NamedTuple):
    misses: int
    hits: int
    maxsize: int
    currsize: int


class LRUCache(MutableMapping):
    __slots__ = ("__dict", "__maxlen", "__miss", "__hit")

    def __init__(self, maxlen=100):
        self.__dict = OrderedDict()
        self.__maxlen = maxlen
        self.__miss = 0
        self.__hit = 0

    def __setitem__(self, key, value):
        dict_ = self.__dict
        dict_[key] = value
        dict_.move_to_end(key)
        if len(dict_) > self.__maxlen:
            dict_.popitem(last=False)

    def __getitem__(self, key):
        dict_ = self.__dict
        try:
            r = dict_[key]
        except KeyError:
            self.__miss += 1
            raise
        else:
            self.__hit += 1
            dict_.move_to_end(key)
            return r

    def __delitem__(self, key):
        del self.__dict[key]

    def __contains__(self, key):
        return key in self.__dict

    def __delete__(self, key):
        del self.__dict[key]

    def __iter__(self):
        return iter(self.__dict)

    def __len__(self):
        return len(self.__dict)

    def cache_info(self):
        return CacheInfo(self.__miss, self.__hit,
                         self.__maxlen, len(self.__dict))

    def clear(self) -> None:
        self.__dict.clear()
        self.__hit = self.__miss = 0
