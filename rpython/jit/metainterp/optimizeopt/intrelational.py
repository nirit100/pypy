from rpython.jit.metainterp.optimize import InvalidLoop


class IntOrderInfo(object):

    def __init__(self):
        self.relations = []

    def contains(self, concrete_values):
        # concrete_values: dict[IntOrderInfo, int]
        for order, value in concrete_values.iteritems():
            for relation in order.relations:
                if not relation.bigger in concrete_values:
                    continue
                if not value < concrete_values[relation.bigger]:
                    return False
        return True

    def make_lt(self, other):
        if other.known_lt(self):
            raise InvalidLoop("Invalid relations: self < other < self")
        if self.known_lt(other):
            return
        self.relations.append(Bigger(other))

    def known_lt(self, other):
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
