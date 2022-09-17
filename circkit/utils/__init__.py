import sys
import gzip
import bz2
import logging
import math
import pickle
import time
import weakref

from functools import wraps

graphlog = logging.getLogger("graph")


Zfile = gzip.GzipFile
Zfile = bz2.BZ2File


def AliasAttr(target, name=None):
    """
    A decorator to save an object/class as an attribute of target object/class.
    """
    def deco(obj):
        if name is None:
            attr_name = obj.__name__
        else:
            attr_name = name
        setattr(target, attr_name, obj)
        return obj
    return deco


def try_draw_graph(circuit, filename, node_limit=float("+inf")):
    if len(circuit) > node_limit:
        return
    try:
        g = circuit.digraph()
        graphlog.info(f"Drawing graph for {circuit}")
        g.render(filename, cleanup=True)
    except ImportError:
        graphlog.warning(
            f"Failed to draw graph with {len(circuit)} nodes. "
            "graphiz is not installed?"
        )


def timing(prologue=None, epilogue=None, function=print):
    def inner(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if prologue:
                function(prologue)

            time1 = time.time()
            ret = f(*args, **kwargs)
            time2 = time.time()

            function(f"{epilogue} in {time2-time1:.2f}s")

            return ret
        return wrapper
    return inner


def ascii_histogram(counter, function, tab):
    total = sum(counter.values())
    counts = ", ".join(
        f"{size}:{cnt} ({cnt*100/total:.2f}%)"
        for size, cnt in counter.most_common())
    function(tab + counts)

    for size in sorted(counter):
        percentage = counter[size]*100/total
        function(tab + f'{size:2d} [{percentage:5.2f}%] ' +
                 '+' * math.floor(percentage))


def flatten(t): return [item for sublist in t for item in sublist]


def gzpickle_load_from(filename):
    return pickle.load(Zfile(filename, "rb"))


def gzpickle_dump_to(obj, filename):
    with Zfile(filename, "wb") as f:
        pickle.dump(obj, f)


def get_state(self):
    dct = {}
    for sup in reversed(type(self).mro()):
        attr_names = (
            getattr(sup, "__slots__", ())
            + getattr(sup, "__extra_attributes__", ())
        )
        for name in attr_names:
            if hasattr(self, name):
                dct[name] = getattr(self, name)

    # update with current obj dict if it exists
    dct.update(getattr(self, "__dict__", {}))

    if "__weakref__" in dct:
        del dct["__weakref__"]
    return dct


def set_state(dst, src):
    """To update class.__dict__ with dict/map"""
    for name, value in src.items():
        setattr(dst, name, value)
    return dst


class NamedObject:
    """Unique objects, named for debugging purposes"""
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<{self.name}>"

    def __eq__(self, other):
        if type(other) == type(self):
            return self.name == other.name
        return False


def rebuild_class(cls, base, avoid=()):
    avoid = set(avoid) | set(base.__slots__)
    dct = cls.__dict__.copy()
    for key in list(dct.keys()):
        if key in avoid:
            del dct[key]
    return type(cls.__name__, (base,), dct)


def set_defaults(config, defaults):
    for k, v in defaults.items():
        config.setdefault(k, v)


class PicklableWeakValueDictionary(weakref.WeakValueDictionary):
    def __getstate__(self):
        return list(self.items())

    def __setstate__(self, items):
        self.__init__()
        self._keep_ref = items  # keep references during pickling
        self.update(items)
        return self

    def _finish_pickle(self):
        del self._keep_ref


class PicklableWeakKeyDictionary(weakref.WeakKeyDictionary):
    def __getstate__(self):
        return list(self.items())

    def __setstate__(self, items):
        self.__init__()
        self._keep_ref = items  # keep references during pickling
        self.update(items)
        return self

    def _finish_pickle(self):
        del self._keep_ref


class __Obj(list):
    pass


def test_PWVD():
    import pickle, gc

    d = PicklableWeakValueDictionary()

    a = d[1] = __Obj([1111])
    b = d[2] = __Obj([2222])

    s = pickle.dumps(d)
    d2 = pickle.loads(s)

    gc.collect()
    assert list(d2.items()) == [(1, [1111]), (2, [2222])]

    # keep reference
    ref = d2[1]
    d2._finish_pickle()

    gc.collect()
    assert list(d2.items()) == [(1, [1111])]


def print_stderr(*args):
    print(*args, file=sys.stderr)


if __name__ == '__main__':
    test_PWVD()
