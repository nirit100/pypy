import pytest
from rpython.jit.metainterp.optimizeopt.intrelational import IntOrderInfo
from rpython.jit.metainterp.optimizeopt.intutils import IntBound, MININT, MAXINT
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

def build_order_info_and_contained_number2(t1, t2, relation_kind):
    i1, n1 = t1
    i2, n2 = t2
    if relation_kind == "lt":
        if n1 < n2:
            i1.make_lt(i2)
        elif n2 < n1:
            i2.make_lt(i1)
        # ignore case '=='
    elif relation_kind.startswith("le"):
        if n1 < n2 or (n1 == n2 and relation_kind == 'le'):
            i1.make_le(i2)
        else:
            # also includes "le_reverse"
            assert n2 <= n1
            i2.make_le(i1)
    return ((i1, n1), (i2, n2))

order_info_and_contained_number2 = strategies.builds(
    build_order_info_and_contained_number2,
    order_info_and_contained_number,
    order_info_and_contained_number,
    strategies.sampled_from(["none", "lt", "le", "le_reverse"])
)

def test_lt_very_basic():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_lt(b)
    assert a._known_lt(b)
    a.make_lt(b)
    assert len(a.relations) == 1

def test_lt_transitivity():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = IntOrderInfo()
    a.make_lt(b)
    b.make_lt(c)
    assert a._known_lt(c)

def test_make_le_already_implied_by_bounds():
    a = IntOrderInfo(IntBound(-20, -10))
    b = IntOrderInfo(IntBound(0, 10))
    a._make_le = None # test that the bounds fast path works
    a.make_le(b)
    assert a.known_le(b)

def test_known_le_self():
    a = IntOrderInfo()
    assert a.known_le(a)
    a.make_le(a)

def test_le_very_basic():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_le(b)
    assert a._known_le(b)
    a.make_le(b)
    assert len(a.relations) == 1

def test_le_transitivity():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = IntOrderInfo()
    a.make_le(b)
    b.make_le(c)
    assert a._known_le(c)

def test_lt_le_transitivity():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = IntOrderInfo()
    a.make_lt(b)
    b.make_le(c)
    assert a._known_lt(c)

def test_lt_le_different():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_le(b)
    assert not a._known_lt(b)
    assert a._known_le(b)

    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_lt(b)
    assert a._known_lt(b)
    assert a._known_le(b)

def test_le_cycle():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_le(b)
    b.make_le(a)
    assert a.known_le(b)
    assert b.known_le(a)
    assert not a.known_lt(b)

def test_str_cycle():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_le(b)
    b.make_le(a)
    assert str(a) == '''\
i0 = IntOrderInfo(IntBound.unbounded()  {
    <= i1 = IntOrderInfo(IntBound.unbounded()  {
        <= i0
       })
})'''


def test_make_lt_then_make_le():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_lt(b)
    a.make_le(b)
    assert a.known_le(b)
    assert a.known_lt(b)
    assert len(a.relations) == 1

def test_make_le_then_make_lt():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_le(b)
    a.make_lt(b)
    assert a.known_le(b)
    assert a.known_lt(b)
    assert len(a.relations) == 1

def test_known_lt_takes_all_paths_into_account():
    import itertools
    for indexes in itertools.permutations([(0, 1, 'le'), (1, 2, 'le'), (0, 2, 'lt')], 3):
        a = IntOrderInfo()
        b = IntOrderInfo()
        c = IntOrderInfo()
        l = [a, b, c]
        for i1, i2, kind in indexes:
            if kind == 'le':
                l[i1].make_le(l[i2])
            else:
                l[i1].make_lt(l[i2])
        assert a.known_le(b)
        assert b.known_le(c)
        assert a.known_lt(c)

