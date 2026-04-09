"""
nanobot - A lightweight AI agent framework
"""

import warnings

warnings.filterwarnings(
    "ignore",
    category=SyntaxWarning,
    module="pydub.utils",
    message=r".*invalid escape sequence.*",
)

__version__ = "0.1.5"
__logo__ = "🐈"

from nanobot.nanobot import Nanobot, RunResult
