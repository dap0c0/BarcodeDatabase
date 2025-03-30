import sys
from pymongo.errors import ServerSelectionTimeoutError
from .MongoClient import MongoClientAsync

class ConnectionVerifier():
    def __init__(self, isuri: str):
        self._client = MongoClientAsync(isuri)
        self._isuri = isuri

    def _DEFAULT_CONNECTION_ERRBACK(self, message: str):
        ''' Display message to stderr and kill process'''
        assert isinstance(message, str)
        print(message, file=sys.stderr)
        sys.exit(1)

    async def verify_connection(self):
        ''' Verify that the connection with the remote
        endpoint is valid. If not, kill process.'''
        print("Verifying connection...")
        if await self._client.connection_valid(
            ServerSelectionTimeoutError,
            lambda: self._DEFAULT_CONNECTION_ERRBACK(
                f"Connection with {self._isuri} could not be established."
                )
        ):
            print(f"Connection with {self._isuri} has been established.")

