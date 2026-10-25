"""Internal modules. Import each module here and merge its ROUTES."""

from app.modules import example

ROUTES = {**example.ROUTES}
