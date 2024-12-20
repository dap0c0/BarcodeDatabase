from abc import ABC, abstractmethod
from ItemServer import ItemProtocol, ItemServer
from ScryptPasswordDB import ScryptPasswordDB
from HTTPResponse import HTTPResponse
from SimpleHTTPFactory import SimpleHTTPFactory
from AuthServer import AuthServerCookie
from SessionHandler import SessionHandler
from twisted.web.server import Site, NOT_DONE_YET, Session
from twisted.python.components import registerAdapter
from zope.interface import Interface, Attribute, implementer
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

#----- Cookie persistence -------#
class ICookie(Interface):
    value = Attribute("A string value that persists per session")

@implementer(ICookie)
class Cookie(object):
    def __init__(self, session):
        self.value = None

# Allow cookie values to persist across sessions.
registerAdapter(Cookie, Session, ICookie)

class SecureResource(Resource, ABC):
    def __init__(self, auth_server_url: str):
        assert isinstance(auth_server_url, str)
        self._auth_server_url = auth_server_url

    def _verify_session(self,
                        request: Request,
                        username: str=None,
                        password: str=None,
                        auth_server_url=AUTH_SERVER_URL
                        ) -> Deferred:
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
        headers = {}
        headers["Connection"] = "close"

        # If the client has a session cookie,
        # include that in the request. In a way,
        # the front-end server acts as a proxy.
        session = request.getSession()
        session_id = ICookie(session).value
        session_cookies = None

        if session_id != None:
            session_cookies = {}
            session_cookies[AuthServerCookie.SESSION_COOKIE_NAME] = session_id

        if username and password:
            auth_b64 = self._generate_auth_basic(username, password)
            headers["Authorization"] = f"Basic {auth_b64}"

        d = self._promise_http(url=auth_server_url, cookies_dict=session_cookies, headers_dict=headers, debug=True)
        return d

    def _generate_auth_basic(self,
                             username: str,
                             password: str) -> str:
        ''' Generate the base64 token of
        "<username>:<password>"'''
        assert isinstance(username, str)
        assert isinstance(password, str)
        temp = f"{username}:{password}"
        return base64.b64encode(bytes(temp, "utf-8")).decode("utf-8")

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
            port = ITEM_SERVER_HTTPS_PORT

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
        
        # Callback:
        # display content of response for debugging.
        # If the auth server's response is empty,
        # authentication failed.
        def print_response(http_response: HTTPResponse):
            reactor.callWhenRunning(print, f"Response is {http_response}")
            assert len(http_response) > 0
            return str(http_response) # Push the content of the response

        # Callback:
        # Authentication has passed! Set the token
        # as session_id for the client.
        def set_session_cookie(token: str):
            assert isinstance(token, str)
            assert len(token) > 0
            print(f"Setting session cookie as {token}")
            session = request.getSession()
            ICookie(session).value = token
            print(f"Cookies: {ICookie(request.getSession()).value}")

        # Callback:
        # Redirect the client to the home page.
        def redirect_home(data: object):
            request.redirect(url="http://localhost/home")
            request.finish()

        # Errback:
        # authentication has failed! Redirect the client
        # to the login page.
        def redirect_login(err):
            print(f"Redirecting login!")
            request.redirect(url="http://localhost/login")
            request.finish()
            
        # Verify that the parameters are correct.
        # If so, add the session id to our handler.
        d = self._verify_session(request, username, password)
        d.addCallback(print_response)
        d.addCallback(set_session_cookie)
        d.addCallback(redirect_home)
        d.addErrback(redirect_login)
        return NOT_DONE_YET

class HomePage(SecureResource):
    def _generate_link(self, link_text: str, redirect: str):
        assert isinstance(link_text, str)
        assert isinstance(redirect, str)
        return f'''<a href="{redirect}">{link_text}</a>'''

    def render_GET(self, request):
        '''Allow user to navigate between search and data addition.'''
        d = self._verify_session(request)

        # Callback:
        # display content of response for debugging.
        # If the auth server's response is empty,
        # authentication failed.
        def print_response(http_response: HTTPResponse):
            reactor.callWhenRunning(print, f"Response is {http_response}")
            assert len(http_response) > 0
            return str(http_response) # Push the content of the response

        # Callback:
        # Token has been authenticated! Display the
        # page html to the client.
        def render_page(data: str):
            request.write(f'''<!DOCTYPE html>
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
                            </html>'''.encode("utf-8"))
            request.finish()

        # Errback:
        # authentication has failed! Redirect the client
        # to the login page.
        def redirect_login(err):
            print(f"Redirecting login!")
            request.redirect(url="http://localhost/login")
            request.finish()

        d.addCallback(print_response)
        d.addCallback(render_page)
        d.addErrback(redirect_login)
        return NOT_DONE_YET

