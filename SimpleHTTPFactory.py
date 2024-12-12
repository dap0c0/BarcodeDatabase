from twisted.internet.protocol import ClientFactory
from SimpleHTTP import SimpleHTTP
from twisted.internet import defer
from HTTPResponse import HTTPResponse

class SimpleHTTPFactory(ClientFactory):
    def __init__(self, deferred: defer.Deferred, url: str, scheme: str, 
                 host: str, path: str, debug: bool, query: str | None):
        self.scheme = scheme
        self.url = url
        self.host = host
        self.path = path
        self.debug = debug
        self.query = query
        
        # Allow callbacks and errbacks
        self.deferred = deferred

        print("Factory built")

    def buildProtocol(self, addr):
        return SimpleHTTP(self, self.url, self.scheme, self.host, self.path, self.debug, self.query)
        
    def http_finished(self, http_response: HTTPResponse):
        assert isinstance(http_response, HTTPResponse)
        
        if self.deferred:
            d, self.deferred = self.deferred, None
            d.callback(http_response)

    def http_failed(self, url: str, reason):
        if self.deferred:
            d, self.deferred = self.deferred, None
            d.errback((url, reason))
