import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DatabaseServer:
    """
    The core server for the in-memory key-value database.
    """
    def __init__(self, host='127.0.0.1', port=8888):
        self._host = host
        self._port = port
        self._data_store = {}
        self._server = None

    async def handle_client(self, reader, writer):
        """
        Coroutine to handle a single client connection.
        """
        addr = writer.get_extra_info('peername')
        logging.info(f"Client connected: {addr}")
        
        try:
            while True:
                # Read data from the client
                data = await reader.read(1024)
                if not data:
                    break
                
                message = data.decode().strip()
                logging.info(f"Received from {addr}: {message}")

                # Process command and get response
                response = self._process_command(message)
                
                # Send response back to the client
                writer.write(response.encode() + b'\n')
                await writer.drain()

        except asyncio.CancelledError:
            logging.info(f"Connection with {addr} cancelled.")
        except Exception as e:
            logging.error(f"Error with client {addr}: {e}")
        finally:
            logging.info(f"Client disconnected: {addr}")
            writer.close()
            await writer.wait_closed()

    def _process_command(self, command_str):
        """
        Parses and executes a command, returning the result.
        """
        parts = command_str.split()
        if not parts:
            return "ERROR: Empty command"
            
        command = parts[0].upper()
        args = parts[1:]

        try:
            if command == 'SET':
                if len(args) < 2:
                    return "ERROR: SET requires a key and a value"
                key = args[0]
                value = ' '.join(args[1:])
                self._data_store[key] = value
                return "OK"

            elif command == 'GET':
                if len(args) != 1:
                    return "ERROR: GET requires a key"
                key = args[0]
                return self._data_store.get(key, "(nil)")

            elif command == 'DELETE':
                if len(args) != 1:
                    return "ERROR: DELETE requires a key"
                key = args[0]
                if key in self._data_store:
                    del self._data_store[key]
                    return "1"  # Success
                return "0"  # Key not found

            elif command == 'EXISTS':
                if len(args) != 1:
                    return "ERROR: EXISTS requires a key"
                key = args[0]
                return "1" if key in self._data_store else "0"

            elif command == 'KEYS':
                if len(args) != 0:
                    return "ERROR: KEYS takes no arguments"
                if not self._data_store:
                    return "(empty list)"
                return '\n'.join(self._data_store.keys())

            elif command == 'FLUSH':
                if len(args) != 0:
                    return "ERROR: FLUSH takes no arguments"
                count = len(self._data_store)
                self._data_store.clear()
                return f"OK (flushed {count} keys)"

            else:
                return f"ERROR: Unknown command '{command}'"
        except Exception as e:
            return f"ERROR: An internal error occurred: {e}"

    async def start(self):
        """
        Starts the TCP server.
        """
        self._server = await asyncio.start_server(
            self.handle_client, self._host, self._port)
        
        addr = self._server.sockets[0].getsockname()
        logging.info(f"Server started on {addr}")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        """
        Stops the server gracefully.
        """
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logging.info("Server has been stopped.")

async def main():
    server = DatabaseServer()
    try:
        await server.start()
    except KeyboardInterrupt:
        logging.info("Server shutting down...")
    finally:
        await server.stop()

if __name__ == '__main__':
    asyncio.run(main())
