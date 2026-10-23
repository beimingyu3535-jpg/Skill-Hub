"""action_eb_delete: component package public entrypoint."""
from importlib.util import find_spec

from . import component as _component

COMPONENT = _component.COMPONENT
if find_spec(f"{__name__}.converter") is not None:
    from .converter import CONVERTER
else:
    CONVERTER = getattr(_component, "CONVERTER", None)
