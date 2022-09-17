from circkit.utils import AliasAttr, NamedObject


UNSET = NamedObject("UNSET")


class Param:
    """
    Describes a type of a parameter of an operation,
        mainly its validation/conversion.

    JW: how about rename this as `ParameterConstraint`

    Default (this type): no validation/conversion
    """

    class InvalidConstraint(Exception):
        pass

    class InvalidValue(Exception):
        pass

    _default = UNSET

    def create(self, operation, value):
        return value

    @property
    def default(self, operation=UNSET):
        if self._default is UNSET:
            raise KeyError(f"default value for {self} is not set")
        return self._default

    def set_default(self, value):
        self._default = value

    def get_key(self, value):
        return value


@AliasAttr(Param, "Const")
class ConstParam(Param):
    def create(self, operation, value):
        return operation._circuit.const_manager.create(value)


@AliasAttr(Param, "Int")
class IntParam(Param):
    def __init__(self, *, min_value: int = None, max_value: int = None):
        self.min_value = int(min_value) if min_value is not None else None
        self.max_value = int(max_value) if max_value is not None else None
        if min_value is not None and \
           max_value is not None and \
           not (min_value <= max_value):

            raise Param.InvalidConstraint(
                f"Bad constraint: min_value={min_value}, max_value={max_value}")

    def create(self, operation, value: int):
        value = int(value)
        if self.min_value is not None and self.min_value > value:
            raise Param.InvalidValue(
                f"Integer value should not be smaller than {self.min_value}")
        if self.max_value is not None and value > self.max_value:
            raise Param.InvalidValue(
                f"Integer value should not be greater than {self.max_value}")
        return value


@AliasAttr(Param, "Bool")
class BoolParam(Param):
    def create(self, operation, value):
        if value not in (True, False, 1, 0):
            raise Param.InvalidValue(
                "Boolean value can only be True or False.")
        return bool(value)


@AliasAttr(Param, "Str")
class StrParam(Param):
    def create(self, operation, value):
        assert isinstance(value, str)
        return value


@AliasAttr(Param, "Tuple")
class TupleParam(Param):
    def create(self, operation, value):
        return tuple(value)


@AliasAttr(Param, "InputName")
class InputNameParam(Param):
    """
    Accepts any subclass of str,int or arbitrarily nested tuple of those
    """
    @staticmethod
    def is_valid(value):
        if isinstance(value, (str, int)):
            return True
        if isinstance(value, tuple):
            return all(InputNameParam.is_valid(sub for sub in value))
        return False

    def create(self, operation, value):
        if not self.is_valid(value):
            raise TypeError(f"{value} is not valid name for VAR")
        return value
