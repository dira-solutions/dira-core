from typing import Any, Callable

from rq.job import Callback
from rq.defaults import CALLBACK_TIMEOUT
from rq.utils import parse_timeout

import inspect


class AscCallback(Callback):
    def __init__(self, func: str | Callable[..., Any], params=dict(), timeout: Any | None = None):
        if not isinstance(func, str) and not inspect.isfunction(func) and not inspect.isbuiltin(func) and not inspect.ismethod(func):
            raise ValueError('Callback `func` must be a string or function')

        self.func = func
        self.timeout = parse_timeout(timeout) if timeout else CALLBACK_TIMEOUT
        self.params = params