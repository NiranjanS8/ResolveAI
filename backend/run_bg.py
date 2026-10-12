import sys
import asyncio
import uvicorn

if sys.platform == "win32":
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)

config = uvicorn.Config("app.main:app", host="0.0.0.0", port=8000, log_level="debug", reload=False)
server = uvicorn.Server(config)
asyncio.get_event_loop().run_until_complete(server.serve())