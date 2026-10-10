import sys
import asyncio

# On Windows, psycopg v3 async requires SelectorEventLoop
if sys.platform == "win32":
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)
else:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import uvicorn

if __name__ == "__main__":
    config = uvicorn.Config("app.main:app", host="0.0.0.0", port=8000, loop="asyncio", reload=False)
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())