from pipetools.debug import get_name, set_name, repr_args
from pipetools.debug import pipe_exception_handler


class Pipe(object):
    """
    Pipe-style combinator.

    Example::

        p = pipe | F | G | H

        p(x) == H(G(F(x)))

    """
    def __init__(self, func=None):
        self.func = func
        self.__name__ = str(self)

    def __str__(self):
        return get_name(self.func)

    @staticmethod
    def compose(first, second):
        name = '{0} | {1}'.format(get_name(first), get_name(second))

        def composite(*args, **kwargs):
            with pipe_exception_handler('pipe | ' + name):
                return second(first(*args, **kwargs))
        return set_name(name, composite)

    @classmethod
    def bind(cls, first, second):
        return cls(
            first if second is None else
            second if first is None else
            cls.compose(first, second))

    def __or__(self, next_func):
        return self.bind(self.func, prepare_function_for_pipe(next_func))

    def __ror__(self, prev_func):
        return self.bind(prepare_function_for_pipe(prev_func), self.func)

    def __lt__(self, thing):
        return self.func(thing) if self.func else thing

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

pipe = Pipe()


class Maybe(Pipe):

    @staticmethod
    def compose(first, second):
        name = '{0} ?| {1}'.format(get_name(first), get_name(second))

        def composite(*args, **kwargs):
            with pipe_exception_handler('maybe ?| ' + name):
                result = first(*args, **kwargs)
                return None if result is None else second(result)
        return set_name(name, composite)

    def __lt__(self, thing):
        return (
            None if thing is None else
            self.func(thing) if self.func else
            thing)

maybe = Maybe()


def prepare_function_for_pipe(thing):
    if isinstance(thing, XObject):
        return ~thing
    if isinstance(thing, tuple):
        return xcurry(*thing)
    if isinstance(thing, basestring):
        return StringFormatter(thing)
    if callable(thing):
        return thing
    raise ValueError('Cannot pipe %s' % thing)


def StringFormatter(template):

    f = unicode(template).format

    def format(content):
        if isinstance(content, dict):
            return f(**content)
        if _iterable(content):
            return f(*content)
        return f(content)

    return set_name("format('%s')" % template[:20], format)


def _iterable(obj):
    return (hasattr(obj, '__iter__')
        or hasattr(obj, '__getitem__')
        and not isinstance(obj, basestring))


class XObject(object):

    def __init__(self, func=None):
        self._func = func
        self.__name__ = get_name(func) if func else 'X'

    def __repr__(self):
        return self.__name__

    def __invert__(self):
        return self._func or set_name('X', lambda x: x)

    def bind(self, name, func):
        try:
            func.__name__ = str(name)
        except UnicodeError:
            func.__name__ = repr(name)
        return XObject((self._func | func) if self._func else (pipe | func))

    def __call__(self, *args, **kwargs):
        name = 'X(%s)' % repr_args(*args, **kwargs)
        return self.bind(name, lambda x: x(*args, **kwargs))

    def __eq__(self, other):
        return self.bind('X == {0!r}'.format(other), lambda x: x == other)

    def __getattr__(self, name):
        return self.bind(u'X.{0}'.format(name), lambda x: getattr(x, name))

    def __getitem__(self, item):
        return self.bind('X[{0!r}]'.format(item), lambda x: x[item])

    def __gt__(self, other):
        return self.bind('X > {0!r}'.format(other), lambda x: x > other)

    def __ge__(self, other):
        return self.bind('X >= {0!r}'.format(other), lambda x: x >= other)

    def __lt__(self, other):
        return self.bind('X < {0!r}'.format(other), lambda x: x < other)

    def __le__(self, other):
        return self.bind('X <= {0!r}'.format(other), lambda x: x <= other)

    def __mod__(self, y):
        return self.bind('X % {0!r}'.format(y), lambda x: x % y)

    def __ne__(self, other):
        return self.bind('X != {0!r}'.format(other), lambda x: x != other)

    def __neg__(self):
        return self.bind('-X', lambda x: -x)

    def __mul__(self, other):
        return self.bind('X * {0!r}'.format(other), lambda x: x * other)

    def __add__(self, other):
        return self.bind('X + {0!r}'.format(other), lambda x: x + other)

    def __sub__(self, other):
        return self.bind('X - {0!r}'.format(other), lambda x: x - other)

    def __pow__(self, other):
        return self.bind('X ** {0!r}'.format(other), lambda x: x ** other)

    def __ror__(self, func):
        return pipe | func | self

    def __or__(self, func):
        if isinstance(func, Pipe):
            return func.__ror__(self)
        return pipe | self | func

    def _in_(self, y):
        return self.bind('X._in_({0!r})'.format(y), lambda x: x in y)


X = XObject()


def xcurry(func, *xargs, **xkwargs):
    """
    Like :func:`functools.partial`, but can take an :class:`XObject`
    placeholder that will be replaced with the first positional argument
    when the curried function is called.

    Useful when the function's positional arguments' order doesn't fit your
    situation, e.g.:

    >>> reverse_range = xcurry(range, X, 0, -1)
    >>> reverse_range(5)
    [5, 4, 3, 2, 1]

    It can also be used to transform the positional argument to a keyword
    argument, which can come in handy inside a *pipe*::

        xcurry(objects.get, id=X)

    Also the XObjects are evaluated, which can be used for some sort of
    destructuring of the argument::

        xcurry(somefunc, name=X.name, number=X.contacts['number'])

    Lastly, unlike :func:`functools.partial`, this creates a regular function
    which will bind to classes (like the ``curry`` function from
    ``django.utils.functional``).
    """
    any_x = any(isinstance(a, XObject) for a in xargs + tuple(xkwargs.values()))
    use = lambda x, value: (~x)(value) if isinstance(x, XObject) else x

    def xcurried(*func_args, **func_kwargs):
        if any_x:
            if not func_args:
                raise ValueError('Function "%s" curried with an X placeholder '
                    'but called with no positional arguments.' % get_name(func))
            first = func_args[0]
            rest = func_args[1:]
            args = tuple(use(x, first) for x in xargs) + rest
            kwargs = dict((k, use(x, first)) for k, x in xkwargs.iteritems())
            kwargs.update(func_kwargs)
        else:
            args = xargs + func_args
            kwargs = dict(xkwargs, **func_kwargs)
        return func(*args, **kwargs)

    name = '%s(%s)' % (get_name(func), repr_args(*xargs, **xkwargs))
    return set_name(name, xcurried)
