"""Socket-Store interactive client — connects to the Socket-Store server over TCP."""

import argparse
import asyncio
import sys

HELP = """Socket-Store commands:
  SET <key> <value> [EX <seconds>]   Store a value (optionally with a TTL)
  GET <key>                          Read a value
  DELETE <key>                       Remove a key (returns 1/0)
  EXISTS <key>                       Check if a key exists (returns 1/0)
  KEYS                               List all keys
  EXPIRE <key> <seconds>             Set a key's time-to-live
  TTL <key>                          Show remaining TTL (-1 = none, -2 = missing)
  INCR <key> / DECR <key>            Increment / decrement an integer
  FLUSH                              Delete every key
  PING                               Round-trip check (returns PONG)
  help                               Show this help
  exit / quit                        Close the client
"""


async def run_client(host: str, port: int) -> None:
    try:
        reader, writer = await asyncio.open_connection(host, port)
    except (ConnectionRefusedError, OSError):
        print(f"Could not connect to {host}:{port}. Is the server running?")
        return

    print(f"Connected to Socket-Store at {host}:{port}")
    print("Type 'help' for commands, 'exit' to quit.")

    try:
        while True:
            # Run input() in a thread so the event loop can still read replies.
            command = await asyncio.get_running_loop().run_in_executor(
                None, sys.stdin.readline
            )
            command = command.strip()
            if not command:
                continue
            if command.lower() in ("exit", "quit"):
                break
            if command.lower() == "help":
                print(HELP)
                continue
            writer.write(command.encode() + b"\n")
            await writer.drain()
            response = await reader.readline()
            print(response.decode().strip())
    except (asyncio.IncompleteReadError, ConnectionResetError):
        print("Connection to the server was lost.")
    finally:
        print("Closing the connection.")
        writer.close()
        await writer.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="Socket-Store interactive client")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Server port (default 8888)")
    args = parser.parse_args()
    try:
        asyncio.run(run_client(args.host, args.port))
    except KeyboardInterrupt:
        print("\nClient shutdown.")


if __name__ == "__main__":
    main()