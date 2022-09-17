"""
Operations may include arbitrary parameters. It is important to distinguish
*parameters* (arbitrary objects) from node's *inputs* (other nodes in the
same circuit).

An :class:`Operation` *(sub)class* describes an operation and all its parameters,
including validation of parameters, number of node's inputs and outputs.

An :class:`Operation` *instance* describes a concrete operation with all
parameters set. It does not however define a node in a circuit or node's
inputs/outputs. One Operation instance can be used by multiple nodes.

The node/operation creation API is a double-step call (similar to e.g.
`Keras Layers API <https://keras.io/api/layers/>`_)::

    x = circuit.INPUT("x")()
    xcube = circuit.EXP(3)(x)

    assert issubclass(circuit.EXP, Operation)
    assert isinstance(circuit.EXP(3), Operation)
    assert isinstance(circuit.EXP(3)(x), circuit.Node)


Here, both lines follow this API, in which the first call creates an :class:`Operation`
instance and the second call creates a :class:`circkit.node.Node` instance.

In the first line, we first create
the :class:`.Circuit.INPUT` *operation*, which has the input name "x" as the only parameter:
``circuit.INPUT("x")``. Then, we call this operation without any incoming nodes
to create a new node in the circuit, corresponding to the input "x".

In the second line, we first create the `EXP` operation with the parameter
`power = 3`. We then call this operation with a node as an argument which
defines the incoming node for exponentitation.

The reason for the double-call is to separate clearly the two different
notions - parameters and inputs, and to allow using the full python's call
syntax. For example, we could use keyword args such as ``Circuit.EXP(power=3)``.
This is particularly useful for complex operations to reduce the number of
errors e.g. in parameter/input order.

Defining operation example::

    class NewCircuitType(Circuit):
        class Operations(Circuit.Operations):  # subclass to include
                                               # standard INPUT, GET, CONST
            class ADD(Operation.Binary):
                def eval(self, a, b):
                    return a + b

            class SUB(Operation.Binary):
                SYMMETRIC = False
                def eval(self, a, b):
                    return a - b

            class MIX(Operation.MultiVariadic):
                alpha : Param.Int(min_value=1) = 2

                def determine_n_outputs(self, node):
                    return len(node.incoming)

                def eval(self, *args):
                    t = self.alpha * sum(args)
                    return [a - t for a in args]

Module contents
===============
"""

import warnings

from circkit.utils import NamedObject, get_state, set_state, AliasAttr

from circkit.param import Param

VARIABLE = NamedObject("VARIABLE")
"""Special :attr:`Operation.n_inputs` / :attr:`Operation.n_outputs` value -
unspecified number of inputs/outputs (or determined dynamically)."""

UNIT = NamedObject("UNIT")
"""Special :attr:`Operation.n_outputs` value - non-iterable output."""

# import after since Node uses UNIT and VARIABLE
from circkit.node import Node


