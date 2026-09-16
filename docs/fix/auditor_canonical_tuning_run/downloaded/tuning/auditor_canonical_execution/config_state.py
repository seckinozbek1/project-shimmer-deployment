"""Identity-preserving snapshots of explicit Python configuration value forms.

No serialization, arbitrary deepcopy hooks, model loaders or tensor operations.
Unsupported hidden/opaque mutable state fails before the evaluation transition.
"""
from collections import OrderedDict
from collections.abc import Mapping, Sequence, Set
from dataclasses import fields, is_dataclass
from enum import Enum
from types import FunctionType, MethodType


class UnsupportedConfig(TypeError):
    pass


def atomic(value):
    if value is None or type(value) in (bool, int, float, complex, str, bytes, type):
        return True
    if isinstance(value, Enum):
        return True
    # Pinned real config may contain torch.dtype. Do not import Torch locally.
    cls = type(value)
    return cls.__module__ == 'torch' and cls.__name__ == 'dtype'


def owned_dict(value):
    """Only real owned state; avoid delegated PEFT attributes/properties."""
    try:
        state = object.__getattribute__(value, '__dict__')
    except AttributeError:
        raise UnsupportedConfig('Object has no owned attribute dictionary') from None
    if type(state) is not dict:
        raise UnsupportedConfig('Unsupported owned attribute storage')
    return state


class ConfigSnapshot:
    """Capture one shared object graph and restore it without replacing objects.

    Dict/OrderedDict, lists and tuples retain identity, aliases and cycles.
    Dataclasses (including slots/frozen) and plain __dict__ config objects keep
    their field objects. Arbitrary mappings, sets, arrays, callables and opaque
    extension objects are rejected, not converted or silently copied.
    """
    def __init__(self, roots):
        self.roots = tuple(roots)
        self.nodes = {}
        for index, value in enumerate(self.roots):
            self._capture(value, 'root[' + str(index) + ']')

    def _capture(self, value, path):
        if atomic(value) or id(value) in self.nodes:
            return
        cls = type(value)
        if cls in (dict, OrderedDict):
            kind, state = 'mapping', tuple(value.items())
            children = []
            for key, child in state:
                if not self._immutable_key(key):
                    raise UnsupportedConfig(path + ': mutable/unsupported mapping key')
                children.append(child)
        elif cls is list or cls is tuple:
            kind, state = 'list' if cls is list else 'tuple', tuple(value)
            children = state
        elif isinstance(value, (Mapping, Sequence, Set, bytearray)):
            raise UnsupportedConfig(path + ': unsupported container implementation ' + cls.__name__)
        elif is_dataclass(value) and not isinstance(value, type):
            names = tuple(f.name for f in fields(value))
            slot_names = self._slots(cls)
            if set(slot_names) - set(names):
                raise UnsupportedConfig(path + ': hidden dataclass slots')
            dictionary = getattr(value, '__dict__', None)
            if dictionary is not None and type(dictionary) is not dict:
                raise UnsupportedConfig(path + ': unsupported dataclass dictionary')
            state = (tuple((name, getattr(value, name)) for name in names),
                     tuple(dictionary.items()) if dictionary is not None else None)
            kind = 'dataclass'
            children = [x for _, x in state[0]] + ([] if state[1] is None else [x for _, x in state[1]])
        else:
            if isinstance(value, (FunctionType, MethodType)) or callable(value) or self._slots(cls):
                raise UnsupportedConfig(path + ': unsupported mutable/opaque type ' + cls.__name__)
            try:
                dictionary = owned_dict(value)
            except UnsupportedConfig:
                raise UnsupportedConfig(path + ': unsupported mutable/opaque type ' + cls.__name__) from None
            kind, state = 'object', tuple(dictionary.items())
            children = [x for _, x in state]
        self.nodes[id(value)] = (value, kind, state)
        for index, child in enumerate(children):
            self._capture(child, path + '.' + str(index))

    @staticmethod
    def _slots(cls):
        result = []
        for base in cls.__mro__:
            slots = base.__dict__.get('__slots__', ())
            result.extend((slots,) if isinstance(slots, str) else slots)
        return tuple(x for x in result if x not in ('__dict__', '__weakref__'))

    @classmethod
    def _immutable_key(cls, value):
        return atomic(value) or (type(value) is tuple and all(cls._immutable_key(x) for x in value))

    def restore(self):
        for value, kind, state in self.nodes.values():
            if kind == 'mapping':
                value.clear(); value.update(state)
            elif kind == 'list':
                value[:] = state
            elif kind == 'object':
                dictionary = owned_dict(value)
                dictionary.clear(); dictionary.update(state)
            elif kind == 'dataclass':
                attributes, dictionary = state
                if dictionary is not None:
                    current = owned_dict(value)
                    current.clear(); current.update(dictionary)
                for name, prior in attributes:
                    object.__setattr__(value, name, prior)
            # Tuples/atomic values cannot be mutated; their mutable descendants
            # are independently restored through the same graph.
        self.verify()

    @staticmethod
    def _same_items(current, saved):
        return len(current) == len(saved) and all(a is b for a, b in zip(current, saved))

    def verify(self):
        for value, kind, state in self.nodes.values():
            if kind == 'mapping':
                now = tuple(value.items())
                valid = len(now) == len(state) and all(k is sk and v is sv for (k,v),(sk,sv) in zip(now,state))
            elif kind in ('list','tuple'):
                valid = self._same_items(tuple(value), state)
            elif kind == 'object':
                now = owned_dict(value)
                valid = list(now) == [k for k,_ in state] and all(now[k] is v for k,v in state)
            else:
                attributes, dictionary = state
                valid = all(getattr(value,name) is prior for name,prior in attributes)
                if dictionary is not None:
                    now = owned_dict(value)
                    valid = valid and list(now) == [k for k,_ in dictionary] and all(now[k] is v for k,v in dictionary)
            if not valid:
                raise ValueError('Configuration state/identity restoration failed: ' + kind)
        return True

    def enable_cache(self):
        # Only owned top-level config values: nested optional configs are state,
        # not independent generation cache policy. No new attribute is invented.
        visited = set()
        for value in self.roots:
            if id(value) in visited: continue
            visited.add(id(value))
            if type(value) in (dict, OrderedDict):
                if 'use_cache' in value: value['use_cache'] = True
            elif is_dataclass(value) and not isinstance(value, type):
                if any(f.name == 'use_cache' for f in fields(value)):
                    # Frozen dataclasses are valid snapshots, but cannot be
                    # rewritten. Explicit use_cache=True kwargs remain binding.
                    if not type(value).__dataclass_params__.frozen: value.use_cache = True
            elif not atomic(value) and type(value) not in (list,tuple):
                state = owned_dict(value)
                if 'use_cache' in state: state['use_cache'] = True

    def inventory(self):
        return [dict(index=i, type=type(value).__module__+'.'+type(value).__qualname__,
                     is_none=value is None, identity_group=next(j for j,x in enumerate(self.roots) if x is value))
                for i,value in enumerate(self.roots)]
