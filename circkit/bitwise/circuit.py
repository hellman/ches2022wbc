from circkit import Circuit, Operation, Param

from .const_manager import BitwiseConstManager
from .ring import BitwiseRing


class BitwiseCircuit(Circuit):
    """Generic class for bitwise circuits (unsigned words)."""
    CONST_MANAGER_CLASS = BitwiseConstManager
    DEFAULT_WORD_SIZE = 64

    def __init__(self, *args, word_size=None, **kwargs):
        if word_size is None:
            self.word_size = self.DEFAULT_WORD_SIZE
        else:
            self.word_size = int(word_size)
        if self.word_size <= 0:
            raise ValueError(f"word_size={self.word_size} must be positive!")
        
        self.DEFAULT_BASE_RING = BitwiseRing(self.word_size)

        super().__init__(*args, **kwargs)

    class Operations(Circuit.Operations):
        """Class gathering :class:`.Operation`s of :class:`.ArithmeticCircuit`."""

        # LOGIC OPERATIONS
        # ----------------

        class AND(Operation.Binary):
            SYMMETRIC = True
            def eval(self, a, b):
                return a & b

        class OR(Operation.Binary):
            SYMMETRIC = True
            def eval(self, a, b):
                return a | b

        class XOR(Operation.Binary):
            SYMMETRIC = True
            def eval(self, a, b):
                return a ^ b

        class NOT(Operation.Unary):
            def eval(self, a):
                return ~a

        # SHIFT OPERATIONS
        # ----------------
        class SHL(Operation.Unary):
            """Shift left"""
            shift: Param.Int()  # to constraint or not?
            def eval(self, a):
                return a << self.shift

        class SHR(Operation.Unary):
            """Shift right"""
            shift: Param.Int()  # to constraint or not?
            def eval(self, a):
                return a >> self.shift

        class ROL(Operation.Unary):
            """Rotate left"""
            shift: Param.Int()  # to constraint or not?
            def eval(self, a):
                return a.rol(self.shift)

        class ROR(Operation.Unary):
            """Rotate left"""
            shift: Param.Int()  # to constraint or not?
            def eval(self, a):
                return a.ror(self.shift)

        # ARITHMETIC OPERATIONS
        # ---------------------

        class ADD(Operation.Binary):
            SYMMETRIC = True
            def eval(self, a, b):
                return a + b

        class SUB(Operation.Binary):
            def eval(self, a, b):
                return a - b

        class MUL(Operation.Binary):
            SYMMETRIC = True
            def eval(self, a, b):
                return a * b

        class DIV(Operation.Binary):
            def eval(self, a, b):
                return a / b

        class MOD(Operation.Binary):
            def eval(self, a, b):
                return a % b

        class NEG(Operation.Unary):
            def eval(self, a):
                return -a

        # MISCELLANIOUS
        # -------------

        class LUT(Operation.Unary):
            table: Param.Tuple()
            def eval(self, idx):
                return self.table[idx.value]

        class RND(Operation.Nullary):
            PRECOMPUTABLE = False

            def eval(self):
                return self._circuit.base_ring.random_element()

    class Node(Circuit.Node):
        __slots__ = ()

        def __xor__(self, b):
            return self.circuit.XOR()(self, b)

        def __rxor__(self, b):
            return self.circuit.XOR()(b, self)

        def __or__(self, b):
            return self.circuit.OR()(self, b)

        def __ror__(self, b):
            return self.circuit.OR()(b, self)

        def __and__(self, b):
            return self.circuit.AND()(self, b)

        def __rand__(self, b):
            return self.circuit.AND()(b, self)

        #

        def __invert__(self):
            return self.circuit.NOT()(self)

        #

        def __lshift__(self, v):
            return self.circuit.SHL(v)(self)

        def __rshift__(self, v):
            return self.circuit.SHR(v)(self)

        def rol(self, v):
            return self.circuit.ROL(v)(self)

        def ror(self, v):
            return self.circuit.ROR(v)(self)

        #

        def __add__(self, b):
            return self.circuit.ADD()(self, b)

        def __radd__(self, b):
            return self.circuit.ADD()(b, self)

        def __sub__(self, b):
            return self.circuit.SUB()(self, b)

        def __rsub__(self, b):
            return self.circuit.SUB()(b, self)

        def __mul__(self, b):
            return self.circuit.MUL()(self, b)

        def __rmul__(self, b):
            return self.circuit.MUL()(b, self)

        def __truediv__(self, b):
            return self.circuit.DIV()(self, b)

        def __rtruediv__(self, b):
            return self.circuit.DIV()(b, self)

        def __mod__(self, b):
            return self.circuit.MOD()(self, b)

        def __rmod__(self, b):
            return self.circuit.MOD()(b, self)

        def __neg__(self):
            return self.circuit.NEG()(self)

        def lookup_in(self, table):
            return self.circuit.LUT(table)(self)