class BarcodeBruteforcerPage(SecureResource):
    def _generate_html(self):
        to_render = f'''<!DOCTYPE HTML>
                        <html>
                            <head>
                                <meta charset='utf-8'>
                                <title>
                                    Search
                                </title>
                            </head>
                            <body>
                                <form method="POST">
                                    <div>
                                        <input type="text" name="upc_barcode" placeholder="UPC Barcode..."/>
                                    </div>
                                    <div>
                                        <button type="submit"></button>
                                    </div>
                                </form>
                            </body>
                        </html>'''
        return to_render

    def render_GET(self, request: Request):
        ''' Allow the user to input a UPC barcode (12 digits),
        with an x signifying a missing digit.'''

        # Callback
        # Check that the token is valid.
        # The auth server echoes the token
        # if the client is authenticated.
        def check_token(http_response: HTTPResponse):
            assert len(http_response) > 0
            return str(http_response)

        # Callback
        # Display the page to the user!
        def render_page(_):
            html = self._generate_html()
            request.write(html.encode("utf-8"))
            request.finish()

        # Errback
        # The client isn't authenticated!
        # Redirect them to the login page
        def redirect_login(err):
            print(f"Redirecting login!")
            request.redirect(url="http://localhost/login")
            request.finish()
            
        d = self._verify_session(request)
        d.addCallback(check_token)
        d.addCallbacks(render_page, redirect_login)
        return NOT_DONE_YET
        
   def render_POST(self, request: Request):
        ''' With the inputted UPC barcode (11 digits with x),
        dynamically generate all barcodes and display on the page.'''


        # Callback
        # Check that the token is valid.
        # The auth server echoes the token
        # if the client is authenticated.
        def check_token(http_response: HTTPResponse):
            assert len(http_response) > 0
            return str(http_response)

        # Callback
        # Display the page to the user!
        def render_page(_):
            html = self._generate_html()
            request.write(html.encode("utf-8"))
            request.finish()

        # Errback
        # The client isn't authenticated!
        # Redirect them to the login page
        def redirect_login(err):
            print(f"Redirecting login!")
            request.redirect(url="http://localhost/login")
            request.finish()

        d = self._verify_session(request)
        d.addCallback(check_token)
        d.addCallbacks(render_page, redirect_login)
        return NOT_DONE_YET
        
 
class SearchPage(SecureResource):
    def render_GET(self, request: Request):
        ''' Allow the user to input information
            into a search bar to perform
            a recursive grep search.

            For all items returned in the search page,
            table them and display hyperlinks to each page.'''


        # Callback:
        # Display content of response for debugging.
        # If the auth server's response is empty,
        # authentication failed.
        def print_response(http_response: HTTPResponse):
            reactor.callWhenRunning(print, f"Response is {http_response}")
            assert len(http_response) > 0
            return str(http_response) # Push the content of the response

        # Errback:
        # Authentication has failed! Redirect the client
        # to the login page.
        def redirect_login(err):
            print(f"Redirecting login!")
            request.redirect(url="http://localhost/login")
            request.finish()

        # Callback:
        # Check whether there was a query sent
        # in the request.
        def check_query(http_response: HTTPResponse):
            search_query = request.args[b"search"][0].decode("utf-8")
            search_query = html.escape(search_query)
            return search_query

        # Errback:
        # Token has been authenticated! Display the
        # page html to the client.
        def render_page(_):
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
            request.write(to_render.encode("utf-8"))
            request.finish()

        # Callback:
        # Query the item server to perform a recursive search
        def search_database(search_query: str):
            def display_json(http_response: HTTPResponse):
                request.write(bytes(http_response.content, "utf-8"))
                request.finish()

            print(f"Search query: {search_query}")

            if search_query != None:
                api_url = f"https://localhost:1931/?search={search_query}"
                headers = {}
                headers["Connection"] = "close"
                d = self._promise_http(api_url, headers_dict=headers, debug=True)
                d.addCallback(display_json)

        d = self._verify_session(request)
        d.addCallback(print_response)
        d.addCallbacks(check_query, redirect_login)
        d.addCallbacks(search_database, render_page)
        return NOT_DONE_YET

if __name__ == "__main__":
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
