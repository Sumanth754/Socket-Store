"""Socket-Store — a tiny Redis-style in-memory key-value server built on Python asyncio.

The protocol is deliberately simple: every command is one line of text ending
with a newline, and every command produces exactly ONE response line. This rule
is what keeps a naive line-reading client perfectly in sync with the server.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class DatabaseServer:
    """TCP server hosting an in-memory key-value store (a mini Redis clone)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8888) -> None:
        self._host = host
        self._port = port
        self._data_store: Dict[str, str] = {}
        self._expiries: Dict[str, float] = {}
        self._server: Optional[asyncio.AbstractServer] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _purge_if_expired(self, key: str) -> None:
        """Delete a key (and its TTL) when its time-to-live has lapsed."""
        expires_at = self._expiries.get(key)
        if expires_at is not None and time.monotonic() > expires_at:
            self._data_store.pop(key, None)
            self._expiries.pop(key, None)

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Serve one client connection until it disconnects."""
        addr = writer.get_extra_info("peername")
        logging.info("Client connected: %s", addr)
        try:
            while True:
                # readline() reads until a newline, so there is no 1024-byte
                # truncation problem with long values.
                raw = await reader.readline()
                if not raw:  # client closed the connection
                    break
                message = raw.decode().strip()
                if not message:
                    continue
                logging.info("Received from %s: %s", addr, message)
                response = self._process_command(message)
                writer.write(response.encode() + b"\n")
                await writer.drain()
        except asyncio.CancelledError:
            logging.info("Connection with %s cancelled.", addr)
        except Exception as exc:  # noqa: BLE001 - never let one client kill the server
            logging.error("Error with client %s: %s", addr, exc)
        finally:
            logging.info("Client disconnected: %s", addr)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Command layer
    # ------------------------------------------------------------------

    def _process_command(self, command_str: str) -> str:
        """Parse and execute one command, returning its single-line reply."""
        parts = command_str.split()
        if not parts:
            return "ERROR: Empty command"

        command = parts[0].upper()
        args = parts[1:]

        if command == "PING":
            return "PONG"

        if command == "SET":
            return self._cmd_set(args)

        if command == "GET":
            if len(args) != 1:
                return "ERROR: GET requires a key"
            key = args[0]
            self._purge_if_expired(key)
            return self._data_store.get(key, "(nil)")

        if command == "DELETE":
            if len(args) != 1:
                return "ERROR: DELETE requires a key"
            key = args[0]
            self._purge_if_expired(key)
            if self._data_store.pop(key, None) is not None:
                self._expiries.pop(key, None)
                return "1"
            return "0"

        if command == "EXISTS":
            if len(args) != 1:
                return "ERROR: EXISTS requires a key"
            key = args[0]
            self._purge_if_expired(key)
            return "1" if key in self._data_store else "0"

        if command == "KEYS":
            if args:
                return "ERROR: KEYS takes no arguments"
            for key in list(self._data_store):
                self._purge_if_expired(key)
            if not self._data_store:
                return "(empty)"
            # One single line, space separated — this fixes the old bug where
            # multi-line replies desynchronized a line-reading client.
            return " ".join(self._data_store.keys())

        if command == "FLUSH":
            if args:
                return "ERROR: FLUSH takes no arguments"
            count = len(self._data_store)
            self._data_store.clear()
            self._expiries.clear()
            return f"OK (flushed {count} keys)"

        if command == "EXPIRE":
            return self._cmd_expire(args)

        if command == "TTL":
            if len(args) != 1:
                return "ERROR: TTL requires a key"
            key = args[0]
            self._purge_if_expired(key)
            if key not in self._data_store:
                return "-2"  # key does not exist
            expires_at = self._expiries.get(key)
            if expires_at is None:
                return "-1"  # key exists, no expiry
            return str(max(1, int(expires_at - time.monotonic())))

        if command in ("INCR", "DECR"):
            return self._cmd_incr_decr(command, args)

        return f"ERROR: Unknown command '{command}'"

    def _cmd_set(self, args: List[str]) -> str:
        if len(args) < 2:
            return "ERROR: SET requires a key and a value"
        key = args[0]
        ex_seconds: Optional[float] = None
        # Optional trailing clause:  SET <key> <value> EX <seconds>
        if len(args) >= 4 and args[-2].upper() == "EX":
            try:
                ex_seconds = float(args[-1])
            except ValueError:
                return "ERROR: EX requires a numeric value"
            value = " ".join(args[1:-2])
        else:
            value = " ".join(args[1:])
        self._data_store[key] = value
        if ex_seconds is not None:
            self._expiries[key] = time.monotonic() + ex_seconds
        else:
            self._expiries.pop(key, None)
        return "OK"

    def _cmd_expire(self, args: List[str]) -> str:
        if len(args) != 2:
            return "ERROR: EXPIRE requires a key and seconds"
        key, seconds = args[0], args[1]
        try:
            seconds = float(seconds)
        except ValueError:
            return "ERROR: EXPIRE requires a numeric value in seconds"
        self._purge_if_expired(key)
        if key not in self._data_store:
            return "0"
        self._expiries[key] = time.monotonic() + max(0.0, seconds)
        return "1"

    def _cmd_incr_decr(self, command: str, args: List[str]) -> str:
        if len(args) != 1:
            return f"ERROR: {command} requires a key"
        key = args[0]
        self._purge_if_expired(key)
        current = self._data_store.get(key, "0")
        try:
            number = int(current)
        except ValueError:
            return f"ERROR: value for key '{key}' is not an integer"
        number += 1 if command == "INCR" else -1
        self._data_store[key] = str(number)
        return str(number)

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self.handle_client, self._host, self._port
        )
        addr = self._server.sockets[0].getsockname()
        logging.info("Socket-Store listening on %s:%s", addr[0], addr[1])
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            logging.info("Socket-Store stopped.")


async def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8888"))
    server = DatabaseServer(host=host, port=port)
    try:
        await server.start()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())