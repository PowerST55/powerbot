import asyncio
async def add_text_to_screentext(text, server):
    await server.addtexthub(text)