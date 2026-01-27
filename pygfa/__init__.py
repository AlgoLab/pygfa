from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygfa.gfa import GFA

from pygfa import bgfa
from pygfa import gfa
from pygfa.bgfa import to_bgfa
from pygfa.dovetail_operations.operations import *  # common operations
from pygfa.operations import *  # common operations

__version__ = "0.1.0"
__all__ = [
    "GFA",
    "bgfa",
    "gfa",
    "to_bgfa",
]
