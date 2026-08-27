"""Process-local active Config context for a service or manager class.

Path/storage helpers read the active Config from a ContextVar instead of taking
it as a parameter, so callers never have to thread it through every function
signature.

A class binds its Config for the duration of each public call via
with_active_config. This keeps multiple instances correct in two ways.

Same thread: use_config uses a token-based reset, so each call restores the
previous value on exit. Sequential calls clean up after themselves; nested calls
(one method invoking another) stack and unstack without leaking.

Separate threads and asyncio Tasks: ContextVars are per-execution-context — each
OS thread and each asyncio Task has its own isolated value — so two instances
running concurrently in different threads never see each other's Config. Methods
that dispatch work to a thread pool capture the current context via
contextvars.copy_context() and execute the worker with ctx.run(), propagating the
correct Config into the background thread even after the caller's with block exits.
"""

from __future__ import annotations

import contextlib
import functools
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional, Protocol, TypeVar

from adsk.flow.local.storage_manager.config import Config

if TYPE_CHECKING:
    from typing import Concatenate, ParamSpec

_active_config: ContextVar[Optional[Config]] = ContextVar("active_config", default=None)


def get_active_config() -> Config:
    """Return the Config bound for the current context.

    Raises RuntimeError if none is active — every public entry point should bind
    one via with_active_config before reaching helpers that call this, so an unset
    value means a helper was called outside of a managed operation.
    """
    config = _active_config.get()
    if config is None:
        raise RuntimeError(
            "No active Config bound. get_active_config() was called outside of a with_active_config-decorated method."
        )
    return config


@contextlib.contextmanager
def use_config(config: Config) -> Generator[None, None, None]:
    """Bind config as the active Config for the duration of the with block."""
    token = _active_config.set(config)
    try:
        yield
    finally:
        _active_config.reset(token)


class HasActiveConfig(Protocol):
    """Contract for classes whose methods can be decorated with with_active_config."""

    _config: Config


_Self = TypeVar("_Self", bound=HasActiveConfig)
if TYPE_CHECKING:
    _P = ParamSpec("_P")
_Ret = TypeVar("_Ret")


def with_active_config(
    method: Callable[Concatenate[_Self, _P], _Ret],
) -> Callable[Concatenate[_Self, _P], _Ret]:
    """Decorator that binds self._config as the active Config for the duration of the call.

    The decorated class must satisfy the HasActiveConfig protocol (i.e. expose a
    _config attribute of type Config). Pyright enforces this at decoration time via
    the _Self bound on HasActiveConfig.
    """

    @functools.wraps(method)
    def wrapper(self: _Self, *args: Any, **kwargs: Any) -> _Ret:
        with use_config(self._config):
            return method(self, *args, **kwargs)

    return wrapper
