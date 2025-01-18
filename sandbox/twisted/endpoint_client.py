from twisted.internet import reactor, ssl
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import SSL4ClientEndpoint, connectProtocol

def _construct_request(command: str, path: str, query: str | None, http_version: int | float, **kargs):
    ''' Return string request header.'''
    assert isinstance(command, str)
    assert isinstance(path, str)
    assert isinstance(http_version, int) or isinstance(http_version, float)

    # Make the main request header
    request = ""

    if query:
        main_header = f"{command} {path}?{query} HTTP/{http_version}\r\n"

    else:
        main_header = f"{command} {path} HTTP/{http_version}\r\n"

    request += main_header

    # Make secondary headers
    if kargs:
        for karg in kargs:
            assert isinstance(karg, str)
            key = karg
            value = kargs[key]
            header_str = f"{key}: {value}\r\n"

            # Add the header str to the request
            request += header_str

    # Signal the end of the message
    request += "\r\n"
    return request

class Greeter(Protocol):
    def dataReceived(self, data: bytes):
        print(data)

    def sendMessage(self):
        peer = self.transport.getPeer()
        host, port = peer.host, peer.port
        print(f"Connected to {host}:{port}")

        # Send request to the server
        request = _construct_request("GET", "/", "search=oreos", 1.1, Connection="Close").encode("utf-8")
        self.transport.write(request)
        
def gotProtocol(p):
    print("got protocol")
    p.sendMessage()

point = SSL4ClientEndpoint(reactor, "localhost", 1931, ssl.ClientContextFactory())
d = connectProtocol(point, Greeter())
d.addCallback(gotProtocol)
reactor.run()
