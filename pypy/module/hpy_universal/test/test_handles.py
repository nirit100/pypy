import pytest
from pypy.module.hpy_universal import handles
from pypy.module.hpy_universal.handles import HandleManager, HandleFinalizer

class FakeSpace(object):
    def __init__(self):
        self._cache = {}

    def fromcache(self, cls):
        if cls not in self._cache:
            self._cache[cls] = cls(self)
        return self._cache[cls]

    def __getattr__(self, name):
        return '<fakespace.%s>' % name

@pytest.fixture
def fakespace():
    return FakeSpace()

def test_fakespace(fakespace):
    assert fakespace.w_ValueError == '<fakespace.w_ValueError>'
    def x(space):
        return object()
    assert fakespace.fromcache(x) is fakespace.fromcache(x)

class TestHandleManager(object):

    def test_first_handle_is_not_zero(self, fakespace):
        mgr = HandleManager(fakespace)
        h = mgr.new('hello')
        assert h > 0

    def test_new(self, fakespace):
        mgr = HandleManager(fakespace)
        h = mgr.new('hello')
        assert mgr.handles_w[h] == 'hello'

    def test_close(self, fakespace):
        mgr = HandleManager(fakespace)
        h = mgr.new('hello')
        assert mgr.close(h) is None
        assert mgr.handles_w[h] is None

    def test_deref(self, fakespace):
        mgr = HandleManager(fakespace)
        h = mgr.new('hello')
        assert mgr.deref(h) == 'hello'     # 'hello' is a fake W_Root
        assert mgr.deref(h) == 'hello'

    def test_consume(self, fakespace):
        mgr = HandleManager(fakespace)
        h = mgr.new('hello')
        assert mgr.consume(h) == 'hello'
        assert mgr.handles_w[h] is None

    def test_freelist(self, fakespace):
        mgr = HandleManager(fakespace)
        h0 = mgr.new('hello')
        h1 = mgr.new('world')
        assert mgr.consume(h0) == 'hello'
        assert mgr.free_list == [h0]
        h2 = mgr.new('hello2')
        assert h2 == h0
        assert mgr.free_list == []

    def test_dup(self, fakespace):
        mgr = HandleManager(fakespace)
        h0 = mgr.new('hello')
        h1 = mgr.dup(h0)
        assert h1 != h0
        assert mgr.consume(h0) == mgr.consume(h1) == 'hello'

class TestFinalizer(object):

    class MyFinalizer(HandleFinalizer):
        def __init__(self, seen, data):
            self.seen = seen
            self.data = data
        def finalize(self, h, obj):
            self.seen.append((h, obj, self.data))

    def test_finalizer(self, fakespace):
        mgr = HandleManager(fakespace)
        seen = []
        h0 = mgr.new('hello')
        h1 = mgr.dup(h0)
        h2 = mgr.dup(h0)
        mgr.attach_finalizer(h0, self.MyFinalizer(seen, 'foo'))
        mgr.attach_finalizer(h1, self.MyFinalizer(seen, 'bar'))
        assert seen == []
        #
        mgr.close(h1)
        assert seen == [(h1, 'hello', 'bar')]
        #
        mgr.close(h2)
        assert seen == [(h1, 'hello', 'bar')]
        #
        mgr.close(h0)
        assert seen == [(h1, 'hello', 'bar'),
                        (h0, 'hello', 'foo')]

    def test_clear(self, fakespace):
        mgr = HandleManager(fakespace)
        seen = []
        h0 = mgr.new('hello')
        mgr.attach_finalizer(h0, self.MyFinalizer(seen, 'foo'))
        mgr.close(h0)
        assert seen == [(h0, 'hello', 'foo')]
        #
        # check that the finalizer array is cleared when we close the handle
        # and that we don't run the finalizer for a wrong object
        h1 = mgr.new('world')
        assert h1 == h0
        mgr.close(h1)
        assert seen == [(h0, 'hello', 'foo')]

    def test_multiple_finalizers(self, fakespace):
        mgr = HandleManager(fakespace)
        seen = []
        h0 = mgr.new('hello')
        mgr.attach_finalizer(h0, self.MyFinalizer(seen, 'foo'))
        mgr.attach_finalizer(h0, self.MyFinalizer(seen, 'bar'))
        mgr.close(h0)
        assert seen == [(h0, 'hello', 'foo'),
                        (h0, 'hello', 'bar')]




def test_using(fakespace):
    mgr = fakespace.fromcache(HandleManager)
    with handles.using(fakespace, 'hello') as h:
        assert mgr.handles_w[h] == 'hello'
    assert mgr.handles_w[h] is None
