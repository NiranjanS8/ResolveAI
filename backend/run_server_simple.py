import sys
import asyncio

if sys.platform == "win32":
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)

import uvicorn

uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="debug", reload=False)