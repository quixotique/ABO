# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

r"""Robust enumeration type.

A new enumeration class is created using the enum() factory, which takes
a list of the names of its elements:

    >>> E = enum('a', 'b', 'c')
    >>> e = E.a
    >>> e
    enum('a', 'b', 'c').a

Enumerations can be subclassed:

    >>> class X(enum('a', 'b', 'c')):
    ...  pass
    >>> e = X.a
    >>> e
    X.a

All enumeration classes are subclasses of enum:

    >>> issubclass(E, enum)
    True
    >>> issubclass(X, enum)
    True

The enum() class factory produces the same class given the same names:

    >>> issubclass(X, enum('a', 'b', 'c'))
    True
    >>> issubclass(X, enum('a', 'b', 'c', 'd'))
    False

The order of the names is significant -- a different order produces a different
class:

    >>> class Y(enum('c', 'b', 'a')):
    ...  pass
    >>> issubclass(X, Y)
    False
    >>> issubclass(Y, X)
    False

Duplicate element names are not allowed in a single enumeration class:

    >>> enum('a', 'a')
    Traceback (most recent call last):
    TypeError: duplicate enum element 'a'

Enumeration values look like class attributes, whose repr() strings are their
names (not qualified with the module name):

    >>> x = X.a
    >>> x
    X.a
    >>> x = X.b
    >>> x
    X.b

Enumeration values are instances of the enumeration class, and also members of
it:

    >>> isinstance(X.a, X)
    True
    >>> isinstance(X.a, enum('a', 'b', 'c'))
    True
    >>> isinstance(X.a, enum)
    True

    >>> X.a in X
    True
    >>> X.a in E
    False

Each enumeration class is its own namespace.  The elements of an enumeration
class are different from the elements of its subclass:

    >>> issubclass(X, enum('a', 'b', 'c'))
    True
    >>> X.a in enum('a', 'b', 'c')
    False
    >>> enum('a', 'b', 'c').a in X
    False
    >>> enum('a', 'b', 'c').a is X.a
    False
    >>> enum('a', 'b', 'c').a == X.a
    False

The class acts as an element factory:

    >>> X(X.a)
    X.a
    >>> X(X.b)
    X.b
    >>> X(X.c) is X.c
    True
    >>> X(1)
    Traceback (most recent call last):
    ValueError: not an element of enumeration 'X'

The default value is the first one:

    >>> X()
    X.a

When the class is iterated, it yields all its elements, in the order declared:

    >>> len(X)
    3
    >>> list(X)
    [X.a, X.b, X.c]

Equality and inequality operations between elements work as expected:

    >>> X.a == X.b
    False
    >>> X.a != X.b
    True
    >>> X() == X()
    True
    >>> X() == X.a
    True
    >>> X() == X.b
    False
    >>> X.a == None
    False
    >>> X.a == 0
    False
    >>> X.a == 1
    False
    >>> X.a == 'a'
    False

All enumerations evaluate as True, to contrast with None:

    >>> bool(X.a)
    True
    >>> bool(X.b)
    True
    >>> bool(X.c)
    True

enum types are immutable, and so are the elements:

    >>> X.b = 3
    Traceback (most recent call last):
    TypeError: can't set attributes of enumeration type 'X'
    >>> X.a.blah = 1
    Traceback (most recent call last):
    TypeError: can't set attributes of enumeration 'X.a'

Since Enums are immutable, copying always produces the same objects:

    >>> y = copy.copy(x)
    >>> y is x
    True
    >>> y == x
    True

    >>> y = copy.deepcopy(x)
    >>> y is x
    True
    >>> y == x
    True

The repr() form of an enumeration type can be used to reconstruct the same
type, provided that the enumeration class name is in scope:

    >>> eval(repr(enum('one', 'two', 'three')))
    enum('one', 'two', 'three')
    >>> eval(repr(enum('one', 'two', 'three'))) is enum('one', 'two', 'three')
    True

    >>> eval(repr(X))
    X
    >>> eval(repr(X)) is X
    True

The repr() form of an enumeration element can be used to reconstruct the same
element:

    >>> eval(repr(X()))
    X.a
    >>> eval(repr(X())) == X.a
    True
    >>> eval(repr(X())) is X.a
    True

enum elements can be pickled and unpickled using protocol 2:

    >>> import abo.enum
    >>> abo.enum.X = X

    >>> pickle.loads(pickle.dumps(X.b, 2))
    X.b
    >>> pickle.loads(pickle.dumps(X.b, 2)) is X.b
    True

    >>> pickle.loads(pickle.dumps(X.b, 0)) is X.b
    Traceback (most recent call last):
    _pickle.UnpicklingError: abo.enum.enum does not support this protocol

Every element has an immutable 'e_name' attribute that is its bare name:

    >>> X.a.e_name
    'a'
    >>> enum('wah').wah.e_name
    'wah'

    >>> X.a.e_name = 'A'
    Traceback (most recent call last):
    TypeError: can't set attributes of enumeration 'X.a'

The type() of an element is its enumeration class:

    >>> type(X.a) is X
    True

"""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.enum
    doctest.testmod(abo.enum)