def test_known_lt_takes_all_paths_into_account_diamond():
    import itertools
    #      a0
    # <= /   \ <
    #   b1    c2
    # <= \   / <=
    #      d3
    for indexes in itertools.permutations([(0, 1, 'le'), (0, 2, 'lt'), (1, 3, 'le'), (2, 3, 'le')], 4):
        a = IntOrderInfo()
        b = IntOrderInfo()
        c = IntOrderInfo()
        d = IntOrderInfo()
        l = [a, b, c, d]
        for i1, i2, kind in indexes:
            if kind == 'le':
                l[i1].make_le(l[i2])
            else:
                l[i1].make_lt(l[i2])

        assert a.known_lt(d)

def test_known_lt_bug():
    r1 = IntOrderInfo(IntBound(MININT, -1))
    r2 = IntOrderInfo(IntBound(MININT, -1))
    r1.make_le(r2)
    r3 = IntOrderInfo(IntBound(MININT + 1, MAXINT))
    r1.make_lt(r3)
    assert not r1._known_lt(r2)

@given(order_info_and_contained_number2)
def test_known_any_random(args):
    ((r1, n1), (r2, n2)) = args
    if r1._known_le(r2):
        assert n1 <= n2
    elif r2._known_le(r1):
        assert n2 <= n1
    if r1._known_lt(r2):
        assert n1 < n2
    elif r2._known_lt(r1):
        assert n2 < n1

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

def test_lt_raises_invalidloop_1():
    a = IntOrderInfo()
    with pytest.raises(InvalidLoop):
        a.make_lt(a)

def test_lt_raises_invalidloop_2():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_lt(b)
    with pytest.raises(InvalidLoop):
        b.make_lt(a)

def test_abstract_add_const():
    a = IntOrderInfo()
    b = a.abstract_add_const(1)
    assert not a._known_lt(b) # could have overflowed

    a = IntOrderInfo(IntBound(0, 10))
    b = a.abstract_add_const(1)
    assert a._known_lt(b) # no overflow

@given(order_info_and_contained_number, ints)
def test_add_const_random(t1, n2):
    r1, n1 = t1
    r3 = r1.abstract_add_const(n2)
    # the result bound works for unsigned addition, regardless of overflow
    values = {r1: n1, r3: intmask(r_uint(n1) + r_uint(n2))}
    assert r3.contains(values)

def test_abstract_add():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = a.abstract_add(b)
    # nothing is known about how a, b, c relate to each other (add could overflow)
    assert not a._known_lt(c)
    assert not c._known_lt(a)
    assert not b._known_lt(c)
    assert not c._known_lt(b)

    a = IntOrderInfo(IntBound(-10, 10))
    b = IntOrderInfo(IntBound(-10, 10))
    c = a.abstract_add(b)
    assert not a._known_lt(c) # inconclusive
    assert not b._known_lt(c)

    a = IntOrderInfo(IntBound(-10, 10))
    b = IntOrderInfo(IntBound(1, 10))
    c = a.abstract_add(b)
    assert a._known_lt(c) # no overflow

    a = IntOrderInfo(IntBound(1, 10))
    b = IntOrderInfo(IntBound(1, 10))
    c = a.abstract_add(b)
    assert a._known_lt(c) # no overflow
    assert b._known_lt(c) # no overflow

def test_abstract_add_sameop():
    a = IntOrderInfo()
    b = a
    c = a.abstract_add(b)
    # nothing is known about how a, b, c relate to each other (add could overflow)
    assert not a._known_lt(c)
    assert not c._known_lt(a)
    assert not b._known_lt(c)
    assert not c._known_lt(b)

    a = IntOrderInfo(IntBound(-10, 10))
    b = a
    c = a.abstract_add(b)
    assert not a._known_lt(c) # inconclusive

    a = IntOrderInfo(IntBound(1, 10))
    b = a
    c = a.abstract_add(b)
    assert a._known_lt(c) # no overflow

    a = IntOrderInfo(IntBound(-10, -1))
    b = a
    c = a.abstract_add(b)
    assert c._known_lt(a) # no overflow

