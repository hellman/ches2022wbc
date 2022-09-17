from .core import CircuitTransformer
from ..array import Array


class IswOnArithmetic(CircuitTransformer):
    def __init__(self, order: int):
        """
        Arguments
        ---------
        :order: ISW masking order
        """
        super().__init__()
        self.order = order
        self.n_shares = order + 1

    def visit_INPUT(self, node):
        shares = []
        for i in range(self.n_shares):
            new_name = f"{node.operation.name}_share{i}"
            x = self.target_circuit.add_input(new_name)
            shares.append(x)
        shares = Array(shares)

        return shares

    def visit_ADD(self, node, x, y):
        return x + y
    visit_XOR = visit_ADD

    def visit_MUL(self, node, x, y):
        r = [[0] * self.n_shares for _ in range(self.n_shares)]
        for i in range(self.n_shares):
            for j in range(i+1, self.n_shares):
                r[i][j] = self.target_circuit.RND()()
                r[j][i] = r[i][j] + x[i]*y[j] + x[j]*y[i]

        z = x * y
        for i in range(self.n_shares):
            for j in range(self.n_shares):
                if i != j:
                    z[i] = z[i] - r[i][j]
        return z
    visit_AND = visit_MUL

    def visit_CONST(self, node):
        shares = Array(self.target_circuit.RND()() for i in range(self.order))

        c = self.target_circuit.add_const(node.operation.value)
        for i in range(self.order):
            c = c + shares[i]

        shares.append(c)
        return shares

