import logging

from queue import Queue
from collections import Counter
from collections.abc import Mapping

from contextlib import contextmanager

from circkit.node import Node
from circkit.operation import Operation, UNIT
from circkit.param import Param
from circkit.const_manager import ConstManager

from circkit.node_info import NodeInfoStorage
from circkit.location import Location

from circkit.utils import set_state, PicklableWeakValueDictionary

log = logging.getLogger("Circuit")


class BaseCircuit:
    """Base circuit class, defining all the "magic" of
    :class:`.Operation`s and :class:`.Node`s.

    Responsible for tracking :class:`.Operation` classes,
    dynamically subclassing :class:`.Operation` and :class:`.Node` classes,
    and copying/pickling.
    """

    class Operations:
        """Container of Operation classes.
        Apriori is not linked to any Circuit class,
        can be reused/inherited from.
        """
        by_name: dict

    # list of operations in the circuit Class
    # overriden later by the list for the circuit instance
    operations: dict

    Node = Node

    def __init_subclass__(cls):
        # collect specs, from base to current Operations class
        # (to allow override)
        by_name = cls.Operations.by_name = {}
        for base in reversed(cls.Operations.mro()):
            if base is object:
                continue
            for name, value in base.__dict__.items():
                if isinstance(value, type) and issubclass(value, Operation):
                    assert name == value.__name__
                    by_name[name] = value

                # if overriden by not an operation, remove previous operation
                else:
                    if name in by_name:
                        del by_name[name]

        # subclass the operations
        # - add ._circuit_class to each operation
        cls.operations = {}
        for name, op in by_name.items():
            # create new op class,
            # connected to the current circuit class
            op = type(
                name, (op,),
                dict(
                    __qualname__=f"{cls.__qualname__}.{name}",
                    __module__=cls.__module__,
                    _circuit_class=cls,
                )
            )
            setattr(cls, name, op)
            cls.operations[name] = op

        # subclass the Node
        # - add .circuit_class to Node class
        cls.Node_unlinked = cls.Node
        cls.Node = type(
            f"{cls.__name__}.Node",
            (cls.Node,),
            dict(
                circuit_class=cls,
                __slots__=(),  # keep slots
                __qualname__=f"{cls.__qualname__}.Node",
                __module__=cls.__module__,
            ),
        )
        # add is_OP methods to Node
        for opname, opcls in cls.operations.items():
            def closure(opname_clo):  # needed to create closure for opname
                def is_op(node):
                    return node.operation._name == opname_clo
                return is_op
            is_op = closure(opname)
            func_name = is_op.__qualname__ = is_op.__name__ = f"is_{opname}"
            setattr(cls.Node, func_name, is_op)

        # add is_OP methods to Operation class/subclass
        # (linked to a Circuit class, but not yet to a Circuit instance)
        # are classmethods
        for opname, opcls in cls.operations.items():
            def closure(opname_clo):  # needed to create closure for opname
                def is_op(op):
                    return op._name == opname_clo
                return is_op
            is_op = classmethod(closure(opname))
            func_name = is_op.__qualname__ = is_op.__name__ = f"is_{opname}"
            for opcls2 in cls.operations.values():
                setattr(opcls2, func_name, is_op)

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        """
        This method creates dynamic subclasses of Node and each Operation,
        to store link to the circuit instance in the class data.
        """
        # subclass each Operation once more ("linked" Operation)
        # - add ._circuit to each op
        # this is the final operation that is called on creating nodes
        # such as `circuit.CONST(5)()`
        for name, op_class in cls.operations.items():
            new_op_class = type(
                name,
                (op_class,),
                dict(
                    _circuit=self,
                    __qualname__=f"{op_class.__qualname__}(linked)",
                    __module__=op_class.__module__,
                )
            )
            setattr(self, name, new_op_class)

        # dict of linked ones (shadows the dict of non-linked,
        # which is still accessible as `type(circuit).operations`)
        self.operations = {
            name: getattr(self, name)
            for name in self.operations
        }

        # event handler
        # (Operation may store circuit-specific information in the circuit)
        for name, op_class in self.operations.items():
            op_class.on_new_circuit(circuit=self)

        # subclass the Node class once more ("linked" Node)
        # - add .circuit to Node class
        self.Node = type(
            "Node",
            (self.Node,),
            dict(
                circuit=self,
                __slots__=(),
                __qualname__=f"{self.Node.__qualname__}(linked)",
                __module__=self.Node.__module__,
            ),
        )
        return self

    # pickle / copy / etc.

    def __getstate__(self):
        dct = self.__dict__.copy()

        # save per-circuit *class* data
        op_class_datas = {}
        for name, op_class in self.operations.items():
            del dct[name]
            op_class_datas[name] = dict(op_class.__dict__)

        dct["operations"] = op_class_datas
        dct["Node"] = dict(self.Node.__dict__)
        return dct

    def __setstate__(self, dct):
        op_class_datas = dct.pop("operations")
        for name, op_class_data in list(op_class_datas.items()):
            set_state(self.operations[name], op_class_data)
        node_class_data = dct.pop("Node")
        set_state(self.Node, node_class_data)
        self.__dict__.update(dct)

        self._node_info_storage._finish_pickle()

        if hasattr(self, "_operations_cache"):
            self._operations_cache._finish_pickle()
        if hasattr(self, "_nodes_cache"):
            self._nodes_cache._finish_pickle()
        return self


