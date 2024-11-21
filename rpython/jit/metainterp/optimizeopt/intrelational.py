from rpython.jit.metainterp.optimize import InvalidLoop
from rpython.jit.metainterp.optimizeopt.intutils import IntBound

class IntOrderInfo(object):

    def __init__(self, bounds=None):
        if bounds is None:
            bounds = IntBound.unbounded()
        self.bounds = bounds
        self.relations = []

    def __str__(self):
        lines = self.pp()
        return '\n'.join(lines)

    def pp(self, indent=0, indent_inc=4, op_pfx="", seen=None):
        if seen is None:
            seen = {}
        indent_prefix = indent * ' '
        op_pfx = "" if op_pfx == "" else op_pfx + ' '
        if self in seen:
            return [indent_prefix + op_pfx + seen[self]]
        else:
            seen[self] = name = 'i%s' % len(seen)
        lines = []
        if len(self.relations) == 0:
            lines.append(indent_prefix + op_pfx + "%s = IntOrderInfo(" % name + repr(self.bounds) + ")")
        else:
            lines.append(indent_prefix + op_pfx + "%s = IntOrderInfo(" % name + repr(self.bounds) + "  {")
            for rel in self.relations:
                rel_pp = rel.pp(indent+indent_inc, indent_inc, seen=seen)
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
        if self.bounds.known_lt(other.bounds):
            return
        self.bounds.make_lt(other.bounds)
        self._make_lt(other)

    def known_lt(self, other):
        # ask bounds first, as it is cheaper
        return self.bounds.known_lt(other.bounds) \
            or self._known_lt(other)

    def make_le(self, other):
        if self.bounds.known_le(other.bounds):
            return
        self.bounds.make_le(other.bounds)
        self._make_le(other)

    def known_le(self, other):
        # ask bounds first, as it is cheaper
        return self is other or self.bounds.known_le(other.bounds) \
            or self._known_le(other)

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
                if not relation.other in concrete_values:
                    continue
                if not relation.concrete_cmp(value, concrete_values[relation.other]):
                    return False
        return True

    def _make_lt(self, other):
        # TODO: should this be other.known_le(self) now?
        if other.known_lt(self) or self is other:
            raise InvalidLoop("Invalid relations: self < other <= self")
        if self.known_lt(other):
            return
        for index, relation in enumerate(self.relations):
            if relation.other is other:
                assert isinstance(relation, BiggerOrEqual)
                self.relations[index] = Bigger(other)
                return
        self.relations.append(Bigger(other))

    def _known_lt(self, other):
        biggest_distance = self._astar(other)
        return biggest_distance > 0

    def _astar(self, other, cutoff=None):
        todo = {self}
        best_distance = {self: 0} # node -> best distance so far, from self
        best_distance[other] = -1
        while todo:
            # pick element from todo with biggest distance
            # TODO: use a priority queue instead
            best_distance_seen = -1
            best = None
            for current in todo:
                if best_distance[current] > best_distance_seen:
                    best_distance_seen = best_distance[current]
                    best = current
            if best is None:
                current = todo.pop()
            else:
                todo.remove(best)
                current = best
            # found the goal?
            for relation in current.relations:
                tentative_score = best_distance[current] + relation.min_margin()
                if tentative_score > best_distance.get(relation.other, -1):
                    best_distance[relation.other] = tentative_score
                    todo.add(relation.other)
            # check cutoff
            if cutoff is not None and best_distance[other] >= cutoff:
                break

        return best_distance[other]

    def _make_le(self, other):
        if other.known_lt(self):
            raise InvalidLoop("Invalid relations: self <= other < self")
        if self.known_le(other):
            return
        self.relations.append(BiggerOrEqual(other))

    def _known_le(self, other):
        todo = self.relations[:]
        seen = dict()
        while todo:
            relation = todo.pop()
            interm = relation.other
            if interm in seen:
                continue
            if interm is other:
                return True
            seen[interm] = None
            todo.extend(interm.relations)
        return False

class Relation(object):
    def __init__(self, other):
        self.other = other

    def __str__(self):
        lines = self.pp()
        return '\n'.join(lines)

    def pp(self, indent=0, indent_inc=2, seen=None):
        raise NotImplementedError("abstract method")

    def concrete_cmp(self, val1, val2):
        """
        Return True iff for the two concrete values
        val1 and val2 and this relation R,
        'val1 R val2' holds, False otherwise

        Args:
            val1 (int): left-hand-side concrete value to compare
            val2 (int): right-hand-side concrete value to compare

        Returns:
            bool: True if 'val1 R val2', False otherwise
        """
        raise NotImplementedError("abstract method")

    def min_margin(self):
        """
        Returns the minimum concrete value difference implied by this relation.

        Returns:
            int: minimum difference between two concrete values for this relation
        """
        raise NotImplementedError("abstract method")

class Bigger(Relation):
    def concrete_cmp(self, val1, val2):
        return val1 < val2 # TODO: looks a bit irritating with respect to the class name now

    def min_margin(self):
        return 1

    def pp(self, indent=0, indent_inc=2, seen=None):
        return self.other.pp(indent, indent_inc, '<', seen=seen)

class BiggerOrEqual(Relation):
    def concrete_cmp(self, val1, val2):
        return val1 <= val2

    def min_margin(self):
        return 0

    def pp(self, indent=0, indent_inc=2, seen=None):
        return self.other.pp(indent, indent_inc, '<=', seen=seen)
