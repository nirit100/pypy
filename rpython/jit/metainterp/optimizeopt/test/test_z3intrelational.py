from __future__ import print_function
import sys
import gc
import pytest
from rpython.jit.metainterp.optimizeopt.intrelational import IntOrderInfo
from rpython.jit.metainterp.optimizeopt.intutils import IntBound
from rpython.jit.metainterp.optimize import InvalidLoop
from rpython.jit.metainterp.optimizeopt.test.test_z3intbound import z3_add_overflow, z3_sub_overflow, z3_mul_overflow, to_z3 as to_z3_bounds
from rpython.jit.metainterp.optimizeopt.test.test_intrelational import order_info_and_contained_number2

from rpython.rlib.rarithmetic import r_uint, intmask, LONG_BIT

try:
    import z3
    from hypothesis import given, strategies, assume, example
except ImportError:
    pytest.skip("please install z3 (z3-solver on pypi) and hypothesis")


def BitVecVal(value):
    return z3.BitVecVal(value, LONG_BIT)

def BitVec(name):
    return z3.BitVec(name, LONG_BIT)

def z3_with_reduced_bitwidth(width):
    def dec(test):
        assert test.func_name.endswith("logic") # doesn't work for code in intutils.py
        def newtest(*args, **kwargs):
            global LONG_BIT
            old_value = LONG_BIT
            LONG_BIT = width
            try:
                return test(*args, **kwargs)
            finally:
                LONG_BIT = old_value
        return newtest
    return dec

MAXINT = sys.maxint
MININT = -sys.maxint - 1

class CheckError(Exception):
    pass


def prove_implies(*args, **kwargs):
    last = args[-1]
    prev = args[:-1]
    return prove(z3.Implies(z3.And(*prev), last), **kwargs)

def teardown_function(function):
    # z3 doesn't add enough memory pressure, just collect after every function
    # to counteract
    gc.collect()

def prove(cond):
    solver = z3.Solver()
    #print('checking', cond)
    z3res = solver.check(z3.Not(cond))
    if z3res == z3.unsat:
        pass
    elif z3res == z3.sat:
        # not possible to prove!
        global model
        model = solver.model()
        raise CheckError(cond, model)

# __________________________________________________________________
# proofs

def test_abstract_add_logic():
    a = BitVec('a')
    b = BitVec('b')
    res, no_ovf = z3_add_overflow(a, b)
    prove_implies(no_ovf, b > 0, res > a)
    prove_implies(no_ovf, b < 0, res < a)

def test_abstract_sub_logic():
    a = BitVec('a')
    b = BitVec('b')
    res, no_ovf = z3_sub_overflow(a, b)
    prove_implies(no_ovf, b > 0, res < a)
    prove_implies(no_ovf, b < 0, res > a)
    prove_implies(no_ovf, a < b, res < 0)
    prove_implies(no_ovf, b < a, res > 0)

@z3_with_reduced_bitwidth(32)
def test_abstract_mul_logic():
    a = BitVec('a')
    b = BitVec('b')
    res, no_ovf = z3_mul_overflow(a, b)
    prove_implies(no_ovf, a > 0, b > 1, a < res)
    prove_implies(no_ovf, a < 0, b > 1, a > res)

# __________________________________________________________________
# bounded model checking

order_info2 = strategies.builds(
    lambda info: (info[0][0], info[1][0]),
    order_info_and_contained_number2
)

def to_z3(*orderinfos):
    z3dict = {}
    for orderinfo in orderinfos:
        variable, cond = to_z3_bounds(orderinfo.bounds)
        z3dict[orderinfo] = variable, cond
    for orderinfo in orderinfos:
        variable, cond = z3dict[orderinfo]
        components = [cond]
        for relation in orderinfo.relations:
            components.append(variable < z3dict[relation.bigger][0])
        if len(components) > 1:
            z3dict[orderinfo] = variable, z3.And(*components)
    return z3dict

@given(order_info2)
def test_add(info):
    i1, i2 = info
    z3dict_before = to_z3(i1, i2)
    var1, formula1 = z3dict_before[i1]
    var2, formula2 = z3dict_before[i2]
    i3 = i1.abstract_add(i2)
    z3dict_after = to_z3(i1, i2, i3)
    var1a, formula1_after = z3dict_after[i1]
    var2a, formula2_after = z3dict_after[i2]
    var3a, formula3_after = z3dict_after[i3]
    prove_implies(formula1, formula2, var1 == var1a, var2 == var2a, var3a == var1 + var2, z3.And(formula1_after, formula2_after, formula3_after))
