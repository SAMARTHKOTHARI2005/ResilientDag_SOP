"""
Minimal drop-in replacement for the subset of SimPy (Environment, Store,
process/timeout) used by this project. Used automatically as a fallback
when the real `simpy` package is unavailable; behaviour matches simpy's
discrete-event semantics for the patterns used here
(`yield env.timeout(t)`, `yield store.get()`, `yield store.put(x)`).
"""
import heapq
import itertools


class Event:
    def __init__(self, env):
        self.env = env
        self.triggered = False
        self.value = None
        self.callbacks = []

    def trigger(self, value=None):
        self.triggered = True
        self.value = value
        for cb in self.callbacks:
            self.env._push(self.env.now, ("call", cb, value))
        self.callbacks = []

    def add_callback(self, cb):
        if self.triggered:
            self.env._push(self.env.now, ("call", cb, self.value))
        else:
            self.callbacks.append(cb)


class Environment:
    def __init__(self):
        self.now = 0.0
        self._heap = []
        self._counter = itertools.count()

    def _push(self, time, item):
        heapq.heappush(self._heap, (time, next(self._counter), item))

    def timeout(self, delay, value=None):
        ev = Event(self)
        self._push(self.now + delay, ("trigger", ev, value))
        return ev

    def process(self, gen):
        def resume(value=None):
            try:
                ev = gen.send(value)
            except StopIteration:
                return
            ev.add_callback(resume)
        resume(None)

    def step(self):
        if not self._heap:
            return False
        time, _, item = heapq.heappop(self._heap)
        self.now = time
        kind = item[0]
        if kind == "trigger":
            _, ev, value = item
            ev.trigger(value)
        elif kind == "call":
            _, cb, value = item
            cb(value)
        return True


class Store:
    def __init__(self, env):
        self.env = env
        self.items = []
        self.get_waiters = []

    def put(self, item):
        ev = Event(self.env)
        if self.get_waiters:
            waiter = self.get_waiters.pop(0)
            waiter.trigger(item)
        else:
            self.items.append(item)
        ev.trigger(None)
        return ev

    def get(self):
        ev = Event(self.env)
        if self.items:
            ev.trigger(self.items.pop(0))
        else:
            self.get_waiters.append(ev)
        return ev