from circkit.utils import AliasAttr


class ConstManager:
    def __init__(self, circuit):
        self.circuit = circuit

    def create(self, value):
        """
        Create a constant of unified type
        from value of possibly various types

        Default implementation: no checks, no conversion
        """
        return value

    def output(self, value):
        """
        Convert a constant of unified type to simple representation (e.g. int or string?)
        AU: maybe have different output formats?

        Default implementation: no conversion
        """
        return value


def const_2_int(value):
    if hasattr(value, "integer_representation"):
        # sage's GF(p**k)
        return value.integer_representation()
    # try whatever
    return int(value)


@AliasAttr(ConstManager, "Arithmetic")
class ArithmeticConstManager(ConstManager):
    """
    Generic manager for arithmetic constants.
    Should cover most cases, including SageMath's Zmod, GF(p), GF(q)

    For validation:
        the input value should be of type int or .parent() should return the base_ring

    For conversion:
        int -> const
        tries base_ring.fetch_int(int), otherwise base_ring(int)

        const -> int
        tries base_ring.integer_representation(int), otherwise int(const)
    """

    def __init__(self, circuit):
        super().__init__(circuit)

        self.base_ring = circuit.base_ring
        self.has_int_repr = hasattr(self.base_ring(0), "integer_representation")

    def create(self, value):
        if isinstance(value, self.circuit.Node):
            assert value.operation.opname == "CONST"
            return self.create(value.value)
        if isinstance(value, int) or type(value).__name__ == "Integer":
            if self.has_int_repr:
                return self.base_ring.fetch_int(value)
            return self.base_ring(value)
        elif hasattr(value, "parent") and value.parent().order() == self.base_ring.order():
            return value

        raise TypeError(
            f"Convert {repr(value)} ({type(value)},"
            f" {type(value).__name__}) to const in {self.base_ring}?"
        )

    def output(self, value):
        return const_2_int(value)

    def eq_SUB_ADD(self):
        # deprecated?
        return self.base_ring.characteristic() == 2


@AliasAttr(ConstManager, "Boolean")
class BooleanConstManager(ConstManager):
    """
    Simple Boolean constant manager (0 or 1 only).
    """
    def __init__(self, circuit):
        super().__init__(circuit)

        self.base_ring = None  # for compatability

    def create(self, value):
        if isinstance(value, self.circuit.Node):
            assert value.operation.opname == "CONST"
            return self.create(value.value)

        value = int(value)
        if value not in (0, 1):
            raise ValueError(f"Boolean constant not in {{0, 1}}: {value}")
        return value

    def output(self, value):
        return value