@given(order_info_and_contained_number2)
def test_abstract_add_random(args):
    ((r1, n1), (r2, n2)) = args
    r3 = r1.abstract_add(r2)
    # the result bound works for unsigned addition, regardless of overflow
    values = {r1: n1, r2: n2, r3: intmask(r_uint(n1) + r_uint(n2))}
    assert r3.contains(values)

def test_known_ne():
    a = IntOrderInfo()
    b = IntOrderInfo()
    a.make_lt(b)
    assert a.known_ne(b)
    assert b.known_ne(a)

@given(order_info_and_contained_number2)
def test_known_ne_random(args):
    ((r1, n1), (r2, n2)) = args
    if r1.known_ne(r2):
        assert n1 != n2

def test_abstract_sub():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = a.abstract_sub(b)
    # nothing is known about how a, b, c relate to each other (sub could overflow)
    assert not a.known_lt(c)
    assert not c.known_lt(a)
    assert not b.known_lt(c)
    assert not c.known_lt(b)

    a = IntOrderInfo(IntBound(-10, 10))
    b = IntOrderInfo(IntBound(-10, 10))
    c = a.abstract_sub(b)
    assert not a.known_lt(c)
    assert not b.known_lt(c)

    a = IntOrderInfo(IntBound(-100, 100))
    b = IntOrderInfo(IntBound(-100, 100))
    a.make_lt(b)
    c = b.abstract_sub(a)
    assert c.bounds.known_gt_const(0)

    a = IntOrderInfo(IntBound(-100, 100))
    b = IntOrderInfo(IntBound(-100, 100))
    b.make_lt(a)
    c = b.abstract_sub(a)
    assert c.bounds.known_lt_const(0)

    a = IntOrderInfo(IntBound(-100, 100))
    b = IntOrderInfo(IntBound(1, 100))
    c = a.abstract_sub(b)
    assert c.known_lt(a)

def test_abstract_sub_other_test():
    a = IntOrderInfo()
    b = a
    c = a.abstract_sub(b)
    # nothing is known about how a, b, c relate to each other (add could overflow)
    assert not a._known_lt(c)
    assert not c._known_lt(a)
    assert not b._known_lt(c)
    assert not c._known_lt(b)

    # Since subtracting any value from itself results just in 0 anyways, there
    #   is no need to really do much about the relations.
    # So we just make test that it doesn't throw.

    a = IntOrderInfo(IntBound(-10, 10))
    b = a
    c = a.abstract_sub(b)

    a = IntOrderInfo(IntBound(1, 10))
    b = a
    c = a.abstract_sub(b)

    a = IntOrderInfo(IntBound(-10, -1))
    b = a
    c = a.abstract_sub(b)

@given(order_info_and_contained_number2)
def test_abstract_sub_random(args):
    ((r1, n1), (r2, n2)) = args
    r3 = r1.abstract_sub(r2)
    # the result bound works for unsigned addition, regardless of overflow
    values = {r1: n1, r2: n2, r3: intmask(r_uint(n1) - r_uint(n2))}
    assert r3.contains(values)

def test_abstract_mul_no_relation():
    a = IntOrderInfo()
    b = IntOrderInfo()
    c = a.abstract_mul(b)
    # nothing is known about how a, b, c relate to each other (mul could overflow)
    assert not a._known_lt(c)
    assert not c._known_lt(a)
    assert not b._known_lt(c)
    assert not c._known_lt(b)

    a = IntOrderInfo(IntBound(-10, 10))
    b = IntOrderInfo(IntBound(-10, 10))
    c = a.abstract_mul(b)
    assert not a._known_lt(c)
    assert not b._known_lt(c)

    a = IntOrderInfo(IntBound(1, 10))
    b = IntOrderInfo(IntBound(-6, -4))
    c = a.abstract_mul(b)
    assert not a._known_lt(c)
    assert not b._known_lt(c)

    a = IntOrderInfo(IntBound(1, 10))
    b = IntOrderInfo(IntBound(-6, -4))
    c = b.abstract_mul(a)
    assert not a._known_lt(c)
    assert not b._known_lt(c)

    a = IntOrderInfo(IntBound(-20, -10))
    b = IntOrderInfo(IntBound(-6, -5))
    c = b.abstract_mul(a)
    assert a.known_lt(c) # not in order, implied by bounds, both
    assert b.known_lt(c)


