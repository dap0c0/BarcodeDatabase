from twisted.internet.protocol import ClientFactory
from SimpleHTTP import SimpleHTTP
from twisted.internet import defer
from HTTPResponse import HTTPResponse

class SimpleHTTPFactory(ClientFactory):
    COOKIE_HEADER_KEY = "Cookie"
    def __init__(self,
                 deferred: defer.Deferred,
                 url: str,
                 scheme: str,
                 host: str,
                 path: str,
                 debug: bool,
                 query: str | None,
                 headers_dict: dict | None):
        self.scheme = scheme
        self.url = url
        self.host = host
        self.path = path
        self.debug = debug
        self.query = query
        self.headers_dict = headers_dict
        
        # Allow callbacks and errbacks
        self.deferred = deferred

    def buildProtocol(self, addr):
        return SimpleHTTP(self,
                          self.url,
                          self.scheme,
                          self.host,
                          self.path,
                          self.debug,
                          self.query,
                          self.headers_dict)
        
    def add_cookie(self, key: str,
                   value: str):
        '''Allow http requests to be sent with the
            supplied cookie.'''
        assert isinstance(key, str)
        assert isinstance(value, str)

        # Check if the cookie header is set yet
        chk = SimpleHTTPFactory.COOKIE_HEADER_KEY

        if chk not in self.headers_dict:
            self.headers_dict[chk] = f"{key}={value}"

        # At least one cookie exists!
        # Add the text appropriately.
        else:
            self.headers_dict[chk] += f"; {key}={value}"

    def http_finished(self, http_response: HTTPResponse):
        assert isinstance(http_response, HTTPResponse)
        
        if self.deferred:
            d, self.deferred = self.deferred, None
            d.callback(http_response)

    def http_failed(self, url: str, reason):
        if self.deferred:
            d, self.deferred = self.deferred, None
            d.errback((url, reason))