class Circuit(BaseCircuit):
    """Main Circuit class, includes skeleton structure and common methods,
    and the basic INPUT, CONST, GET nodes.
    """
    _unnamed_circuit_counter = 1

    CONST_MANAGER_CLASS = ConstManager
    DEFAULT_BASE_RING = None  # class-wide default

    TRACK_PATH = True

    CACHE_OPERATIONS = False
    CACHE_NODES = False
    PRECOMPUTE_CONSTANT_OPERATIONS = False

    class Operations(BaseCircuit.Operations):
        class INPUT(Operation):
            """Input node. Parameters:

            * name (str): name of the input
            """
            n_inputs = 0
            name: Param.InputName()

            PRECOMPUTABLE = False
            UNNAMED_PATTERN = "x%d"

            def __init__(self, name, *args, **kwargs):
                if name is None:
                    name = self._get_unnamed_input_name()
                return super().__init__(name, *args, **kwargs)

            @classmethod
            def _get_unnamed_input_name(cls):
                while True:
                    cntr = cls._circuit._unnamed_input_counter
                    name = cls.UNNAMED_PATTERN % cntr
                    cls._circuit._unnamed_input_counter += 1
                    if name not in cls._circuit._input_names:
                        break
                return name

            @classmethod
            def on_new_circuit(cls, circuit):
                assert circuit is cls._circuit  # current impl.
                circuit._input_names = set()
                circuit._unnamed_input_counter = 0

            def before_create_node(self):
                if self.name in self._circuit._input_names:
                    raise KeyError(
                        f"Repeated input name {self.name} "
                        f"in circuit {self._circuit}"
                    )
                self._circuit._input_names.add(self.name)

            def eval(self, value):
                return value

        class CONST(Operation):
            """Constant node. Parameters:

            * value (circuit constant type): constant value to use
            """
            n_inputs = 0
            value: Param.Const()

            def eval(self):
                return self.value

        class GET(Operation):
            """Getter node for multi-output nodes. Parameters:

            * index (int): index of the element to get
            """
            n_inputs = 1
            index: Param.Int()  # .options(transparent=True)

            def before_create_node(self, node):
                n_outputs = node.n_outputs
                if n_outputs is UNIT:
                    raise TypeError(
                        f"Can not apply GET to {node}: "
                        f"{node.operation} is indivisible"
                    )
                if self.index < -n_outputs or self.index >= n_outputs:
                    raise IndexError(
                        f"can not GET index={self.index} out of n_outputs={n_outputs}"
                    )

            def eval(self, x):
                return x[self.index]

    def __init__(self, base_ring=None, name=None, **kwargs):
        self.clear()

        if name is None:
            name = "Unnamed%d" % self._unnamed_circuit_counter
            # type() to update the class variable
            type(self)._unnamed_circuit_counter = \
                type(self)._unnamed_circuit_counter + 1
        self.name = name

        self.base_ring = base_ring or self.DEFAULT_BASE_RING
        self.const_manager = self.create_const_manager()

    def clear(self):
        self.nodes = []
        self.inputs = []
        self.outputs = []
        self._input_id = {}
        self._output_ids = {}

        self._node_info_storage = NodeInfoStorage()

        if self.CACHE_OPERATIONS:
            self._operations_cache = PicklableWeakValueDictionary()

        if self.CACHE_NODES:
            self._nodes_cache = PicklableWeakValueDictionary()

        self.node_counter = 0

        self.location = Location()

    def create_const_manager(self):
        return self.CONST_MANAGER_CLASS(self)

    def clone_empty(self, base_ring=None, name=None):
        if base_ring is None:
            base_ring = self.base_ring
        return type(self)(base_ring=base_ring, name=name)

    # internal
    # --------------------------------

    def add_node(self, node):
        if node.circuit is not self:
            raise RuntimeError(f"node's circuit {node.circuit} is not self")

        if self.TRACK_PATH:
            node._set_location(self.location)
        self.nodes.append(node)

        if node.operation.is_INPUT():
            self._register_input_node(node)
        return node

    def _get_next_node_id(self):
        new_id = self.node_counter
        self.node_counter += 1
        return new_id

    def _register_input_node(self, node):
        self._input_id[node] = len(self.inputs)
        self.inputs.append(node)

    def _register_output_node(self, node):
        self._output_ids.setdefault(node, []).append(len(self.outputs))
        self.outputs.append(node)

    def _get_node_input_id(self, node):
        return self._input_id.get(node, None)

    def _get_node_output_ids(self, node):
        return tuple(self._output_ids.get(node, ()))

    # nodes
    # -----------------------------------

    @property
    def n_inputs(self):
        return len(self.inputs)

    @property
    def n_outputs(self):
        return len(self.outputs)

    def __len__(self):
        return len(self.nodes)

    def __iter__(self):
        return iter(self.nodes)

    def add_output(self, value):
        if isinstance(value, self.Node):
            if value.is_iterable():
                # unpack the multi-output node
                # TBD: maybe add a flag allowing output multiple nodes as single?
                for sub in value:
                    self.add_output(sub)
            else:
                self._register_output_node(node=value)
            return

        elif isinstance(value, Node):
            raise TypeError(
                f"Can not output the Node {value} from a different circuit"
            )

        try:
            nodes = list(value)
        except TypeError:
            self.add_output(self.add_const(value))
            return
            # raise TypeError("don't know how to output %r" % value)

        for node in nodes:
            # can be a nested list
            self.add_output(node)

    def add_const(self, value):
        return self.CONST(value)()

    def add_input(self, *args, **kwargs):
        return self.INPUT(*args, **kwargs)()

    def add_inputs(self, n, format=None):
        if format is None:
            format = self.INPUT._get_unnamed_input_name() + "_%d"
        return [self.add_input(format % i) for i in range(n)]

    @contextmanager
    def with_location(self, token):
        if not self.TRACK_PATH:
            yield
            return

        # start = len(self.ordered)
        prev_location = self.location
        self.location = self.location + (token,)
        yield
        self.location = prev_location

    # in-place modifications
    # -----------------------------------

    def in_place_remove_unused_nodes(self):
        """
        WARNING: modifies the circuit (and nodes) in place
        """
        q = Queue()

        used = set(self.inputs)
        for node in self.outputs:
            q.put(node)
            used.add(node)

        while not q.empty():
            node = q.get()
            for sub in node.incoming:
                if sub not in used:
                    q.put(sub)
                    used.add(sub)

        if len(used) == len(self.nodes):
            log.info("no unused nodes detected")
            return

        # careful...
        n_before = len(self.nodes)

        self.nodes = [node for node in self.nodes if node in used]
        for node in self.nodes:
            node.outgoing = [node for node in node.outgoing if node in used]

        n_removed = n_before - len(self.nodes)
        log.info(f"removed {n_removed} unused nodes")
        return

    def in_place_remove_duplicate_nodes(self):
        def node_inc(node):
            inc = [sub.id for sub in node.incoming]
            if node.operation.SYMMETRIC:
                inc = sorted(inc)
            return tuple(inc)

        n_removed = 0

        seen = {}
        new_order = []
        for node in self:
            key = node.operation._cache_key, node_inc(node)
            # 128-bit hash to reduce memory footprint
            h = (
                0
                | (hash((0, key)) << 64)
                | (hash((1, key)))
            )

            if node in seen:
                node0 = seen[node]
                if node0.operation != node.operation or node_inc(node0) != node_inc(node):
                    raise RuntimeError(
                        "Hash collision, try extending hash size"
                    )

                n_removed += 1
                # surgery (re-wiring)
                for sub in node.incoming:
                    outgoing = []
                    for out in sub.outgoing:
                        if out is node:
                            out = node0
                        outgoing.append(out)
                    sub.outgoing = outgoing

                for out in node.outgoing:
                    incoming = []
                    for inc in out.incoming:
                        if inc is node:
                            inc = node0
                        incoming.append(inc)
                    sub.incoming = tuple(incoming)
            else:
                seen[h] = node
                new_order.append(node)

        log.info(f"removed {n_removed} duplicate nodes")
        self.nodes[:] = new_order
        return

    def in_place_renumerate(self):
        for i, node in enumerate(self):
            node.id = i

    def in_place_reorder_inputs(self, inputs):
        if len(inputs) != self.n_inputs or set(inputs) != set(self.inputs):
            raise ValueError("the list of inputs does not match")
        self.inputs.clear()
        self._input_id.clear()
        for node in inputs:
            self._register_input_node(node)

    def in_place_reorder_outputs(self, outputs):
        if len(outputs) != self.n_outputs or set(outputs) != set(self.outputs):
            raise ValueError("the list of outputs does not match")
        self.outputs.clear()
        self._output_ids.clear()
        for node in outputs:
            self._register_output_node(node)

    def in_place_reorder_inputs_first(self):
        order = list(self.inputs)
        for node in self:
            if not node.is_INPUT():
                order.append(node)
        assert len(order) == len(self)
        self.nodes = order

    # behavior
    # -----------------------------------
    def trace(self, input, convert_input=True, convert_values=True, as_list=False):
        """Trace the circuit execution on a given input.

        Arguments
        ---------
        input: list[values]
            List of input values, one per input node.
        convert_input: bool = True
            Convert input values using circuits :class:`.ConstManager`?
        convert_values: bool = True
            Convert traced values using circuits :class:`.ConstManager`?
        as_list: bool = False
            Output as list instead (with order defined by the circuit's order)?

        Returns
        -------
        trace : dict[:class:`.Node`, value]

        """
        _, mem = self.evaluate(
            input,
            convert_input=convert_input,
            convert_output=False,
            with_mem=True
        )
        if convert_values:
            mem = {k: self.const_manager.output(v) for k, v in mem.items()}

        if as_list:
            return [mem[node] for node in self]
        else:
            return mem

    def evaluate(self, input, convert_input=True, convert_output=True, with_mem=False):
        """
        convert_input validates and converts input to the base_ring
            element should be disabled e.g. for evaluating on Arrays
            (bit-sliced fashion), or for evaluating on symbolic objects
            (e.g. another circuit nodes).

        convert_output converts the output to a simple value, defined by
            ConstManager maybe later we could specify different formats
            for conversion.
        """
        if len(input) != len(self.inputs):
            raise ValueError(
                f"Number of inputs mismatch: circuit has {len(self.inputs)},"
                f" given {len(input)}")

        if convert_input:
            input = [self.const_manager.create(c) for c in input]

        # initialize memory with inputs
        mem = {
            node: node.operation.eval_with_node(node, value)
            for node, value in zip(self.inputs, input)
        }
        for node in self:
            if node.is_INPUT():
                continue
            args = [mem[sub] for sub in node.incoming]
            mem[node] = node.operation.eval_with_node(node, *args)

        output = [mem[node] for node in self.outputs]

        if convert_output:
            output = [self.const_manager.output(o) for o in output]

        if with_mem:
            return output, mem
        else:
            return output

    # misc
    # -----------------------------------

    def random_inputs(self):
        if not hasattr(self.base_ring, 'random_element'):
            raise NotImplementedError("Do not know how to generate "
                                      "random inputs")
        return [self.base_ring.random_element() for _ in range(self.n_inputs)]

    def digraph(self):
        from graphviz import Digraph

        dot = Digraph()
        for node in self:
            vnode = "v%d" % node.id
            text = node.short_repr()
            color = "black"
            shape = "ellipse"

            if node.operation.is_GET():
                text = str(node.operation.index)
                color = "gray"
                shape = "diamond"
            if node.input_id is not None:
                color = "blue"
            elif node.output_ids:
                color = "red"

            dot.node(vnode, text, color=color, shape=shape)

            for sub in node.incoming:
                vsub = "v%d" % sub.id
                dot.edge(vsub, vnode, style="")
        return dot

    def get_order_starting_with(self, prefix=()):
        res = list(prefix)
        seen = set(prefix)
        for node in self:
            if node not in seen:
                res.append(node)
        return res

    # composition / rebuilding
    # ----------------------------------------

    def reapply(self, circuit, input=None, do_output=True):
        m = {}
        if not input:
            rep = {}
        elif isinstance(input, Mapping):
            rep = input
        else:
            # iterable, convert to Mapping
            if len(input) != self.n_inputs:
                raise ValueError("number of inputs does not match")
            rep = {src: dst for src, dst in zip(self.inputs, input)}

        for node in self:
            if node in rep:
                m[node] = rep[node]
                node.info.inherit_to_node(m[node], is_output=True)
            else:
                incoming = [m[sub] for sub in node.incoming]
                m[node] = node.reapply(*incoming, circuit=circuit)

        if do_output:
            for node in self.outputs:
                circuit.add_output(m[node])
        return m

    def compose(self, *circuits, name=None):
        circuits = circuits[::-1]
        circuits.append(self)

        base = circuits[0]
        C = base.clone_empty(name=name)
        m = base.reapply(C, do_output=False)
        input = [m[node] for node in base.outputs]
        for i, other in enumerate(circuits[1:]):
            assert isinstance(other, Circuit)
            assert len(other.inputs) == len(base.outputs)

            m = self.reapply(C, input=input, do_output=(i == len(circuits) - 1))
            input = [m[node] for node in other.outputs]

            base = other
        return C

    def concat_on_same_inputs(self, *circuits, name=None):
        """Concatenate two or more circuits by reusing the inputs"""
        for other in circuits:
            if other.n_inputs != self.n_inputs:
                raise ValueError(
                    "Number of inputs differs: "
                    f"{self.n_inputs} != {other.n_inputs}"
                )

        C = self.clone_empty(name=name)
        m = self.reapply(C, do_output=True)
        inputs = [m[node] for node in self.inputs]
        for other in circuits:
            other.reapply(C, input=inputs, do_output=True)
        return C

    def concat_parallel(self, *circuits, name=None):
        """Concatenate two or more circuits fully in parallel"""
        C = self.clone_empty(name=name)
        self.reapply(C, do_output=True)
        for other in circuits:
            other.reapply(C, do_output=True)
        return C

    # information
    # ------------------------------------

    def __repr__(self):
        n_in = len(self.inputs)
        n_out = len(self.outputs)
        n_nodes = len(self.nodes)
        name = f"'{self.name}' " if self.name else ""
        return (f"<{type(self).__name__} {name}in:{n_in} "
                f"out:{n_out} nodes:{n_nodes}>")

    def print_stats(self, function=print, tab="   | ", exclude=[], by_address=False):
        """
        Shows basic information about the circuit.

        Example:
            .. code-block:: python

               circuit.print_stats()

            output::

               circuit_name(ArithmeticCircuit):
               32 inputs,   129 outputs,    8487 nodes


        """
        self.counter = counter = self.node_counts()
        remark = ""
        for opname in exclude:
            if opname in self.counter:
                ctr = self.counter.pop(opname)
                remark += f"({ctr} {opname} is excluded)"

        total = sum(counter.values())
        counts = ", ".join(f"{name}:{count} ({count*100/total:.2f}%)"
                           for name, count in counter.most_common())
        name = self.name if self.name else "_"
        function(f"{name}({type(self).__name__}): {remark}")
        function(
            tab
            + f"{len(self.inputs):5d} inputs,"
            + f"{len(self.outputs):5d} outputs,"
            + f"{total:7d} nodes",
        )
        function(tab + f"{counts}")

        if by_address:
            counter = self.node_counts(by_address=True)
            # exploiting that dicts preserve insertion order
            # will not show duplicate areas separately!
            for addr in counter:
                function(tab * len(addr) + str(addr) + f": {counter[addr]}")

    def node_counts(self, by_address=False):
        if by_address:
            counter = Counter()
            for node in self:
                addr = node.info.get(self.NODE_ADDRESS_KEY)
                if addr:
                    for i in range(1, len(addr) + 1):
                        counter[addr[:i]] += 1
            return counter
        counter = Counter()
        for node in self:
            counter[node.operation._name] += 1
        return counter
