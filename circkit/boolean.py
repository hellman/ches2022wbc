from random import randrange

from circkit import Circuit, Operation, Param
# from circkit.circuit import Table
from circkit.const_manager import ConstManager


class BooleanCircuit(Circuit):
    """Generic class for Boolean circuits (single bits)."""
    CONST_MANAGER_CLASS = ConstManager.Boolean

    class Operations(Circuit.Operations):
        """Class gathering :class:`.Operation`s of :class:`.BooleanCircuit`."""

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
                return 1 ^ a

        # MISCELLANIOUS
        # -------------

        class LUT(Operation.Variadic):
            def eval(self, *args):
                return self.table[args]

        class RND(Operation.Nullary):
            PRECOMPUTABLE = False

            def eval(self):
                return randrange(2)


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

        def __invert__(self):
            return self.circuit.NOT()(self)

        # ADD=SUB=XOR,MUL=AND
        # ---------------
        def __add__(self, b):
            return self.circuit.XOR()(self, b)

        def __radd__(self, b):
            return self.circuit.XOR()(b, self)

        def __sub__(self, b):
            return self.circuit.XOR()(self, b)

        def __rsub__(self, b):
            return self.circuit.XOR()(b, self)

        def __mul__(self, b):
            return self.circuit.AND()(self, b)

        def __rmul__(self, b):
            return self.circuit.AND()(b, self)


class OptBooleanCircuit(BooleanCircuit):
    """Optimized Boolean circuits.

    Optimizations include:

    - caching operations and nodes;
    - precomputing annihilator operations, e.g. a&0 = 0;
    - precomputing identity operations, e.g. a&1 = a, a^0 = a;
    - precomputing constant operations;
    """

    CACHE_OPERATIONS = True
    CACHE_NODES = True
    PRECOMPUTE_CONSTANT_OPERATIONS = True

    class Node(BooleanCircuit.Node):
        __slots__ = ()

        def __xor__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)

            if b.is_CONST() and b.operation.value == 0:
                return self
            if self.is_CONST() and self.operation.value == 0:
                return b

            if b.is_CONST() and b.operation.value == 1:
                return ~self
            if self.is_CONST() and self.operation.value == 1:
                return ~b

            return self.circuit.XOR()(self, b)

        def __rxor__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)

            if b.is_CONST() and b.operation.value == 0:
                return self
            if self.is_CONST() and self.operation.value == 0:
                return b

            if b.is_CONST() and b.operation.value == 1:
                return ~self
            if self.is_CONST() and self.operation.value == 1:
                return ~b

            return self.circuit.XOR()(b, self)

        @staticmethod
        def _and(a, b):
            if b.is_CONST():
                if b.operation.value == 0:
                    return b
                if b.operation.value == 1:
                    return a
                # if b.operation.value == -1:
                #     return -a
            if a.is_CONST():
                if a.operation.value == 0:
                    return a
                if a.operation.value == 1:
                    return b
                # if a.operation.value == -1:
                #     return -b
            return a.circuit.AND()(a, b)

        def __and__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)
            return self._and(self, b)

        def __rand__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)
            return self._and(b, self)

        def __invert__(self):
            if self.is_NOT():
                return self.incoming[0]
            return self.circuit.NOT()(self)
