import asyncio
import sys

async def client(host='127.0.0.1', port=8888):
    """
    An interactive CLI client to connect to the DatabaseServer.
    """
    try:
        reader, writer = await asyncio.open_connection(host, port)
        print(f"Connected to the database server at {host}:{port}")
        print("Type 'exit' or 'quit' to close the client.")
    except ConnectionRefusedError:
        print(f"Connection refused. Is the server running at {host}:{port}?")
        return

    try:
        while True:
            # Use run_in_executor to avoid blocking the event loop with input()
            loop = asyncio.get_running_loop()
            try:
                command = await loop.run_in_executor(
                    None, sys.stdin.readline)
            except RuntimeError: # Catch RuntimeError if stdin is closed unexpectedly
                break
                
            command = command.strip()

            if not command:
                continue
            
            if command.lower() in ['exit', 'quit']:
                break

            # Send the command to the server
            writer.write(command.encode() + b'\n')
            await writer.drain()

            # Read the response
            response = await reader.readline()
            print(response.decode().strip().replace('\n', '\n'))

    except (asyncio.IncompleteReadError, ConnectionResetError):
        print("Connection to the server was lost.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Closing the connection.")
        writer.close()
        await writer.wait_closed()

if __name__ == '__main__':
    try:
        asyncio.run(client())
    except KeyboardInterrupt:
        print("\nClient shutdown.")
