from ItemServer import ItemProtocol, ItemServer
from ScryptPasswordDB import ScryptPasswordDB
from HTTPResponse import HTTPResponse
from SimpleHTTPFactory import SimpleHTTPFactory
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
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

class LoginPage(Resource):
    def __init__(self, authenticator: LoginAuthenticator):
        assert isinstance(authenticator, LoginAuthenticator)
        self._authenticator = authenticator

    def generate_login_forms(self):
        html = "<form method=\"POST\">\n" + \
                    "<div>\n" + \
                        "<input type=\"text\" name=\"username\" placeholder=\"username\"/>\n" + \
                    "</div>\n" + \
                    "<div>\n" + \
                        "<input type=\"text\" name=\"password\" placeholder=\"password\"/>\n" + \
                    "</div>\n" + \
                        "<button type=\"submit\">Login</button>" + \
                    "</div>\n" + \
                "</form>"
        return bytes(html, "utf-8")

    def render_GET(self, request):
        ''' Allow the client to input their username
            and password.'''
        return (b"<!DOCTYPE html><html><head><meta charset='utf-8'>" + \
                b"<title></title></head><body>" + \
                self.generate_login_forms())

    def render_POST(self, request):
        ''' Receive the username and password.
            Attempt to authenticate with the given parameters.
            If a match is made, redirect them to the main page.'''
        # Receive login parameters
        username = request.args[b"username"][0].decode("utf-8")
        username = html.escape(username)
        password = request.args[b"password"][0].decode("utf-8")
        password = html.escape(password)

        # Verify that the parameters are correct
        if self._authenticator.authenticate_params(username, password):
            return redirectTo(b"home", request)
        
        else:
            return redirectTo(b"login", request)

class HomePage(Resource):
    def __init__(self):
        # TODO:
        # - need to add some form of session authentication
        # for users.
        pass

    def _generate_link(self, link_text: str, redirect: str):
        assert isinstance(link_text, str)
        assert isinstance(redirect, str)
        return f'''<a href="{redirect}">{link_text}</a>'''

    def render_GET(self, request):
        '''Allow user to navigate between search and data addition.'''
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

class SearchPage(Resource):
    def render_GET(self, request):
        ''' Allow the user to input information
            into a search bar to perform
            a recursive grep search.

            For all items returned in the search page,
            table them and display hyperlinks to each page.'''

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

            def write_response(data: HTTPResponse):
                ''' Upon receiving the response, return it
                to the transport.'''
                request.write(data.content.encode("utf-8"))
                request.finish()

            # Query the item server to perform a recursive search
            api_url = f"https://localhost:1931/?search={search_query}"
            d = self._promise_http(api_url, debug=True)
            d.addCallback(write_response)
            return NOT_DONE_YET
        
    def _react(self, url: str, debug: bool=False):
        def display_json(data: bytes):
            print(data)

        d = self._promise_http(url, debug)
        d.addCallback(display_json)

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

        if len(path) == 0:
            path = "/"

        # Remove the port from the netloc to prevent
        # dns lookup errors.
        if len(host.split(":")) == 2:
            host, _ = host.split(":")

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
            reactor.connectSSL(host, ITEM_SERVER_HTTPS_PORT, factory, ssl.ClientContextFactory())

        return d

# Create the resource
root = Resource()
root.putChild(b"login", LoginPage(LoginAuthenticator(ScryptPasswordDB())))
root.putChild(b"home", HomePage())
root.putChild(b"search", SearchPage())

# Serve the web tree
factory = Site(root)

# Serve connections
endpoint = endpoints.TCP4ServerEndpoint(reactor, HTTP_PORT)
endpoint.listen(factory)
reactor.run()