def test_abstract_mul():
    a = IntOrderInfo(IntBound(1, 10))
    b = IntOrderInfo(IntBound(5, 6))
    c = a.abstract_mul(b)
    assert a._known_lt(c)
    assert not b._known_lt(c)

    a = IntOrderInfo(IntBound(1, 10))
    b = IntOrderInfo(IntBound(5, 6))
    c = b.abstract_mul(a)
    assert a._known_lt(c)
    assert not b._known_lt(c)

    a = IntOrderInfo(IntBound(2, 10))
    b = IntOrderInfo(IntBound(5, 6))
    c = a.abstract_mul(b)
    assert a._known_lt(c)
    assert b.known_lt(c) # implied by bounds

    a = IntOrderInfo(IntBound(2, 10))
    b = IntOrderInfo(IntBound(-100, -4))
    c = a.abstract_mul(b)
    assert c.known_lt(a) # implied by bounds
    assert c._known_lt(b)

    a = IntOrderInfo(IntBound(2, 10))
    b = IntOrderInfo(IntBound(-100, -4))
    c = b.abstract_mul(a)
    assert c.known_lt(a) # implied by bounds
    assert c._known_lt(b)

@given(order_info_and_contained_number2)
def test_abstract_mul_random(args):
    ((r1, n1), (r2, n2)) = args
    r3 = r1.abstract_mul(r2)
    values = {r1: n1, r2: n2, r3: intmask(r_uint(n1) * r_uint(n2))}
    assert r3.contains(values)



from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule


class IntOrderStateful(RuleBasedStateMachine):
    def __init__(self):
        RuleBasedStateMachine.__init__(self)
        self.abstract_to_contrete = {}

    orderinfos = Bundle("orderinfos")

    @rule(target=orderinfos, t=knownbits_and_bound_with_contained_number)
    def add_orderinfo(self, t):
        i, n = build_order_info_and_contained_number(t)
        self.abstract_to_contrete[i] = n
        return i

    @rule(a=orderinfos, b=orderinfos)
    def make_lt(self, a, b):
        na = self.abstract_to_contrete[a]
        nb = self.abstract_to_contrete[b]
        if na < nb:
            a.make_lt(b)

    @rule(a=orderinfos, b=orderinfos)
    def make_le(self, a, b):
        na = self.abstract_to_contrete[a]
        nb = self.abstract_to_contrete[b]
        if na <= nb:
            a.make_le(b)

    @rule(a=orderinfos, b=orderinfos, target=orderinfos)
    def add(self, a, b):
        na = self.abstract_to_contrete[a]
        nb = self.abstract_to_contrete[b]
        c = a.abstract_add(b)
        nc = intmask(na + nb)
        self.abstract_to_contrete[c] = nc
        return c

    @rule(a=orderinfos, b=orderinfos, target=orderinfos)
    def sub(self, a, b):
        na = self.abstract_to_contrete[a]
        nb = self.abstract_to_contrete[b]
        c = a.abstract_sub(b)
        nc = intmask(na - nb)
        self.abstract_to_contrete[c] = nc
        return c

    @rule(a=orderinfos, b=orderinfos, target=orderinfos)
    def mul(self, a, b):
        na = self.abstract_to_contrete[a]
        nb = self.abstract_to_contrete[b]
        c = a.abstract_mul(b)
        nc = intmask(na * nb)
        self.abstract_to_contrete[c] = nc
        return c

    @rule(a=orderinfos)
    def check_contains(self, a):
        assert a.contains(self.abstract_to_contrete)


TestIntOrderStateful = IntOrderStateful.TestCase