class OperationMeta(type):
    """Metaclass for the :class:`.Operation` class.

    Manages definition of operations (classes)
    and creation of operation instances (e.g. preparing parameters,
    caching operatios).
    """
    def __new__(meta, clsname, bases, attrs):
        """Define a new Operation class (in a circuit class).

        1. Parse definitions of parameters from the annotations and
           assignments (defaults).
        2. Update ``__slots__`` to include new parameters.
        3. Collects parameters from superclasses. If such a parameter attribute
           is overriden by a non-parameter attribute, the parameter is excluded.
           This allows e.g. to remove superclass' parameter by setting attribute
           ``param = None``.
        4. Create dynamically new :class:`.Operation` class with given slots
           and parameters descriptions.
        """

        # Collect new parameters from annotations
        # `name: Param() = default`
        new_params = {}
        for name, ann in attrs.get("__annotations__", {}).items():
            if isinstance(ann, Param):
                new_params[name] = ann
                if name in attrs:  # default value
                    new_params[name].set_default(attrs[name])
                    # eject params to allow slot creation
                    # (can not have slot = class variable)
                    del attrs[name]

        # slots in Operation are important as each Node has its own Operation
        # (although dups may be removed)
        attrs.setdefault("__slots__", ())
        attrs["__slots__"] += tuple(new_params)

        # create the Operation class
        cls = type.__new__(meta, clsname, bases, attrs)

        # collect params from subclasses
        # order defined by MRO, newly added params go last
        cls._param_descriptions = cls._param_descriptions.copy()
        for name in list(cls._param_descriptions):
            if name not in new_params and name in cls.__dict__:
                # if param was overriden by not-a-Param, not count it
                # even if it was included in a superclass
                # (a Param would not occur in cls.__dict__)
                del cls._param_descriptions[name]
        for name, param in new_params.items():
            cls._param_descriptions[name] = param

        # to allow both OperationClass._name
        # and OperationInstance._name
        cls._name = cls.__name__
        return cls

    def __call__(cls, *values, **kvalues):
        """Create an instance of :class:`.Operation`.

        Currently, only implements caching of :class:`Operation`s (if enabled),
        and passes all the parameters to the constructor of the :class:`Operation`.
        """
        if cls._circuit is None:
            raise TypeError(
                "Creating an operation that is not linked to a circuit."
                " Calling an operation from a circuit class?"
                " Or using a removed operation from a superclass?"
            )

        # create the Operation instance anyway
        # (not avoiding it to unify parsing of parameters)
        op_new = super().__call__(*values, **kvalues)
        if cls._circuit is not None and cls._circuit.CACHE_OPERATIONS:
            # if a similar operation is in cache,
            # return it instead (the new one will be deleted)
            cache = op_new._circuit._operations_cache
            key = op_new._cache_key
            op_old = cache.get(key, None)
            if op_old is not None:
                return op_old
            cache[key] = op_new
            return op_new
        else:
            return op_new


