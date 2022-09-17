import operator
from itertools import chain

__all__ = 'Array',


class classproperty(object):
    # https://stackoverflow.com/a/5192374/1868332
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


class Array(list):
    @classproperty
    def new(cls):
        return cls

    def __getitem__(self, obj):
        if isinstance(obj, slice):
            return self.new(super().__getitem__(obj))
        return super().__getitem__(obj)

    def __bool__(self):
        return any(a for a in self)

    def __pow__(self, e):
        return self.new(a**e for a in self)

    def __neg__(self):
        return self.new(-a for a in self)

    def __invert__(self):
        return self.new(~a for a in self)

    def __xor__(self, other):
        return self._binary_operator(operator.xor, other)

    def __rxor__(self, other):
        return self._binary_operator_right(operator.xor, other)

    def __or__(self, other):
        return self._binary_operator(operator.or_, other)

    def __ror__(self, other):
        return self._binary_operator_right(operator.or_, other)

    def __and__(self, other):
        return self._binary_operator(operator.and_, other)

    def __rand__(self, other):
        return self._binary_operator_right(operator.and_, other)

    def __add__(self, other):
        return self._binary_operator(operator.add, other)

    def __radd__(self, other):
        return self._binary_operator_right(operator.add, other)

    def __iadd__(self, other):
        """Replace default list's extend implementation."""
        return self + other

    def __sub__(self, other):
        return self._binary_operator(operator.sub, other)

    def __rsub__(self, other):
        return self._binary_operator_right(operator.sub, other)

    def __mul__(self, other):
        return self._binary_operator(operator.mul, other)

    def __rmul__(self, other):
        return self._binary_operator_right(operator.mul, other)

    def _binary_operator(self, operator, other):
        """ binary operation between `self` and `other`, note that `operator` does not have to be
        commutative. """
        if isinstance(other, type(self)):
            self._ensure_eq_len(other)
            return self.new(operator(a, b) for a, b in zip(self, other))

        if isinstance(other, tuple) or isinstance(other, list):
            raise TypeError(f"Wrong operand type {type(other)}.")

        return self.new(operator(a, other) for a in self)

    def _binary_operator_right(self, operator, other):
        if isinstance(other, tuple) or isinstance(other, list):
            raise TypeError(f"Wrong operand type {type(other)}.")

        return self.new(operator(other, a) for a in self)

    def _ensure_eq_len(self, other):
        if len(other) != len(self):
            raise ValueError(f"Arrays of length {len(self)} and {len(other)} not aligned")

    def map(self, func):
        return self.new(func(a) for a in self)

    @classmethod
    def concat(cls, *args):
        return cls.new(chain(*args))

    @classmethod
    def dup(cls, element, n):
        return cls.new((element,) * n)

    def repeat(self, n):
        return self.newconcat(*([self]*n))

    def dot(self, other):
        self._ensure_eq_len(other)
        return sum(self * other)

    # def reshape(self, row, col):
    #     if row * col != len(self):
    #         raise ValueError(f"Reshape dims ({row}, {col}) and array length {len(self)} not aligned")
    #     return Array2D.from_array(self, row, col)

    def rol(self, n):
        n %= len(self)
        return self.new(chain(self[n:], self[:n]))

    def ror(self, n):
        return self.rol(-n)

    def padr(self, n, value=0):
        if n < len(self):
            raise ValueError(f"Array length {len(self)} is large than {n}")
        if n == len(self):
            return self
        return self.new.concat(self, self.new.dup(value, n - len(self)))

    def chunks(self, size=None, num=None):
        if size is None:
            size = (len(self) + num - 1) // num   # ceil
        elif num is None:
            num = (len(self) + size - 1) // size  # ceil
        return self.new(self[i:i+size] for i in range(0, len(self), size))

    # def partition(self, *sizes):
    #     assert sum(sizes) == len(self)
    #     ret = []
    #     i = 0
    #     for sz in sizes:
    #         ret.append(self[i:i+sz])
    #         i += sz
    #     return self.new(ret)

    def flatten(self):
        return self.new.concat(*self)
