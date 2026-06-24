import importlib
import pkgutil

import mcp_server.tools as _pkg

for _finder, _name, _ispkg in pkgutil.iter_modules(_pkg.__path__, _pkg.__name__ + "."):
    if _ispkg:
        importlib.import_module(_name)
