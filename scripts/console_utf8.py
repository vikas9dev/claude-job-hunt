"""console_utf8.py — force UTF-8 stdin/stdout/stderr for the SR scripts.

Windows defaults the console to cp1252, so print()-ing emoji or box-drawing
characters raises UnicodeEncodeError — and piped stdin (e.g. job_track.py
--stdin-json heredocs) silently MOJIBAKES emoji on decode. Reconfiguring all
three streams to UTF-8 fixes both. No-op on Linux/WSL.

Import purely for its side effect — put `import console_utf8` at the top of any
script that prints, or import a module (e.g. sr_utils) that already does so.
"""

import sys

for _stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")