class Operation(metaclass=OperationMeta):
    """Describes a (parametrized) operation that can be used in a circuit.

    Parameters of an :class:`Operation` instance are accessible directly as
    attributes.

    All supporting attributes are either prefixed with "_" or are UPPERCASE
    to avoid collisions with possible parameter names. Exceptions:
    :attr:`n_inputs` and :attr:`n_outputs`.

    Attributes
    ----------
    Defining attributes (may/should be overwritten in subclasses):

    n_inputs: int
        Number of node inputs the operation requires.

    n_outputs: int = UNIT
        Number of node outputs the operation has (to be retrieved with the
        :class:`.Circuit.Operations.GET` operation).
        By default, is set to the special object :data:`UNIT`, which
        means that the output is non iterable. Note that this is different from
        ``n_outputs = 1``, where the actual output has to be retrieved e.g. as
        ``out = node[0]`` or `out, = node`.

    SYMMETRIC: bool
        Whether the order of the input nodes does not matter. Used e.g.
        for caching nodes (``b + a`` may return the cached node ``a + b``).

    PRECOMPUTABLE: bool
        Whether the operation is precomputable (given the inputs and the parameters).

    STR_LIMIT: int = 30
        Maximum length of the string describing parameters to keep (for
        :meth:`__str__`).

    Functional attributes (should not be overriden manually):

    _circuit: :class:`.Circuit`
        Circuit instance in which this :class:`Operation` class/instance
        is defined/subclassed.

    _circuit_class: :class:`.Circuit`
        Circuit class in which this :class:`Operation` class/instance
        is defined/subclassed.

    _param_descriptions : `dict`[str, :class:`.Param`]
        Mapping from parameter names to :class:`.Param` objects describing
        the parameters.

    """
    _circuit: "Circuit" = None
    _circuit_class: type = None
    _param_descriptions = {}

    SYMMETRIC = False
    PRECOMPUTABLE = True

    n_inputs = NotImplemented  # to be defined in a subclass
    n_outputs = UNIT  # by default, not GETtable

    __slots__ = "__weakref__",  # will be expanded by descendants

    STR_LIMIT = 30

    def __init__(self, *values, **kvalues):
        """Create an :class:`.Operation` *instance* by specifying parameters (if any).

        Note that it is not linked to any :class:`.Node` yet.
        """

        # check that __slots__ work well
        try:
            self.__dict__
        except AttributeError:
            pass
        else:
            warnings.warn(
                f"operation {self} has __dict__: __slots__ not working")

        # 1: accumulate kvalues to be complete
        # go through params in canonical order
        if len(values) + len(kvalues) > len(self._param_descriptions):
            raise TypeError(
                f"passed {len(values)}+{len(kvalues)} parameters, "
                f"required at most {len(self._param_descriptions)}")

        for i, (name, param) in enumerate(self._param_descriptions.items()):
            # set ones given not by name
            if i < len(values):
                assert name not in kvalues
                kvalues[name] = values[i]
            # for not given at all try default
            elif name not in kvalues:
                kvalues[name] = param.default  # or raise error
        assert len(kvalues) == len(self._param_descriptions)

        # 2: process through validators/converters
        for name, param in self._param_descriptions.items():
            # param can use previously set value, or not?
            # possible:
            # - param checks only single value, is independent
            # - to check groups, add methods to the op class
            setattr(self, name, param.create(self, value=kvalues[name]))

    def __call__(self, *incoming, **kwargs):
        """Create a new node using this operation."""
        assert not kwargs, "Incoming by name not implemented"

        # check n_inputs
        if self.n_inputs != VARIABLE and len(incoming) != self.n_inputs:
            raise TypeError(
                f"{self} requires exactly {self.n_inputs} inputs, "
                f"given {len(incoming)}")

        # check inputs are nodes
        incoming2 = []
        for value in incoming:
            if isinstance(value, self._circuit.Node):
                incoming2.append(value)
            elif isinstance(value, Node):
                raise TypeError(
                    f"incoming node {value} is not this circuit's node"
                )
            else:
                incoming2.append(self._circuit.add_const(value))
        incoming = incoming2
        del incoming2

        if self._circuit.PRECOMPUTE_CONSTANT_OPERATIONS:
            # check that incoming is non-empty to avoid INPUT and maybe
            # other special ops
            if self.PRECOMPUTABLE and incoming:
                if all(node.is_CONST() for node in incoming):
                    value = self.eval(
                        *[node.operation.value for node in incoming]
                    )
                    return self.circuit.add_const(value)

        if self._circuit.CACHE_NODES:
            node_cache_key = tuple(node.id for node in incoming)
            if self.SYMMETRIC:
                node_cache_key = tuple(sorted(node_cache_key))
            cache_key = node_cache_key, self._cache_key
            node_old = self._circuit._nodes_cache.get(cache_key, None)
            if node_old is not None:
                return node_old

        # custom checks
        self.before_create_node(*incoming)

        node = self._circuit.Node(operation=self, incoming=incoming)
        self._circuit.add_node(node)

        self.after_create_node(node)

        if self._circuit.CACHE_NODES:
            self._circuit._nodes_cache[cache_key] = node

        return node

    def reapply(self, circuit, name=None):
        """Create new operation instance with same parameters (by name),
        but in the other circuit. @name define name of the operation, by
        default it is the name of this operation.
        """
        if name is None:
            name = self._name
        new_opcls = getattr(circuit, self._name)
        return new_opcls(**self._parameters)

    @property
    def _parameters(self):
        # TBD: maybe values should be re-wrapped by the param object?
        return {name: getattr(self, name) for name in self._param_descriptions}

    @property
    def _cache_key(self):
        """Return cache key of this operation.

        Cache key identifies the operation in the operation cache (if enabled).

        It is also used to get operation's hash (for python's `set`, `dict`, etc.).
        """
        param_keys = frozenset(
            (name, descr.get_key(getattr(self, name)))
            for name, descr in self._param_descriptions.items()
        )
        return (self._name, param_keys)

    def __eq__(self, other: "Operation"):
        """Test equality of two operations.

        Two operations are equal if their names are equal and all parameters
        are equal.

        To check the class of the operation (e.g. INPUT, ADD, CONST, etc.)
        use:

        - ``isinstance(op, CircuitClass.ADD)`` : checks circuit class;
        - ``isinstance(op, CircuitInstance.ADD)`` : checks circuit instance too;
        - ``op.is_ADD()`` : ADD must be present in the circuit's class;
        - ``op._name == "ADD"`` : by name, does not check circuit class/instance.
        """
        # if isinstance(other, str):
        #     return self._name == other
        if isinstance(other, Operation):
            return (
                self._name == other._name
                and self._parameters == other._parameters
            )
        raise TypeError(
            f"Can'not compare operation of type {type(self)} to {other}"
        )

    def __hash__(self):
        key = self._cache_key
        try:
            return hash(key)
        except TypeError:
            raise UnhashableOperationError()

    def __str__(self):
        items = self._parameters.items()

        # JW: use ConstManger turn const `value` into integer representation?
        # AU: more generally, parameter may have an optional conversion method?
        info = " ".join(
            f"{key}={value}"
            for key, value in items if key[0] != "_"
        )

        # extended
        # if info:
        #     info = " " + info
        # return f"<{type(self).__name__}:{self.opname}{info}>"

        # short
        res = f"{self._name}"
        if info and len(info) < self.STR_LIMIT:
            res += f"[{info}]"
        elif info:
            res += f"[{info[:self.STR_LIMIT]}...]"
        return res

    def __repr__(self):
        return f"<{self._circuit.name}({type(self._circuit).__name__}):{self}>"

    # operation-specific methods, to be overriden

    def eval_with_node(self, node, *args):
        """This method should be overriden if the evaluation requires some
        information from the node. By default, it ignores the node and calls
        :meth:`eval`.
        """
        return self.eval(*args)

    def eval(self, *args):
        """Evaluate the operation on given inputs (typically values, not nodes)."""
        raise NotImplementedError(
            "default evaluation of %r is not defined" % self)

    def before_create_node(self, *args):
        """Validate node inputs before creating a new node with this operation."""
        pass

    def after_create_node(self, node):
        """Check new node after creation (node uses this operation)."""
        pass

    @classmethod
    def on_new_circuit(cls, circuit):
        """Callback on linking the operation class to a new circuit instance.

        E.g. can store common circuit-level data in the circuit instance.
        """
        pass

    def determine_n_outputs(self, node) -> int:
        """Determine number of outputs of a new node using this operation.

        By default, returns operation's :attr:`n_outputs`.
        However, this method must be overriden for multi-operations.
        For example, the number of outputs may be set equal to the number
        of inputs.
        """
        if self.n_outputs != VARIABLE:
            return self.n_outputs
        raise NotImplementedError(f"{self}.determine_n_outputs is missing")

    # methods for pickling

    def __reduce__(self):
        return (
            self._reconstruct_object,  # callable to create object
            (self._circuit, type(self).__name__),  # arguments
            self.__getstate__(),  # state to set
        )

    __getstate__ = get_state
    __setstate__ = set_state

    @staticmethod
    def _reconstruct_object(circuit, opname):
        op_class = getattr(circuit, opname)
        return op_class.__new__(op_class)


