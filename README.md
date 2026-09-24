# Socket-Store — A Mini Redis Clone in Python

A from-scratch, in-memory key-value database built with Python's `asyncio`.
It speaks a simple text protocol over TCP and is inspired by Redis — you get a
network server, a CLI client, an auto-expiring key cache, and a full test
suite, with **zero third-party runtime dependencies** (only the standard
library).

```
 +------------------+   TCP (plain text, one line per command)
 |  client.py  CLI  | <----------------------------> +----------------------+
 +------------------+                                 |  server.py (asyncio) |
 | demo.py script   |                                 |  - command parser    |
 +------------------+                                 |  - string store      |
 | your own code    |                                 |  - TTL/expiry        |
 +------------------+                                 +----------------------+
```

## Why this is a real "systems programming" project

- **Networking from scratch**: a real TCP server that accepts concurrent
  clients, no HTTP framework hiding the hard part.
- **Concurrency without threads**: one event loop handles many simultaneous
  connections using `asyncio` — the same event-loop architecture Redis uses.
- **Custom protocol design**: I defined the wire format, which forces you to
  think about framing, buffering, and client/server sync (a naive design here
  silently corrupts replies — that real bug is fixed and regression-tested).
- **Data structures**: expiry tracking uses `time.monotonic()` deadlines —
  the same lazy-expiry approach Redis uses, minus the buckets.

## Features

| Command          | Arguments                  | Description                                        |
|------------------|----------------------------|----------------------------------------------------|
| `PING`           | —                          | Round-trip check, replies `PONG`                   |
| `SET`            | `key value [EX seconds]`   | Store a value, optionally auto-expiring            |
| `GET`            | `key`                      | Read a value (`(nil)` if missing)                  |
| `DELETE`         | `key`                      | Remove a key (returns `1`/`0`)                     |
| `EXISTS`         | `key`                      | Returns `1`/`0`                                    |
| `KEYS`           | —                          | List all keys on a single line                     |
| `EXPIRE`         | `key seconds`              | Set a key's time-to-live                           |
| `TTL`            | `key`                      | Remaining seconds (`-1` none, `-2` missing)        |
| `INCR` / `DECR`  | `key`                      | Increment/decrement an integer value               |
| `FLUSH`          | —                          | Delete everything                                  |

Every command replies with **exactly one line**, so any line-reading client
stays perfectly in sync with the server.

## How to run

You need **Python 3.9+**. No `pip install` is required to run it.

**1. Start the server** (keep this window open):
```sh
python server.py
```
You'll see `Socket-Store listening on 127.0.0.1:8888`.

**2. Talk to it** (new terminal):
```sh
python client.py
```
Then type commands:
```text
> SET name Alice
OK
> GET name
Alice
> INCR visits
1
> KEYS
name visits
> exit
```

**3. Run the self-driving demo** (prints every command working — perfect for
recording a GIF):
```sh
python demo.py
```

**4. Run the tests:**
```sh
pip install -r requirements.txt
python -m pytest -q
```

## Running in Docker

```sh
docker compose up -d        # server inside a container on port 8888
python client.py            # connect from your machine
```

## Connecting from your own code

```python
import socket

s = socket.create_connection(("127.0.0.1", 8888))
s.sendall(b"SET greeting Hello World\n")
print(s.recv(1024))   # b"OK\n"
```

## The protocol (plain-text framing)

- Client sends: `COMMAND arg1 arg2\n`
- Server replies: one line, e.g. `OK`, the value, `(nil)`, or
  `ERROR: ...`, always terminated by `\n`.
- Multi-key replies (like `KEYS`) are space-separated on a single line.
  This design rule is enforced by unit tests so nobody reintroduces the
  reply-desynchronization bug.

## Configuration

Environment variables (e.g. for Docker):

| Variable | Default | Purpose        |
|----------|---------|----------------|
| `HOST`   | `127.0.0.1` | Bind address  |
| `PORT`   | `8888`   | Listen port    |

## What's inside

```
server.py      the TCP server + command parser (the "database")
client.py      interactive command-line client
demo.py        scripted end-to-end demo
test_server.py pytest suite (unit + socket-level integration tests)
Dockerfile     container image for the server
requirements.txt    only needed for running tests
```

## Design notes

- The store is a plain `dict`. Expired keys are purged lazily: the first
  command that touches a key removes it if its deadline passed.
- A single asyncio event loop never blocks, so a slow client can't freeze the
  whole server (`await writer.drain()` backpressure).
- This is an educational Redis clone, not a production datastore: data is
  volatile, there is no persistence or replication.

## Future ideas

- RESP (the real Redis wire protocol)
- `MGET`/`MSET`, `APPEND`, sorted sets
- Persistence (append-only log) and snapshotting
- A WebSocket gateway so browsers can use it