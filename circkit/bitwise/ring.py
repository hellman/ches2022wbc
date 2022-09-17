from circkit.utils import AliasAttr
import random

class BitwiseRing:
    """Ring of fixed-width bit-words."""

    def __init__(self, word_size):
        self.word_size = int(word_size)
        assert self.word_size > 0
        self.mask = (1 << self.word_size) - 1

    def __call__(self, value):
        return self.Word(value, ring=self)

    def order(self):
        return 1 << self.word_size

    fetch_int = __call__  # Sage-style API

    def random_element(self):
        r = random.randint(0, self.mask)
        return self.Word(r, ring=self)


@AliasAttr(BitwiseRing)
class Word:
    """Wrapper for a bit-word."""
    __slots__ = "value", "ring"
    def __init__(self, value: int, ring: BitwiseRing):
        self.ring = ring
        self.value = int(value) & self.mask

    @property
    def mask(self):
        return self.ring.mask

    # Sage-style API
    def integer_representation(self):
        return self.value

    def parent(self):
        return self.ring

    # LOGIC OPERATIONS
    # ----------------

    def __xor__(self, b):
        return Word(self.value ^ b.value, self.ring)

    def __or__(self, b):
        return Word(self.value | b.value, self.ring)

    def __and__(self, b):
        return Word(self.value & b.value, self.ring)

    def __invert__(self):
        return Word(~self.value, self.ring)

    # SHIFT OPERATIONS
    # ----------------

    def __lshift__(self, v):
        return Word(self.value << v, self.ring)

    def __rshift__(self, v):
        return Word(self.value >> v, self.ring)

    def rol(self, v):
        v = v % self.ring.word_size
        r = (self.value << v) | (self.value >> (self.ring.word_size - v))
        return Word(r, self.ring)

    def ror(self, v):
        v = v % self.ring.word_size
        r = (self.value >> v) | (self.value << (self.ring.word_size - v))
        return Word(r, self.ring)

    def __add__(self, b):
        return Word(self.value + b.value, self.ring)

    def __sub__(self, b):
        return Word(self.value - b.value, self.ring)

    def __mul__(self, b):
        return Word(self.value * b.value, self.ring)

    def __truediv__(self, b):
        return Word(self.value / b.value, self.ring)

    def __mod__(self, b):
        return Word(self.value % b.value, self.ring)

    def __neg__(self):
        return Word(-self.value, self.ring)

    def lookup_in(self, table):
        pass
    
