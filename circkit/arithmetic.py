from circkit import Circuit, Operation, Param
from circkit.const_manager import ConstManager


class Table(tuple):
    def __getitem__(self, a):
        if isinstance(a, Circuit.Node):
            return a.circuit.LUT(self)(a)
        elif (isinstance(a, tuple)
              and any(isinstance(v, Circuit.Node) for v in a)):
            for v in a:
                if isinstance(v, Circuit.Node):
                    return v.circuit.LUT(self)(*a)
            assert False
        return super().__getitem__(a)


class ArithmeticCircuit(Circuit):
    """Generic class for arithmetic circuits."""

    # None corresponds to default choice:
    #  - base_ring=None: no conversion/validation
    #  - base_ring=Something: use ArithmeticConstManager, a generic manager
    # if need to override, simply specify particular one in a subclass
    CONST_MANAGER_CLASS = None
    DEFAULT_BASE_RING = None

    class Operations(Circuit.Operations):
        """Class gathering :class:`.Operation`s of :class:`.ArithmeticCircuit`."""
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

        class EXP(Operation.Unary):
            # override if fractional powers are needed
            power: Param.Int()
            def eval(self, a):
                return a**self.power

        class INV(Operation.Unary):
            def eval(self, a):
                # e.g. SageMath syntax
                return ~a

        class NEG(Operation.Unary):
            def eval(self, a):
                return -a

        class LUT(Operation.Unary):
            table: Param.Tuple()
            def eval(self, idx):
                if self._circuit.base_ring != None:
                    idx = idx.integer_representation()
                return self.table[idx]

        class RND(Operation.Nullary):
            PRECOMPUTABLE = False
            def eval(self):
                return self._circuit.base_ring.random_element()

    class Node(Circuit.Node):
        __slots__ = ()

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

        def __pow__(self, a):
            return self.circuit.EXP(int(a))(self)

        def __invert__(self):
            return self.circuit.INV()(self)

        def __neg__(self):
            return self.circuit.NEG()(self)

        def lookup_in(self, table):
            return self.circuit.LUT(table)(self)

    def create_const_manager(self):
        clsConstManager = self.CONST_MANAGER_CLASS
        if not clsConstManager:
            if not self.base_ring:
                clsConstManager = ConstManager
            else:
                clsConstManager = ConstManager.Arithmetic
        return clsConstManager(self)

    def to_matrix(self, zero=0, one=1, n_tests=0):
        """
        Attempts to express the circuit as an affine map
        C(x) = A*x + b, where
        A is a matrix
        b is a vector, b = 0 when the map is linear

        Done by evaluating the circuit at unit-vector inputs and at zero vector.
        Does not verify that the circuit is actually linear.

        Note: current implementation does batch execution using Array inputs
              may be doing single calls is more reliable for some circuit variants.

        .. todo:: add option for non-batch execution

        Args:
            zero (const): constant representing zero
            one (const): constant representing one

        Returns:
            Matrix: matrix A
            Array: vector b
        """
        from circkit.array import Array
        assert not n_tests, "not implemented"

        w = len(self.inputs)
        # h = len(self.outputs)
        input = []
        for i in range(w):
            # w+1 to include all-zero vector
            vec = Array([zero]*(w+1))
            vec[i] = one
            input.append(vec)

        # if one wants to convert input, specify arguments zero and one
        output = self.evaluate(
            input,
            convert_input=False,
            convert_output=False,
        )
        for i, node in enumerate(self.outputs):
            if node.is_CONST():
                output[i] = Array([output[i]] * (w+1))

        b = Array(vec[w] for vec in output)
        A = [a[:w] - Array.dup(b[y], w) for y, a in enumerate(output)]
        return A, b


class OptArithmeticCircuit(ArithmeticCircuit):
    """Optimized arithmetic circuits.

    Optimizations include:

    - caching operations and nodes;
    - precomputing annihilator operations, e.g. a*0 = 0;
    - precomputing identity operations, e.g. a*1 = a, a+0 = 0;
    - precomputing constant operations;
    """

    CACHE_OPERATIONS = True
    CACHE_NODES = True
    PRECOMPUTE_CONSTANT_OPERATIONS = True

    class Node(ArithmeticCircuit.Node):
        __slots__ = ()

        def __add__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)

            if b.is_CONST() and b.operation.value == 0:
                return self
            if self.is_CONST() and self.operation.value == 0:
                return b
            return self.circuit.ADD()(self, b)

        def __radd__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)

            if b.is_CONST() and b.operation.value == 0:
                return self
            if self.is_CONST() and self.operation.value == 0:
                return b
            return self.circuit.ADD()(b, self)

        @staticmethod
        def _sub(a, b):
            if b.is_CONST() and b.operation.value == 0:
                return a
            if a.is_CONST() and a.operation.value == 0:
                return -b
            return a.circuit.SUB()(a, b)

        def __sub__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)
            return self._sub(self, b)

        def __rsub__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)
            return self._sub(b, self)

        @staticmethod
        def _mul(a, b):
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
            return a.circuit.MUL()(a, b)

        def __mul__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)
            return self._mul(self, b)

        def __rmul__(self, b):
            if not isinstance(b, type(self)):
                assert not isinstance(b, Circuit.Node)
                b = self.circuit.add_const(b)
            return self._mul(b, self)
