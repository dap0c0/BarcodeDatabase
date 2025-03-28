from twisted.internet.protocol import Protocol, ClientFactory
from .HTTPResponse import HTTPResponse

class SimpleHTTP(Protocol):
    HTTP_VERSION = 1.1
    HTTPS_VERSION = 1.1

    def __init__(self,
                 factory: ClientFactory,
                 url: str,
                 scheme: str,
                 host: str,
                 path: str,
                 debug: bool,
                 query: str,
                 headers_dict: dict | None):
        assert isinstance(factory, ClientFactory)
        assert isinstance(url, str)
        assert isinstance(host, str)
        assert isinstance(path, str) or path == None
        assert isinstance(debug, bool)
        assert isinstance(query, str) or query == None
        assert isinstance(headers_dict, dict) or headers_dict == None
        self.factory = factory
        self.url = url
        self.scheme = scheme
        self.host = host
        self.path = path
        self.debug = debug
        self.query = query
        self.headers_dict = headers_dict

        # Get the http version
        self.http_version = None

        if scheme == "http":
            self.http_version = SimpleHTTP.HTTP_VERSION

        elif scheme == "https":
            self.http_version = SimpleHTTP.HTTPS_VERSION

        assert self.http_version != None, "HTTP version not set!"

        # Initialize message for further concatenation
        self.http = b""

    def dataReceived(self, data: bytes):
        assert len(data) != None
        self.http += data

        if self.debug:
            peer = self.transport.getPeer()
            host, port = peer.host, peer.port
            # print(f"Received {len(data)} bytes from {host}:{port}")

    def connectionMade(self):
        ''' Upon connection, send the appropriate GET request
            according to the url given.'''
        main_request = bytes(self._construct_request("GET",
                                                     self.path,
                                                     self.query,
                                                     self.http_version,
                                                     self.headers_dict), "utf-8")
        print("Connection made")
        if self.debug:
            peer = self.transport.getPeer()
            host, port = peer.host, peer.port
            print(f"Sending request {main_request} to {host}:{port}")

        self.transport.write(main_request)
        
    def connectionLost(self, reason):
        if self.debug:
            peer = self.transport.getPeer()
            host, port = peer.host, peer.port
            print(f"------------------> Completed response from {host}:{port}")

        # Wrap the http in HTTPResponse class       
        try:
            http_response = HTTPResponse(self.url,self.http)

        except Exception as e:
            self.factory.http_failed(self.url, e)

        else:
            self.factory.http_finished(http_response)

    def _construct_request(self,
                           command: str,
                           path: str,
                           query: str | None,
                           http_version: int | float,
                           header_pairs: dict):
        ''' Return string request header.'''
        assert isinstance(command, str)
        assert isinstance(path, str)
        assert isinstance(http_version, int) \
        or isinstance(http_version, float)
        assert isinstance(header_pairs, dict) or header_pairs == None

        # Make the main request header
        request = ""

        if query:
            main_header = f"{command} {path}?{query} HTTP/{http_version}\r\n"

        else:
            main_header = f"{command} {path} HTTP/{http_version}\r\n"

        request += main_header

        # Make secondary headers if necessary
        if header_pairs:
            for key in header_pairs:
                assert isinstance(key, str)
                value = header_pairs[key]
                header_str = f"{key}: {value}\r\n"
                request += header_str

        # Signal the end of the message
        request += "\r\n"
        return request

