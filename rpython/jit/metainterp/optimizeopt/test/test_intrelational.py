import pytest
from rpython.jit.metainterp.optimizeopt.intrelational import IntOrderInfo
from rpython.jit.metainterp.optimizeopt.intutils import IntBound
from rpython.jit.metainterp.optimize import InvalidLoop


def test_very_basic():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_lt(b)
    assert a.known_lt(b)
    a.make_lt(b)
    assert len(a.relations) == 1

def test_lt_transitivity():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = IntOrderInfo()
    a.make_lt(b)
    b.make_lt(c)
    assert a.known_lt(c)


def test_contains_simple():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_lt(b)
    assert a.contains({a: 1, b: 2})
    assert not a.contains({a: 2, b: 1})

def test_contains():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = IntOrderInfo()
    a.make_lt(b)
    b.make_lt(c)
    assert a.contains({a: 1, b: 2, c: 3})
    assert not a.contains({a: 1, b: 3, c: 2})

def test_contains_transitive():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = IntOrderInfo()
    a.make_lt(b)
    b.make_lt(c)
    assert a.contains({a: 1, b: 2, c: 3})
    assert not a.contains({a: 1, b: 3, c: 2})

def test_lt_raises_invalidloop():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_lt(b)
    with pytest.raises(InvalidLoop):
        b.make_lt(a)

def test_abstract_add():
    a = IntOrderInfo()
    b = a.abstract_add_const(1)
    assert not a.known_lt(b) # could have overflowed

    a = IntOrderInfo(IntBound(0, 10))
    b = a.abstract_add_const(1)
    assert a.known_lt(b) # no overflow
