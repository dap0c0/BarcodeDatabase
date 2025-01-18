from abc import ABC, abstractmethod
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol, ClientFactory
from HTTPResponse import HTTPResponse
from ItemDatabase import ItemDatabase
from twisted.internet import reactor, defer, endpoints, ssl
import ItemServer
import urllib.parse
import json
import encodings.idna

HTTP_PORT = 80
HTTPS_PORT = 443

# Too lazy to refactor simplehttp lol.
# Just gonna have a local version of simplehttp
# and change it here.
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
                 headers_dict: dict | None,
                 body: str):
        assert isinstance(factory, ClientFactory)
        assert isinstance(url, str)
        assert isinstance(host, str)
        assert isinstance(path, str) or path == None
        assert isinstance(debug, bool)
        assert isinstance(query, str) or query == None
        assert isinstance(headers_dict, dict) or headers_dict == None
        assert isinstance(body, str)
        self.factory = factory
        self.url = url
        self.scheme = scheme
        self.host = host
        self.path = path
        self.debug = debug
        self.query = query
        self.headers_dict = headers_dict
        self.body = body

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
        ''' Upon connection, send the appropriate POST request
            according to the url given.'''
        main_request = bytes(self._construct_request("POST",
                                                     self.path,
                                                     self.query,
                                                     self.http_version,
                                                     self.headers_dict,
                                                     self.body), "utf-8")
        print(f"Connection made for {json.loads(self.body)['product_id']}")
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
                           header_pairs: dict,
                           data: str):
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

        # Process the body and add
        # the content length header if necessary.
        if data != None and data != "":
            data_valid = "\r\n".join(data.strip().splitlines())
            header_pairs["Content-Length"] = str(len(data_valid.encode("utf-8")))

        # Make secondary headers if necessary
        if header_pairs:
            for key in header_pairs:
                assert isinstance(key, str)
                value = header_pairs[key]
                header_str = f"{key}: {value}\r\n"
                request += header_str

        # Add the processed
        # body of the data if provided.
        if data_valid:
            request += "\r\n"
            request += data_valid

        # breakpoint()
        return request

class SimpleHTTPFactory(ClientFactory):
    COOKIE_HEADER_KEY = "Cookie"
    def __init__(self,
                 deferred: defer.Deferred,
                 url: str,
                 scheme: str,
                 host: str,
                 path: str,
                 debug: bool,
                 query: str,
                 headers_dict: dict,
                 body: str):
        self.url = url
        self.scheme = scheme
        self.host = host
        self.path = path
        self.debug = debug
        self.query = query
        self.headers_dict = headers_dict
        self.body = body
        
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
                          self.headers_dict,
                          self.body)
        
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
class ItemClient(ABC):
    def __init__(self,
                 api_cookie: dict):
        self._api_cookie = api_cookie

    @abstractmethod
    def write_to_server(self,
                        server_endpoint_url: str):
        pass

    def _promise_http(self,
                    url: str,
                    body: str,
                    cookies_dict: dict=None,
                    headers_dict: dict=None,
                    debug: bool=False,
                    ) -> Deferred:
        ''' Issue an http request to the ItemServer endpoint 
            using the given url.

            All additional keyword args supplied are to be
            added as header pairs.

            Content length header is added automatically
            if body is provided.
            '''
        d = Deferred()

        # Get relevant information from the url
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme
        host = parsed.netloc
        path = parsed.path
        query = parsed.query

        # Set default ports before
        # checking netloc.
        if scheme == "http":
            port = HTTP_PORT

        elif scheme == "https":
            port = HTTPS_PORT

        if len(path) == 0:
            path = "/"

        # Remove the port from the netloc to prevent
        # dns lookup errors.
        if len(host.split(":")) == 2:
            host, port = host.split(":")
            port = int(port)

        # Allow factory to bridge between main code and the reactor loop.
        # The bridge is primarily through callbacks and errbacks added
        # to the deferred at runtime.
        if len(query) == 0:
            factory = SimpleHTTPFactory(d, url, scheme, host, path, debug, None, headers_dict, body)

        else:
            factory = SimpleHTTPFactory(d, url, scheme, host, path, debug, query, headers_dict, body)

        # If any cookies are supplied, add them to the
        # cookie header.
        if cookies_dict:
            for key in cookies_dict:
                factory.add_cookie(key, cookies_dict[key])

        # Connect to the appropriate port.
        # Upon connection, the factory will delegate work
        # to its protocol and return results through deferred.
        if scheme == "http":
            reactor.connectTCP(host, port, factory)

        elif scheme == "https":
            reactor.connectSSL(host, port, factory, ssl.ClientContextFactory())

        return d

