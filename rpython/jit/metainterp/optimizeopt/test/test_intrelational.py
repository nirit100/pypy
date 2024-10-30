import pytest
from rpython.jit.metainterp.optimizeopt.intrelational import IntOrderInfo
from rpython.jit.metainterp.optimizeopt.intutils import IntBound
from rpython.jit.metainterp.optimize import InvalidLoop
from rpython.jit.metainterp.optimizeopt.test.test_intbound import knownbits_and_bound_with_contained_number, ints

from rpython.rlib.rarithmetic import r_uint, intmask

from hypothesis import given, strategies, example, seed, assume

def build_order_info_and_contained_number(t):
    b, n = t
    return IntOrderInfo(b), n

order_info_and_contained_number = strategies.builds(
    build_order_info_and_contained_number,
    knownbits_and_bound_with_contained_number
)

def build_order_info_and_contained_number2(t1, t2, are_related):
    i1, n1 = t1
    i2, n2 = t2
    if n1 != n2 and are_related:
        if n1 < n2:
            i1.make_lt(i2)
        else:
            assert n2 < n1
            i2.make_lt(i1)
    return ((i1, n1), (i2, n2))

order_info_and_contained_number2 = strategies.builds(
    build_order_info_and_contained_number2,
    order_info_and_contained_number,
    order_info_and_contained_number,
    strategies.booleans()
)

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

def test_abstract_add_const():
    a = IntOrderInfo()
    b = a.abstract_add_const(1)
    assert not a.known_lt(b) # could have overflowed

    a = IntOrderInfo(IntBound(0, 10))
    b = a.abstract_add_const(1)
    assert a.known_lt(b) # no overflow


@given(order_info_and_contained_number, ints)
def test_add_const_random(t1, n2):
    b1, n1 = t1
    b3 = b1.abstract_add_const(n2)
    # the result bound works for unsigned addition, regardless of overflow
    values = {b1: n1, b3: intmask(r_uint(n1) + r_uint(n2))}
    assert b3.contains(values)

def test_abstract_add():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = a.abstract_add(b)
    # nothing is known about how a, b, c relate to each other (add could overflow)
    assert not a.known_lt(c)
    assert not c.known_lt(a)
    assert not b.known_lt(c)
    assert not c.known_lt(b)

    a = IntOrderInfo(IntBound(-10, 10))
    b = IntOrderInfo(IntBound(1, 10))
    c = a.abstract_add(b)
    assert a.known_lt(c) # no overflow

    a = IntOrderInfo(IntBound(1, 10))
    b = IntOrderInfo(IntBound(1, 10))
    c = a.abstract_add(b)
    assert a.known_lt(c) # no overflow
    assert b.known_lt(c) # no overflow

@given(order_info_and_contained_number2)
def test_abstract_add_random(args):
    ((b1, n1), (b2, n2)) = args
    b3 = b1.abstract_add(b2)
    # the result bound works for unsigned addition, regardless of overflow
    values = {b1: n1, b2: n2, b3: intmask(r_uint(n1) + r_uint(n2))}
    assert b3.contains(values)
