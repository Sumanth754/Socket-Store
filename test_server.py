"""Tests for the Socket-Store command layer.

Run with:
    python -m pytest -q
"""

import asyncio

import pytest

from server import DatabaseServer


@pytest.fixture()
def db() -> DatabaseServer:
    return DatabaseServer()


class TestCommandLayer:
    """Direct tests of the command handler (no sockets needed)."""

    def test_ping(self, db):
        assert db._process_command("PING") == "PONG"

    def test_set_get(self, db):
        assert db._process_command("SET name Alice") == "OK"
        assert db._process_command("GET name") == "Alice"

    def test_set_value_with_spaces(self, db):
        assert db._process_command("SET quote Hello World") == "OK"
        assert db._process_command("GET quote") == "Hello World"

    def test_get_missing_key(self, db):
        assert db._process_command("GET nope") == "(nil)"

    def test_delete_existing_then_missing(self, db):
        db._process_command("SET k v")
        assert db._process_command("DELETE k") == "1"
        assert db._process_command("DELETE k") == "0"

    def test_exists(self, db):
        db._process_command("SET k v")
        assert db._process_command("EXISTS k") == "1"
        assert db._process_command("EXISTS nope") == "0"

    def test_keys_returns_a_single_line(self, db):
        # Regression test for the old bug: KEYS used to return multiple lines,
        # which silently corrupted a line-reading client. KEYS must never
        # contain a newline.
        db._process_command("SET a 1")
        db._process_command("SET b 2")
        reply = db._process_command("KEYS")
        assert "\n" not in reply
        assert set(reply.split(" ")) == {"a", "b"}

    def test_keys_empty(self, db):
        assert db._process_command("KEYS") == "(empty)"

    def test_keys_ignores_expired_keys(self, db):
        db._process_command("SET a 1")
        db._process_command("SET b 1")
        db._expiries["b"] = 0.0  # force "b" past its deadline deterministically
        assert db._process_command("KEYS") == "a"

    def test_flush(self, db):
        db._process_command("SET a 1")
        db._process_command("SET b 2")
        assert db._process_command("FLUSH").startswith("OK")
        assert db._process_command("KEYS") == "(empty)"

    def test_expire_and_ttl(self, db):
        db._process_command("SET k v")
        assert db._process_command("EXPIRE k 10") == "1"
        ttl = int(db._process_command("TTL k"))
        assert 1 <= ttl <= 10
        assert db._process_command("TTL missing") == "-2"

    def test_expire_on_missing_key_returns_zero(self, db):
        assert db._process_command("EXPIRE nope 10") == "0"

    def test_incr_decr(self, db):
        assert db._process_command("INCR counter") == "1"
        assert db._process_command("INCR counter") == "2"
        assert db._process_command("DECR counter") == "1"
        assert db._process_command("GET counter") == "1"

    def test_incr_non_integer_value(self, db):
        db._process_command("SET k abc")
        assert "not an integer" in db._process_command("INCR k")

    def test_unknown_command(self, db):
        assert db._process_command("BADCMD") == "ERROR: Unknown command 'BADCMD'"

    def test_empty_command(self, db):
        assert db._process_command("") == "ERROR: Empty command"


class TestEndpoint:
    """Tests that spin up a real server and talk to it over a socket."""

    def test_full_session_over_socket(self):
        async def scenario():
            server_instance = DatabaseServer()
            listener = await asyncio.start_server(
                server_instance.handle_client, "127.0.0.1", 0
            )
            port = listener.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)

            async def ask(command):
                writer.write(command.encode() + b"\n")
                await writer.drain()
                return (await reader.readline()).decode().strip()

            try:
                assert await ask("SET a 1") == "OK"
                assert await ask("SET b 2") == "OK"
                assert await ask("KEYS") in ("a b", "b a")
                # Regression check: GET right after KEYS must not be shifted.
                assert await ask("GET a") == "1"
                assert await ask("GET b") == "2"
                assert await ask("EXISTS a") == "1"
                assert await ask("DELETE a") == "1"
                assert await ask("EXISTS a") == "0"
                assert await ask("PING") == "PONG"
                assert (await ask("BOGUS")).startswith("ERROR")
                assert await ask("FLUSH") != ""
            finally:
                writer.close()
                await writer.wait_closed()
                listener.close()
                await listener.wait_closed()

        asyncio.run(scenario())

    def test_values_longer_than_1024_bytes(self):
        async def scenario():
            server_instance = DatabaseServer()
            listener = await asyncio.start_server(
                server_instance.handle_client, "127.0.0.1", 0
            )
            port = listener.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)

            async def ask(command):
                writer.write(command.encode() + b"\n")
                await writer.drain()
                return (await reader.readline()).decode().strip()

            try:
                big = "x" * 3000
                assert await ask(f"SET big {big}") == "OK"
                assert await ask("GET big") == big
            finally:
                writer.close()
                await writer.wait_closed()
                listener.close()
                await listener.wait_closed()

        asyncio.run(scenario())

    def test_expiry_actually_expires(self):
        async def scenario():
            server_instance = DatabaseServer()
            listener = await asyncio.start_server(
                server_instance.handle_client, "127.0.0.1", 0
            )
            port = listener.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)

            async def ask(command):
                writer.write(command.encode() + b"\n")
                await writer.drain()
                return (await reader.readline()).decode().strip()

            try:
                assert await ask("SET temp hello EX 1") == "OK"
                assert await ask("GET temp") == "hello"
                await asyncio.sleep(1.2)
                assert await ask("GET temp") == "(nil)"
                assert await ask("EXISTS temp") == "0"
            finally:
                writer.close()
                await writer.wait_closed()
                listener.close()
                await listener.wait_closed()

        asyncio.run(scenario())


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-q", __file__]))