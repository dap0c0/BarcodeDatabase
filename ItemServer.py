from ItemDatabase import ItemDatabase
from ScryptPasswordDB import ScryptPasswordDB
from SessionHandler import SessionHandler
from HTTPResponse import HTTPResponse
from SimpleHTTPFactory import SimpleHTTPFactory
from twisted.web.server import Site, Session, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web.http import Request
from twisted.internet import reactor, endpoints, ssl
from twisted.internet.defer import Deferred
from AuthServer import AuthServerCookie
import json
import html
import urllib.parse

SESSION_ID_KEY = bytes(AuthServerCookie.SESSION_COOKIE_NAME, "utf-8")
API_COOKIE_KEY = b"api_cookie_key"
API_COOKIE = "abcdefghijklmnopqrstuvwxyz"
AUTH_SERVER_URL = "https://localhost:3191/test_auth"
HTTP_PORT = 80
HTTPS_PORT = 443

class ItemProtocol(Resource):
    ''' HTTP protocol for serving items from the
        supplied item database.'''
    isLeaf = True
    ITEM_FORMAT_JSON = {"url": "",
                        "brand": "",
                        "flavor": "",
                        "weight": "",
                        "volume": "",
                        "count": "",
                        "company": "",
                        "manufacturer": "",
                        "upc": "",
                        "ean": "",
                        "asin": "",
                        "price": ""
                        }

    def __init__(self, file_path, indents=4):
        Resource.__init__(self)
        self._indents = indents
        self._item_database = ItemDatabase(file_path)

    def render_GET(self, request):
        '''Client must search through URL api as such:
        localhost:port/?search=foo+bar.

        The protocol will return all recursive grep matches
        in json format.'''
        # Callback:
        # Verify that the auth item server
        # authenticated the client.
        def check_token(http_response: HTTPResponse):
            assert len(http_response) > 0
            return str(http_response)

        # Callback:
        # The user is authenticated either through
        # an api key or their session id. Perform
        # a search with their query.
        def search_and_display(_):
            search_arg = request.args[b"search"][0].decode("utf-8")
            arg_escaped = html.escape(search_arg)
            matches = self._item_database.search_matches_iterative(arg_escaped)

            # Send back response to the client
            response = json.dumps(matches, indent=self._indents).encode("utf-8")
            request.write(response)
            request.finish()

        # Check the api key of the user
        # before session authentication
        if self._authenticate_api_key(request):
            reactor.callWhenRunning(search_and_display, None)

        else:
            d = self._verify_session(request)
            d.addCallback(check_token)
            d.addCallback(search_and_display)

        return NOT_DONE_YET

    def render_POST(self, request):
        ''' Client wants to post a new item to the
        database. Ensure that the client is an
        authenticated user.

        Client passes in a json representing the
        data of the item in the following format:
        {"<product_name>": {
            "url": "",
            "brand": "",
            "flavor": "",
            "weight": "",
            "volume": "",
            "count": "",
            "company": "",
            "manufacturer": "",
            "upc": "",
            "ean": "",
            "asin": "",
            "price": "",
        }'''
        if self._authenticate_request(request):
            # Get the data. Assure that it is json.
            # If json, ensure that it is the correct format
            # for submission of data.
            data = request.content.read().decode("utf-8")
            
            try:
                data_json = json.loads(data)

                if self._check_format_json(data_json):
                    # Get name of the item
                    product_name = list(data_json.keys())[0]

                    # Get the values of the item and
                    # write into the database
                    values_dict = data_json[product_name]
                    self._item_database.write_data(product_name=product_name,
                                                    url=values_dict["url"],
                                                    brand=values_dict["brand"],
                                                    flavor=values_dict["flavor"],
                                                    weight=values_dict["weight"],
                                                    volume=values_dict["volume"],
                                                    count=values_dict["count"],
                                                    company=values_dict["company"],
                                                    manufacturer=values_dict["manufacturer"],
                                                    upc=values_dict["upc"],
                                                    ean=values_dict["ean"],
                                                    asin=values_dict["asin"],
                                                    price=values_dict["price"])
                    return json.dumps(data_json, indent=self._indents).encode("utf-8")

            except json.decoder.JSONDecodeError:
                pass

    #------ Helper functions ---------#
    def _authenticate_api_key(self, request):
        ''' If the client provided an API key,
        authenticate it.'''
        try:
            api_key = request.getCookie(API_COOKIE_KEY).decode("utf-8")

            if api_key and api_key == API_COOKIE:
                return True

            return False

        except:
            return False

    def _verify_session(self,
                        request: Request,
                        auth_server_url=AUTH_SERVER_URL
                        ) -> Deferred:
            ''' Query the authentication server endpoint and
            attempt to authenticate the current session.

            If the client has a session token, the authentication server
            will resend the session token.

            If verification fails, no bytes will be returned.
            '''
            # Query the item server to perform a recursive search
            headers = {}
            headers["Connection"] = "close"

            # If the client has a session cookie,
            # include that in the request. In a way,
            # the front-end server acts as a proxy.
            session_id = request.getCookie(SESSION_ID_KEY)
            print(f"session_id is {session_id}")
            session_cookies = None

            if session_id:
                session_cookies = {}
                session_cookies[AuthServerCookie.SESSION_COOKIE_NAME] = str(session_id, "utf-8")

            d = self._promise_http(url=auth_server_url, cookies_dict=session_cookies, headers_dict=headers, debug=True)
            return d

    def _promise_http(self,
                      url: str,
                      cookies_dict: dict=None,
                      headers_dict: dict=None,
                      debug: bool=False
                      ) -> Deferred:
            ''' Issue an http request to the ItemServer endpoint 
                using the given url.
                         a
                All additional keyword args supplied are to be
                added as header pairs.
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
                factory = SimpleHTTPFactory(d, url, scheme, host, path, debug, None, headers_dict)

            else:
                factory = SimpleHTTPFactory(d, url, scheme, host, path, debug, query, headers_dict)

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

    def _check_format_json(self, dictionary: dict):
        ''' Check that the dictionary tables
        the same vanues as required by the
        item database.'''
        assert isinstance(dictionary, dict)
        
        # The dictionary must be tabled/keyed by the
        # product name.
        if len(dictionary) != 1:
            return False
    
        for key in dictionary:
            if not isinstance(key, str):
                return False

        # Check that all the values of dictionary follow
        # the predisclosed format of the class
        # invariant ITEM_FORMAT_JSON.
        for key in dictionary:
            if not isinstance(dictionary[key], dict):
                return False

            else:
                sub_dict = dictionary[key]

                for sub_key in sub_dict:
                    if sub_key not in ItemProtocol.ITEM_FORMAT_JSON:
                        return False
        return True

class ItemServer(object):
    DEFAULT_PORT = 1931
    def __init__(self, protocol):
        assert isinstance(protocol, ItemProtocol)
        self._protocol = protocol

    def run_https(self, cert_file, key_file, port=DEFAULT_PORT):
        '''Serve items through https at the previously
        supplied port.'''
        assert isinstance(cert_file, str)
        assert isinstance(key_file, str)
        assert isinstance(port, int)
        assert port > 0

        # Create an ssl context
        ssl_context = ssl.DefaultOpenSSLContextFactory(
            key_file,
            cert_file
        )

        # Listen to connections and serve through ssl encryption
        ssl_endpoint = endpoints.SSL4ServerEndpoint(
            reactor,
            port,
            ssl_context
        )

        # Serve items via the pre-defined protocol
        factory = Site(self._protocol)
        ssl_endpoint.listen(factory)
        reactor.run()

if __name__ == "__main__":
    item_server = ItemServer(ItemProtocol("test_file.json"))
    item_server.run_https(cert_file="crt.pem", key_file="key.pem")
