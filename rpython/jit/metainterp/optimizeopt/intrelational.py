from rpython.jit.metainterp.optimize import InvalidLoop
from rpython.jit.metainterp.optimizeopt.intutils import IntBound

class IntOrderInfo(object):

    def __init__(self, bounds=None):
        if bounds is None:
            bounds = IntBound.unbounded()
        self.bounds = bounds
        self.relations = []

    def __repr__(self):
        lines = self.pp()
        return '\n'.join(lines)

    def pp(self, indent=0, indent_inc=4, op_pfx=""):
        indent_prefix = indent * ' '
        op_pfx = "" if op_pfx == "" else op_pfx + ' '
        lines = []
        if len(self.relations) == 0:
            lines.append(indent_prefix + op_pfx + "IntOrderInfo(" + repr(self.bounds) + ")")
        else:
            lines.append(indent_prefix + op_pfx + "IntOrderInfo(" + repr(self.bounds) + "  {")
            for rel in self.relations:
                rel_pp = rel.pp(indent+indent_inc, indent_inc)
                lines.extend(rel_pp)
            lines.append(indent_prefix + len(op_pfx)*' ' + "})")
        return lines


    def contains(self, concrete_values):
        if isinstance(concrete_values, dict):
            return self._contains(concrete_values)
        else:
            # assume that `default_values` is a single integer
            return self.bounds.contains(concrete_values)

    def make_lt(self, other):
        # TODO: if make_lt returns False we can return early
        self.bounds.make_lt(other.bounds)
        self._make_lt(other)

    def known_lt(self, other):
        # ask bounds first, as it is cheaper
        return self.bounds.known_lt(other.bounds) \
            or self._known_lt(other)

    def known_ne(self, other):
        return self.bounds.known_ne(other.bounds) or self._known_lt(other) or other._known_lt(self)

    def abstract_add_const(self, const):
        bound_other = IntBound.from_constant(const)
        bounds = self.bounds.add_bound(bound_other)
        res = IntOrderInfo(bounds)
        if self.bounds.add_bound_cannot_overflow(bound_other):
            if const > 0:
                self.make_lt(res)
            elif const < 0:
                res.make_lt(self)
        return res

    def abstract_add(self, other):
        bounds = self.bounds.add_bound(other.bounds)
        res = IntOrderInfo(bounds)
        if self.bounds.add_bound_cannot_overflow(other.bounds):
            if other.bounds.known_gt_const(0):
                self.make_lt(res)
            elif other.bounds.known_lt_const(0):
                res.make_lt(self)
            if self.bounds.known_gt_const(0):
                other.make_lt(res)
            elif self.bounds.known_lt_const(0):
                res.make_lt(other)
        return res

    def abstract_sub(self, other):
        bounds = self.bounds.sub_bound(other.bounds)
        res = IntOrderInfo(bounds)
        if self.bounds.sub_bound_cannot_overflow(other.bounds):
            if other.bounds.known_gt_const(0):
                res.make_lt(self)
            elif other.bounds.known_lt_const(0):
                self.make_lt(res)
            # refine resulting bounds by operand's relations
            if self._known_lt(other):
                res.bounds.make_lt_const(0)
            elif other._known_lt(self):
                res.bounds.make_gt_const(0)
        return res

    def abstract_mul(self, other):
        # TODO: This is probably unsound or at least not precise!
        bounds = self.bounds.mul_bound(other.bounds)
        res = IntOrderInfo(bounds)
        if self.bounds.mul_bound_cannot_overflow(other.bounds):
            if other.bounds.known_gt_const(1):
                if self.bounds.known_gt_const(0):
                    self.make_lt(res)
                elif self.bounds.known_lt_const(0):
                    res.make_lt(self)
            if self.bounds.known_gt_const(1):
                if other.bounds.known_gt_const(0):
                    other.make_lt(res)
                elif other.bounds.known_lt_const(0):
                    res.make_lt(other)
        return res

    def _contains(self, concrete_values):
        # concrete_values: dict[IntOrderInfo, int]
        for order, value in concrete_values.iteritems():
            if not order.bounds.contains(value):
                return False
            for relation in order.relations:
                if not relation.bigger in concrete_values:
                    continue
                if not value < concrete_values[relation.bigger]:
                    return False
        return True

    def _make_lt(self, other):
        if other.known_lt(self) or self is other:
            raise InvalidLoop("Invalid relations: self < other < self")
        if self.known_lt(other):
            return
        self.relations.append(Bigger(other))

    def _known_lt(self, other):
        todo = self.relations[:]
        seen = dict()
        while todo:
            relation = todo.pop()
            interm = relation.bigger
            if interm in seen:
                continue
            if interm is other:
                return True
            seen[interm] = None
            todo.extend(interm.relations)
        return False

class Bigger(object):

    def __init__(self, bigger):
        self.bigger = bigger

    def pp(self, indent=0, indent_inc=2):
        return self.bigger.pp(indent, indent_inc, '<')