@AliasAttr(Operation)
class Nullary(Operation):
    """Operation with no inputs."""
    n_inputs = 0


@AliasAttr(Operation)
class Unary(Operation):
    """Operation with 1 inputs."""
    n_inputs = 1


@AliasAttr(Operation)
class Binary(Operation):
    """Operation with 2 inputs."""
    n_inputs = 2


@AliasAttr(Operation)
class Ternary(Operation):
    """Operation with 3 inputs."""
    n_inputs = 3


@AliasAttr(Operation)
class Variadic(Operation):
    """Operation with variable number of inputs."""
    n_inputs = VARIABLE


@AliasAttr(Operation)
class MultiNullary(Operation):
    """Operation with no inputs and (possibly) multiple number of outputs."""
    n_inputs = 0
    n_outputs = VARIABLE


@AliasAttr(Operation)
class MultiUnary(Operation):
    """Operation with 1 input and (possibly) multiple number of outputs."""
    n_inputs = 1
    n_outputs = VARIABLE


@AliasAttr(Operation)
class MultiBinary(Operation):
    """Operation with 2 inputs and (possibly) multiple number of outputs."""
    n_inputs = 2
    n_outputs = VARIABLE


@AliasAttr(Operation)
class MultiTernary(Operation):
    """Operation with 3 inputs and (possibly) multiple number of outputs."""
    n_inputs = 3
    n_outputs = VARIABLE


@AliasAttr(Operation)
class MultiVariadic(Operation):
    """Operation with variable number of inputs and (possibly) multiple number of outputs."""
    n_inputs = VARIABLE
    n_outputs = VARIABLE


class UnhashableOperationError(Exception):
    """Raised when an :class:`.Operation` is being hashed but hashing
    is not defined (e.g. some parameters are unhashable objects).
    """
    pass
