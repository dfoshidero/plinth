"""An example module. Copy this file to start a new one, then register it in __init__.py.

Modules talk to each other only through functions they choose to expose, which keeps
the boundaries clean enough to split a module into its own service later.
"""


def hello() -> tuple[int, dict]:
    return 200, {"module": "example", "message": "hello"}


ROUTES = {"/example/hello": hello}
