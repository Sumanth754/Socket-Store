"""End-to-end demo of Socket-Store.

Starts the server in-process, talks to it over a real TCP socket, and prints
a table of every command working. Great for recording a terminal demo GIF.

Usage:
    python demo.py
"""

import asyncio

from server import DatabaseServer


async def main() -> None:
    server = DatabaseServer(host="127.0.0.1", port=8888)
    task = asyncio.create_task(server.start())
    await asyncio.sleep(0.1)

    reader, writer = await asyncio.open_connection("127.0.0.1", 8888)

    async def ask(command: str) -> str:
        writer.write(command.encode() + b"\n")
        await writer.drain()
        return (await reader.readline()).decode().strip()

    commands = [
        "PING",
        "SET name Alice",
        "SET role QA Engineer",
        "GET name",
        "GET missing",
        "EXISTS name",
        "EXISTS missing",
        "SET counter 10",
        "INCR counter",
        "DECR counter",
        "EXPIRE temp 1",
        "TTL temp",
        "KEYS",
        "DELETE name",
        "KEYS",
        "FLUSH",
        "GET name",
    ]

    width = max(len(cmd) for cmd in commands)
    print(f"SOCKET-STORE DEMO - talking to 127.0.0.1:8888")
    print("-" * (width + 8))
    for command in commands:
        print(f"{command.ljust(width)}  ->  {await ask(command)}")
    print("-" * (width + 8))

    writer.close()
    await writer.wait_closed()
    task.cancel()
    await asyncio.sleep(0.05)


if __name__ == "__main__":
    asyncio.run(main())