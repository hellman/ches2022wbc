from collections.abc import Iterable

from circkit import Circuit, Operation, Node


import logging
log = logging.getLogger("Transformer")


class Transformer:
    """Base transformer class."""
    START_FROM_VARS = False

    source_circuit: Circuit = None
    current_node: Node = None
    current_operation: Operation = None

    def transform(self, circuit, **kwargs):
        self.before_transform(circuit, **kwargs)

        self.visit_all(circuit)
        self.output = [
            self.make_output(node, self.result[node])
            for node in circuit.outputs
        ]
        self.transform_output = self.output

        self.after_transform(circuit, **kwargs)  # can change self.transform_output

        return self.transform_output

    def before_transform(self, circuit, **kwargs):
        self.source_circuit = circuit
        self.result = {}

        self._current_stack = []

    def after_transform(self, circuit, **kwargs):
        self.source_circuit = None
        assert not self._current_stack

    def visit_all(self, circuit):
        if self.START_FROM_VARS:
            nodes_to_visit = (
                list(circuit.inputs)
                + [node for node in circuit if not node.is_INPUT()]
            )
        else:
            nodes_to_visit = list(circuit)

        for node in nodes_to_visit:
            self.before_visit(node)
            self.visit(node, *[self.result[sub] for sub in node.incoming])
            self.after_visit(node)

    def before_visit(self, node):
        """Event handler before visiting node"""
        self._current_stack.append((
            self.current_node,
            self.current_operation
        ))
        self.current_node = node
        self.current_operation = node.operation

    def after_visit(self, node):
        """Event handler after visiting node"""
        self.current_node, self.current_operation = self._current_stack.pop()

    def on_visit_error(self, node, err):
        log.error(f"node: {node} err: {err}")
        if hasattr(node, "show_debug"):
            node.show_debug()

    def visit(self, node, *args):
        method_name = f"visit_{node.operation._name}"
        method = getattr(self, method_name, self.visit_generic)
        try:
            result = self.result[node] = method(node, *args)
        except Exception as err:
            if not self.on_visit_error(node, err):
                raise
        return result

    def visit_generic(self, node, *args):
        raise NotImplementedError(
            f"Visit method for {node.operation._name} "
            f"is not implemented in {type(self)}"
        )

    def visit_GET(self, node, multi_result):
        return multi_result[node.operation.index]

    def make_output(self, node, result):
        return result


class CircuitTransformer(Transformer):
    """Base class for circuit->circuit transformers."""
    DEFAULT_CIRCUIT_CLASS = None
    DEFAULT_BASE_RING = None

    AUTO_OUTPUT = True
    NAME_SUFFIX = None

    FORCE_MANY_TO_ONE = False

    def create_target_circuit(
            self,
            source_circuit,
            # keyword-only
            *, name=None, circuit_class=None, base_ring=None, **kwargs):
        if name is None and source_circuit.name and self.NAME_SUFFIX:
            name = source_circuit.name + self.NAME_SUFFIX

        if circuit_class:
            target_circuit_class = circuit_class
        elif self.DEFAULT_CIRCUIT_CLASS:
            target_circuit_class = self.DEFAULT_CIRCUIT_CLASS
        else:
            target_circuit_class = type(source_circuit)

        if base_ring:
            target_base_ring = base_ring
        elif self.DEFAULT_BASE_RING:
            target_base_ring = self.DEFAULT_BASE_RING
        else:
            target_base_ring = source_circuit.base_ring

        log.debug(
            f"{type(self)}: create target circuit {target_circuit_class} "
            f"with ring {base_ring}"
        )
        target_circuit = target_circuit_class(
            base_ring=target_base_ring,
            name=name,
        )
        return target_circuit

    @property
    def base_ring(self):
        return self.target_circuit.base_ring

    # VSN: It is better to write this prototype in a clearer way
    #      so that we can understand what we need to pass for kwargs
    #      (circuit_class, base_ring, etc for create_target_circuit)
    def transform(self, circuit, **kwargs):
        if not isinstance(circuit, Circuit):
            raise TypeError(
                "Transformers are defined only for Circuits,"
                f" passed: {type(circuit)}"
            )
        self.source_circuit = circuit
        if "target_circuit" in kwargs:
            self.target_circuit = kwargs["target_circuit"]
        else:
            self.target_circuit = self.create_target_circuit(circuit, **kwargs)
        super().transform(circuit, **kwargs)
        return self.target_circuit

    def visit_generic(self, node, *args):
        return node.reapply(*args, circuit=self.target_circuit)

    def make_output(self, node, result):
        """ Default implementation: mark images of output notes as outputs in
        new circuit. """
        if not self.AUTO_OUTPUT:
            return

        if isinstance(result, self.target_circuit.Node):
            return self.target_circuit.add_output(result)
        elif isinstance(result, Iterable):
            ret = []
            for result_node in result:
                ret.append(self.target_circuit.add_output(result_node))
            return ret
        else:
            log.error(f"{type(result)} cannot be outputted")
            raise NotImplementedError(f"{type(result)} cannot be outputted")
