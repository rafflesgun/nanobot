"""
nanobot - A lightweight AI agent framework
"""

import warnings

# Suppress pydub SyntaxWarnings about invalid escape sequences
# These occur in pydub 0.25.1 due to non-raw strings in regex patterns
warnings.filterwarnings(
    "ignore",
    category=SyntaxWarning,
    module="pydub.utils",
    message=r".*invalid escape sequence.*",
)

__version__ = "0.1.4.post5"
__logo__ = "🐈"
