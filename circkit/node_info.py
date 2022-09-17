from collections.abc import MutableMapping

from circkit.utils import PicklableWeakKeyDictionary


class InheritanceInfo:
    def __init__(self, only_output=False, merge_flatten=True, merge_unique=True):
        self.only_output = only_output
        self.merge_unique = merge_unique
        self.merge_flatten = merge_flatten

    def __repr__(self):
        return (
            "<InheritanceInfo"
            + f" only_output={self.only_output}"
            + f" merge_unique={self.merge_unique}"
            + f" merge_flatten={self.merge_flatten}"
            + ">"
        )


Nothing = object()
RaiseException = object()


class MergeTuple(tuple):
    def __repr__(self):
        return "Merged" + super().__repr__()


class NodeInfoMapper(MutableMapping):
    def __init__(self, node):
        self.node = node
        self.circuit = node.circuit

    @property
    def storage(self):
        return self.circuit._node_info_storage

    def __getitem__(self, key, default=None):
        return self.storage.get(node=self.node, key=key)

    def __setitem__(self, key, value):
        return self.storage.set(node=self.node, key=key, value=value)

    def __delitem__(self, key):
        return self.storage.delete(node=self.node, key=key)

    def __iter__(self):
        return self.storage.iter(node=self.node)

    def __len__(self):
        return self.storage.len(node=self.node)

    def get_inheritance(self, key):
        return self.storage.inheritance.get(key, None)

    def set_inheritance(self, key, inheritance_info=None, **options):
        if inheritance_info is None:
            if not options:
                if key in self.storage.inheritance:
                    del self.storage.inheritance[key]
                return
            inheritance_info = InheritanceInfo(**options)
        self.storage.inheritance[key] = inheritance_info

    def inherit_to_node(self, new_node, is_output):
        new_info = new_node.info
        for key in self:
            inh_info = self.get_inheritance(key)
            if not inh_info:
                continue
            value = self.storage.get(node=self.node, key=key)
            # if key == "_obfuscator_index":
            #     # print(self, new_node, self, new_info)
            #     raise

            new_info.set_inheritance(key, inh_info)
            if (not inh_info.only_output) or is_output:
                new_info[key] = value

    @classmethod
    def inherit_to_node_from_many(cls, old_nodes, new_node, is_output):
        keys = set()
        for old in old_nodes:
            keys |= set(old.info.keys())

        new_info = new_node.info
        for key in keys:
            # inh. info is the same through circuit
            inh_info = old_nodes[0].info.get_inheritance(key)
            if not inh_info:
                continue

            values = []
            for old in old_nodes:
                value = old.info.storage.get(old, key, Nothing)
                if value is Nothing:
                    continue
                if not inh_info.merge_flatten:
                    values.append(value)
                else:
                    if isinstance(value, MergeTuple):
                        for sub in value:
                            values.append(sub)
                    else:
                        values.append(value)

            if inh_info.merge_unique:
                values = tuple(set(values))

            # optimize to keep the same Merge object if nothing is merged
            if len(values) == 1 and isinstance(values[0], MergeTuple):
                values = values[0]
            else:
                values = MergeTuple(values)

            new_info.set_inheritance(key, inh_info)
            if (not inh_info.only_output) or is_output:
                new_info[key] = values

    def __str__(self):
        return str(dict(self.items()))


class NodeInfoDescriptor:
    def __get__(self, node, nodecls=None):
        return NodeInfoMapper(node)


class NodeInfoStorage:
    PER_KEY_DICT_CLASS = PicklableWeakKeyDictionary

    def __init__(self):
        self.data = {}
        self.inheritance = {}

    def clear(self):
        self.data.clear()
        self.inheritance.clear()

    def iter(self, node):
        for key in self.data:
            if node in self.data[key]:
                yield key

    def len(self, node):
        return len(list(self.iter(node)))

    def has(self, node, key):
        if key not in self.data:
            return False
        if node not in self.data[key]:
            return False
        return True

    def get(self, node, key, default=RaiseException):
        if key not in self.data:
            if default is RaiseException:
                raise KeyError(f"unknown key {key}")
            return default
        data = self.data[key]
        if node not in data:
            if default is RaiseException:
                raise KeyError(f"node {node} does not have {key}")
            return default
        return data[node]

    def set(self, node, key, value):
        if key not in self.data:
            self.data[key] = self.PER_KEY_DICT_CLASS()
        self.data[key][node] = value

    def delete(self, node, key):
        if key in self.data:
            del self.data[key][node]
            if not self.data[key]:
                del self.data[key]

    def _finish_pickle(self):
        for key, mapp in self.data.items():
            mapp._finish_pickle()
