# Py-Redis-Clone: A Simple In-Memory Key-Value Database

This project is a lightweight, in-memory key-value database built with Python's `asyncio` library. It's designed to mimic some of the basic functionalities of Redis and demonstrates fundamental concepts in networking and systems programming.

The database runs as a server that listens for TCP connections and can handle multiple clients concurrently. Clients can connect to the server to set, get, and delete key-value pairs.

## Features

*   **Asynchronous Server:** Built with `asyncio` to handle multiple clients efficiently without threads.
*   **TCP-based Communication:** Uses a simple, text-based protocol over TCP.
*   **In-Memory Storage:** All data is stored in a Python dictionary for fast access. Data is volatile and will be lost when the server is shut down.
*   **Interactive CLI Client:** A simple command-line client is provided to interact with the server.

## How to Run

1.  **Start the Server:**
    Open a terminal and run the following command. The server will start and listen on `localhost:8888`.
    ```sh
    python server.py
    ```

2.  **Start the Client:**
    Open a **new** terminal and run the client. It will automatically connect to the server.
    ```sh
    python client.py
    ```
    You will see a `> ` prompt. You can now start typing commands.

## Supported Commands

The communication protocol is text-based. Send commands as plain text, followed by a newline.

| Command         | Arguments          | Description                                             | Example                               |
|-----------------|--------------------|---------------------------------------------------------|---------------------------------------|
| `SET`           | `key value`        | Stores the value associated with the key.               | `> SET name Alice`                    |
| `GET`           | `key`              | Retrieves the value for a given key.                    | `> GET name`                          |
| `DELETE`        | `key`              | Deletes a key-value pair.                               | `> DELETE name`                       |
| `EXISTS`        | `key`              | Checks if a key exists in the database. Returns `1` or `0`. | `> EXISTS name`                       |
| `KEYS`          | (none)             | Returns a list of all keys in the database.             | `> KEYS`                              |
| `FLUSH`         | (none)             | Deletes all keys from the database.                     | `> FLUSH`                             |
| `exit` / `quit` | (none)             | Disconnects the client.                                 | `> exit`                              |

