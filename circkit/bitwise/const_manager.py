from circkit.utils import AliasAttr
from circkit.const_manager import ConstManager


@AliasAttr(ConstManager, "Bitwise")
class BitwiseConstManager(ConstManager):
    def __init__(self, circuit):
        super().__init__(circuit)
        self.base_ring = circuit.base_ring

    def create(self, value):
        if isinstance(value, self.circuit.Node):
            assert value.operation.opname == "CONST"
            return self.create(value.value)
        
        return self.base_ring(value)

    def output(self, value):
        return value.integer_representation()
