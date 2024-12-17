from abc import ABC, abstractmethod
from ItemServer import ItemProtocol, ItemServer
from ScryptPasswordDB import ScryptPasswordDB
from HTTPResponse import HTTPResponse
from SimpleHTTPFactory import SimpleHTTPFactory
from SessionHandler import SessionHandler
from twisted.web.server import Site, NOT_DONE_YET, Session
from twisted.web.resource import Resource
from twisted.web.http import Request
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import SSL4ClientEndpoint, connectProtocol
from twisted.internet.protocol import Protocol
from twisted.internet import reactor, endpoints, ssl
from twisted.web.util import redirectTo
import urllib.parse
import html
import base64

HTTP_PORT = 80
ITEM_SERVER_HTTPS_PORT = 1931
SESSION_ID_KEY = b"session_id"
AUTH_SERVER_URL = "https://localhost:3191/test_auth/"

class SecureResource(Resource, ABC):
    def __init__(self, auth_server_url: str):
        assert isinstance(auth_server_url, str)
        self._auth_server_url = auth_server_url

    def _verify_session(self, request: Request) -> Deferred:
        ''' Query the authentication server endpoint and
        attempt to authenticate the current session.

        If the client doesn't currently have a session token,
        the authentication server will provide it upon verification
        through a set cookie header.

        If the client has a session token, the authentication server
        will resend the session token.

        If verification fails, no bytes will be returned.
        '''
        # Query the item server to perform a recursive search
        api_url = AUTH_SERVER_URL
        d = self._promise_http(api_url, debug=True)
        return d

    def _promise_http(self, url: str, debug: bool=False) -> Deferred:
            ''' Issue an http request to the ItemServer endpoint 
                using the given url.'''
            d = Deferred()

            # Get relevant information from the url
            parsed = urllib.parse.urlparse(url)
            scheme = parsed.scheme
            host = parsed.netloc
            path = parsed.path
            query = parsed.query
            port = ITEM_SERVER_HTTPS_PORT

            if len(path) == 0:
                path = "/"

            # Remove the port from the netloc to prevent
            # dns lookup errors.
            if len(host.split(":")) == 2:
                host, port = host.split(":")

            # Allow factory to bridge between main code and the reactor loop.
            # The bridge is primarily through callbacks and errbacks added
            # to the deferred at runtime.
            if len(query) == 0:
                factory = SimpleHTTPFactory(d, url, scheme, host, path, debug, None)

            else:
                factory = SimpleHTTPFactory(d, url, scheme, host, path, debug, query)

            # Connect to the appropriate port.
            # Upon connection, the factory will delegate work
            # to its protocol and return results through deferred.
            if scheme == "http":
                reactor.connectTCP(host, HTTP_PORT, factory)

            elif scheme == "https":
                reactor.connectSSL(host, port, factory, ssl.ClientContextFactory())

            return d

class LoginPage(SecureResource):
    def _generate_login_forms(self):
        ''' Generate html for login page.
        Will include basic username and password
        fields.'''
        
        html = '''<form method="POST">
                    <div>
                        <input type="text" name="username" placeholder="username"/>
                    </div>
                    <div>
                        <input type="text" name="password" placeholder="password"/>
                    </div>
                        <button type="submit">Login</button>
                    </div>
                </form>'''
        return bytes(html, "utf-8")

    def render_GET(self, request):
        ''' Allow the client to input their username
            and password.'''
        return (b"<!DOCTYPE html><html><head><meta charset='utf-8'>" + \
                b"<title></title></head><body>" + \
                self._generate_login_forms())

    def render_POST(self, request):
        ''' Receive the username and password.
            Attempt to authenticate with the given parameters.
            If a match is made, redirect them to the main page.'''
        # Receive login parameters
        username = request.args[b"username"][0].decode("utf-8")
        username = html.escape(username)
        password = request.args[b"password"][0].decode("utf-8")
        password = html.escape(password)
        print(username, password)

        # Verify that the parameters are correct.
        # If so, add the session id to our handler.
        mutable = []
        d = self._verify_session(request)
        d.addCallback(lambda data,)

        return redirectTo(b"home", request)
        # else:
        # return redirectTo(b"login", request)

class HomePage(SecureResource):
    def _generate_link(self, link_text: str, redirect: str):
        assert isinstance(link_text, str)
        assert isinstance(redirect, str)
        return f'''<a href="{redirect}">{link_text}</a>'''

    def render_GET(self, request):
        '''Allow user to navigate between search and data addition.'''
        if self._verify_session(request.getSession()):
            return f'''<!DOCTYPE html>
                            <html>
                                <head>
                                    <meta charset='utf-8'>
                                    <title>
                                    </title>
                                </head>
                                <body>
                                    <div>
                                        {self._generate_link("Search", "/search")}
                                    </div>
                                    <div>
                                        {self._generate_link("Edit database", "/edit_database")}
                                    </div>
                                    <div>
                                        {self._generate_link("Login", "/login")}
                                    </div>
                                </body>
                            </html>'''.encode("utf-8")

class SearchPage(SecureResource):
    def render_GET(self, request):
        ''' Allow the user to input information
            into a search bar to perform
            a recursive grep search.

            For all items returned in the search page,
            table them and display hyperlinks to each page.'''

        if self._verify_session(request.getSession()):
            # If any query paramaters are provided in the
            # url, perform a search using those values.
            try:
                search_query = request.args[b"search"][0].decode("utf-8")
                search_query = html.escape(search_query)

            except:
                to_render = f'''<!DOCTYPE HTML>
                                <html>
                                    <head>
                                        <meta charset='utf-8'>
                                        <title>
                                            Search
                                        </title>
                                    </head>
                                    <body>
                                        <form method="GET">
                                            <div>
                                                <input type="text" name="search" placeholder="Search..."/>
                                            </div>
                                            <div>
                                                <button type="submit"></button>
                                            </div>
                                        </form>
                                    </body>
                                </html>'''
                return to_render.encode("utf-8")

            else:

                # Query the item server to perform a recursive search
                # api_url = f"https://localhost:1931/?search={search_query}"
                # d = self._promise_http(api_url, debug=True)
                # d.addCallback(write_response)
                # return NOT_DONE_YET
                pass
            
        def _react(self, url: str, debug: bool=False):
            def display_json(data: bytes):
                print(data)

            d = self._promise_http(url, debug)
            d.addCallback(display_json)

if __name__ == "__main__":
    # Upon successful authentication, provide the user with a
    # session id.

    # Construct the web tree
    root = Resource()
    root.putChild(b"login", LoginPage(AUTH_SERVER_URL))
    root.putChild(b"home", HomePage(AUTH_SERVER_URL))
    root.putChild(b"search", SearchPage(AUTH_SERVER_URL))

    # Serve the web tree
    factory = Site(root)

    # Serve connections
    endpoint = endpoints.TCP4ServerEndpoint(reactor, HTTP_PORT)
    endpoint.listen(factory)
    reactor.run()