class ItemClientJSON(ItemClient):
    def __init__(self,
                 json_file: str,
                 api_cookie: dict):
        ItemClient.__init__(self, api_cookie)
        self._json_file = json_file

    def _post_product(self,
                      server_endpoint_url: str,
                      product_dict: dict) -> Deferred:
        data_json = json.dumps(product_dict, indent=4)
        return self._promise_http(server_endpoint_url,
                                  data_json,
                                  cookies_dict=self._api_cookie,
                                  headers_dict={"Host": "localhost:1931",
                                                "Connection": "close"})

    def write_to_server(self,
                        server_endpoint_url: str):
        ''' Send all product data from the pre-established
        json file to the server-endpoint.'''
        db_wrapper = ItemDatabase(self._json_file)
        data_dicts = db_wrapper.get_dict()
            
        # Callback:
        # Receive the confirmation signal from the server
        # to verify that the product was actually written to it.
        # If confirmed, remove the product from our queue.
        # If not confirmed, retry posting the product.
        def verify_product(data: HTTPResponse):
            product_id = str(data)
            data_dicts.pop(product_id)

        # Callback:
        # A has been removed from our queue.
        # Continue writing to the server.
        def post_five_products():
            for i in range(5):
                react()

        # DRIVER
        def react():
            product = data_dicts.popitem()
            d = self._post_product(server_endpoint_url, product)
                                    
            d.addCallback(verify_product)

        # Begin chain of processing
        reactor.callWhenRunning(react)

    def test_write_to_server(self,
                             server_endpoint_url: str):
        db_wrapper = ItemDatabase(self._json_file)
        data_dicts = db_wrapper.get_dict()

        def post_driver(products: dict):
            item = data_dicts.popitem()
            key, data_dict = item
            data_json = json.dumps(data_dict, indent=4)

            d = self._promise_http(server_endpoint_url,
                                data_json,
                                cookies_dict=self._api_cookie,
                                headers_dict={"Host": "localhost:1931",
                                                "Connection": "close"})
            print(f"Sent {key} to {server_endpoint_url}")

            # Callback:
            # Receive the confirmation signal from the server
            # to verify that the product was actually written to it.
            # If confirmed, remove the product from our queue.
            # If not confirmed, retry posting the product.
            def verify_product(data: HTTPResponse):
                print(data)
                post_driver(data_dict)

            d.addCallback(verify_product)

        reactor.callWhenRunning(post_driver, data_dicts)
        reactor.run()

    def test_other(self, server_endpoint_url: str,
                   send_at_once: int=10):
        db_wrapper = ItemDatabase(self._json_file)
        data_dicts = db_wrapper.get_dict()

        # Add products to our queue
        def pop_products():
            i = 0

            while i < send_at_once and len(data_dicts) != 0:
                key, product = data_dicts.popitem()
                data_json = json.dumps(product, indent=4)
                d = self._promise_http(server_endpoint_url,
                                       data_json,
                                        cookies_dict=self._api_cookie,
                                        headers_dict={"Host": "localhost:1931",
                                                        "Connection": "close"})
                def foo(data):
                    print(data)

                d.addCallback(foo)
            reactor.callWhenRunning(pop_products)
        reactor.callWhenRunning(pop_products)
        
if __name__ == "__main__":
    ENDPOINT_URL = "https://localhost:1931/"
    JSON_FILE = "page_data/jan_2.json"
    api_cookie = {str(ItemServer.API_COOKIE_KEY, "utf-8"): f"{ItemServer.API_COOKIE}"}
    print(api_cookie)
    item_client = ItemClientJSON(JSON_FILE,
                                 api_cookie)

    from twisted.internet import reactor
    reactor.callWhenRunning(item_client.test_other, ENDPOINT_URL)
    reactor.run()