import copy
import pickle

class _enum_meta(type):

    r'''Enumeration metaclass.  Initialises attributes and enforces class
    immutability.
    '''

    def __init__(cls, name, bases, dct):
        for name in cls._names:
            if name in cls.__dict__:
                raise TypeError('duplicate enum element %r' % name)
            cls(name)
        cls._immutable_class = True

    def __setattr__(cls, name, value):
        if cls.__dict__.get('_immutable_class', False):
            raise TypeError("can't set attributes of enumeration type %r" % (
                                 cls.__name__))
        return type.__setattr__(cls, name, value)

    def __repr__(cls):
        return cls.__name__

    def __contains__(cls, elt):
        return type(elt) is cls and getattr(cls, elt.e_name, None) is elt

    def __len__(cls):
        return len(cls._names)

    def __iter__(cls):
        for name in cls._names:
            yield getattr(cls, name)

class enum(object, metaclass=_enum_meta):

    r'''Superclass of all enumeration types.
    '''
    _names = ()

    def __new__(cls, *args):
        r'''The enum constructor is used for three purposes.  When invoked
        directly as enum(), it creates a new enumeration type:

            >>> _E = enum('one', 'two', 'three')
            >>> class E(_E):
            ...     pass
            >>> issubclass(E, enum)
            True
            >>> issubclass(E, _E)
            True

        When invoked via a sub-class with zero or one arguments, it acts as the
        constructor for that class:

            >>> _E()
            enum('one', 'two', 'three').one
            >>> E()
            E.one
            >>> E(E.three)
            E.three

        The single argument can be a string with the bare name of the element.
        This is used for creating the original elements when a class is
        created, and also for unpickling:

            >>> E('three')
            E.three

        '''
        if cls is not enum:
            if not args:
                return getattr(cls, cls._names[0])
            assert len(args) == 1
            if isinstance(args[0], str):
                obj = cls.__dict__.get(args[0])
                if obj is None:
                    obj = object.__new__(cls)
                    obj.e_name = args[0]
                    obj._immutable = True
                    setattr(cls, args[0], obj)
            else:
                obj = args[0]
            if obj not in cls:
                raise ValueError('not an element of enumeration %r' %
                                 cls.__name__)
            return obj
        names = tuple(args)
        assert len(names) > 0
        for name in names:
            assert type(name) is str, '%r is not a str' % name
        if names in globals():
            return globals()[names]
        name = '%s(%s)' % (cls.__name__, ', '.join(map(repr, names)))
        cls = type(cls)(name, (enum,), {'_names': names})
        globals()[names] = cls
        return cls

    def __setattr__(self, name, value):
        if getattr(self, '_immutable', False):
            raise TypeError("can't set attributes of enumeration %r" % (
                                 repr(self)))
        return object.__setattr__(self, name, value)

    def __repr__(self):
        return '%s.%s' % (type(self).__name__, self.e_name)

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __getnewargs__(self):
        r'''Pickle protocol 2 support.  Return a tuple of args that will be
        passed to __new__() when unpickled.
        '''
        return self.e_name,

    def __setstate__(self, state):
        r'''Here is where we catch an unpickling by a protocol that does not
        support __getnewargs__()/__new__().  If it does, then __new__() has
        already been called, so we check that it has produced the correct
        result.
        '''
        try:
            assert self.e_name == state['e_name']
        except (AttributeError, AssertionError):
            raise pickle.UnpicklingError(
                    '%s.enum does not support this protocol' % enum.__module__)
        assert self is type(self).__dict__.get(self.e_name)
