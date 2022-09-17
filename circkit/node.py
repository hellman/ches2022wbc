import warnings
import traceback

from circkit.utils import get_state, set_state, print_stderr

from circkit.operation import UNIT, VARIABLE

from circkit.node_info import NodeInfoDescriptor


class Node:
    """Node in a circuit."""

    circuit: "Circuit" = None
    circuit_class: type = None

    # NOTE: outgoing order is fragile, do not be relied on
    __slots__ = (
        "id",
        "operation", "incoming", "outgoing",
        "n_outputs",
        "location",
        # "_info",
        "__weakref__",
        # "debug_info",  add in a subclass with DEBUG = True
    )
    DEBUG = False

    info = NodeInfoDescriptor()

    def __init__(self, operation, incoming):
        # check that __slots__ work well
        try:
            self.__dict__
        except AttributeError:
            pass
        else:
            warnings.warn(f"node {type(self)} has __dict__: __slots__ not working")

        if self.DEBUG:
            self.debug_info = traceback.format_stack()

        self.id = self.circuit._get_next_node_id()
        self.operation = operation

        self.incoming = tuple(incoming)
        self.outgoing = []
        # self._info = None

        for sub in self.incoming:
            sub.add_outgoing(self)

        self.n_outputs = self.operation.determine_n_outputs(self)
        assert self.n_outputs != VARIABLE

        init_method = getattr(
            self, f"init_{self.operation._name}", self.init_generic
        )
        init_method()

    def init_generic(self):
        pass

    def _set_location(self, location):
        """
        Makes more sense to be set by Circuit at registration.
        """
        self.location = location

    def add_outgoing(self, node=None):
        assert node.circuit is self.circuit
        self.outgoing.append(node)

    def set_outgoing(self, nodes):
        self.outgoing = list(nodes)
        cls = type(self)
        for node in self.outgoing:
            if not isinstance(node, cls):
                raise TypeError("outgoing")

    @property
    def input_id(self):
        return self.circuit._get_node_input_id(self)

    @property
    def output_ids(self):
        return self.circuit._get_node_output_ids(self)

    # similar to is_OPERATION
    def is_OUTPUT(self):
        """
        Returns whether this node is an output node in its circuit.
        """
        return bool(self.output_ids)

    # iterations (GET)
    # -------------------------------------------
    def __bool__(self):
        """
        By default, Python will use __len__ to check bool(node).
        Force `bool(node)` to True, to allow checks against None (if node: ...)
        """
        return True

    def is_iterable(self):
        return self.n_outputs != UNIT

    def __iter__(self):
        return iter(self[i] for i in range(self.n_outputs))

    def __len__(self):
        if self.n_outputs == UNIT:
            raise TypeError("can not iterate %r" % self)
        return self.n_outputs

    def __getitem__(self, index):
        # AU: maybe cache at some point to avoid creating duplicate GETs
        #     but if using tuple unpacking once: a, b, c = node
        #     then no duplicates
        if not self.is_iterable():
            raise TypeError("can not iterate %r" % self)
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index))
        assert -self.n_outputs <= index < self.n_outputs
        return self.circuit.GET(index)(self)

    def siblings_by_outgoing(self, node=None):
        """Find the siblings of current by outgoing nodes
        (or by the single @node node)
        """
        if node:
            if node not in self.outgoing:
                raise ValueError(f"{node} isn't in node")
            outgoing = (node,)
        else:
            outgoing = self.outgoing

        ret = set()
        for node in outgoing:
            for sib in node.incoming:
                if sib is not self:
                    ret.add(sib)
        return ret

    # pickle/copy machinery
    # ----------------------------------------

    def __reduce__(self):
        return (self._reconstruct_object, (self.circuit,), self.__getstate__())

    # slots-aware get/set state
    # __getstate__ = get_state
    # __setstate__ = set_state
    def __getstate__(self):
        data = get_state(self)
        # WARNING:
        # removing outgoing links to prevent pickle recursion limit
        # links are reconstructed later by using incoming links
        # NOTE: may change order of node.outgoing
        if "outgoing" in data:
            del data["outgoing"]
        return data

    def __setstate__(self, data):
        set_state(self, data)
        self.outgoing = []
        for sub in self.incoming:
            sub.add_outgoing(self)

    @staticmethod
    def _reconstruct_object(circuit):
        return circuit.Node.__new__(circuit.Node)

    # information
    # ----------------------------------------

    def __repr__(self):
        incoming = ",".join(map(str, [node.id for node in self.incoming]))
        return f"<{type(self.circuit).__name__}:{self.operation}#{self.id} ({incoming})>"

    def short_repr(self):
        return f"{self.id}:{self.operation}"

    def __hash__(self):
        """
        Used to order sets, etc.
        We only need to make it stable.
        Comparison is still == iff object is the same.
        """
        return hash(self.id)

    def show_debug(self, function=print_stderr):
        if self.DEBUG:
            function("Node creation traceback:")
            for line in self.debug_info:
                function(line.rstrip())
            function("")

    # rebuilding
    # ----------------------------------------

    def reapply(self, *incoming, circuit=None, inherit_info=True, auto_output=False):
        """
        Apply the same operation to new `incoming` nodes/values in th.
        # AU: auto_output option? (outputs in new circuit if is output here)
        """
        for node in incoming:
            if circuit is None:
                circuit = node.circuit
            elif node.circuit is not circuit:
                raise ValueError("reapply to nodes from a mixture of circuits?")
        if circuit is None:
            # could set self.circuit but is unlikely this is useful?
            # reapplying node without inputs? like INPUT or CONST to the same circuit
            raise ValueError("could not determine target circuit to reapply to")

        if circuit is not self.circuit:
            operation = self.operation.reapply(circuit=circuit)

        clone = operation(*incoming)

        if auto_output and self.is_OUTPUT():
            clone.circuit.add_output(clone)

        if inherit_info:
            # TBD: check better options for inherit:
            self.info.inherit_to_node(clone, is_output=True)
        return clone
