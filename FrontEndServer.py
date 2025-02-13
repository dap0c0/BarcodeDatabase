from abc import ABC, abstractmethod
from MongoClient import MongoClientSync
from HTTPResponse import HTTPResponse
from SimpleHTTPFactory import SimpleHTTPFactory
from AuthServer import AuthServerCookie
from BarcodeGenerator import UPCBarcodeGenerator
from PatternExtractor import PatternExtractor
from twisted.web.server import Site, NOT_DONE_YET, Session
from twisted.python.components import registerAdapter
from zope.interface import Interface, Attribute, implementer
from twisted.web.resource import Resource
from twisted.web.http import Request
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.internet import reactor, endpoints, ssl
from Globals import GROCERY_NAME, HOME_BEAUTY_BABY_NAME, JF_NAME, today
from assets import fonts, colours
from pymongo.errors import OperationFailure
import argparse
import urllib.parse
import html
import base64
import io
import json
import re

HTTP_PORT = 80
ITEM_SERVER_HTTPS_PORT = 1931
SESSION_ID_KEY = AuthServerCookie.SESSION_COOKIE_NAME
AUTH_SERVER_URL = "https://auth_server:3191/test_auth/"

#----- Cookie persistence -------#
class ICookie(Interface):
    value = Attribute("A string value that persists per session")

@implementer(ICookie)
class Cookie(object):
    def __init__(self, session):
        self.value = None

# Allow cookie values to persist across sessions.
registerAdapter(Cookie, Session, ICookie)

class HTTPResource(Resource, ABC):
    def _generate_link(self, link_text: str, redirect: str):
        assert isinstance(link_text, str)
        assert isinstance(redirect, str)
        return f'''<a href="{redirect}">{link_text}</a>'''

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

            # Set default ports before checking netloc
            if scheme == "http":
                port = 80

            elif scheme == "https":
                port = 443

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

class SecureResource(HTTPResource, ABC):
    ''' Limit access to the resource based on the
    auth server.'''
    def __init__(self, auth_server_url: str):
        assert isinstance(auth_server_url, str)
        self._auth_server_url = auth_server_url

    # Authentication has failed! Redirect the client
    # to the login page.
    def redirect_login(self,
                       err,
                       request):
        request.redirect(url="/login")
        request.finish()

    def _verify_session(self,
                        request: Request,
                        username: str=None,
                        password: str=None,
                        auth_server_url: str=None,
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

        # Callback:
        # display content of response for debugging.
        # If the auth server's response is empty,
        # authentication failed.
        def print_response(http_response: HTTPResponse):
            reactor.callWhenRunning(print, f"Response is {http_response}")
            assert len(http_response) > 0
            return http_response

        d.addCallback(print_response)
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
        # Authentication has passed! Set the token
        # as session_id for the client.
        def set_session_cookie(http_response: HTTPResponse):
            token = str(http_response)
            assert isinstance(token, str)
            assert len(token) > 0
            print(f"Setting session cookie as {token}")
            session = request.getSession()
            ICookie(session).value = token
            print(f"Cookies: {ICookie(request.getSession()).value}")

        # Callback:
        # Redirect the client to the home page.
        def redirect_home(_):
            request.redirect(url="/")
            request.finish()

        # Verify that the parameters are correct.
        # If so, add the session id to our handler.
        d = self._verify_session(request, username, password, self._auth_server_url)
        d.addCallback(set_session_cookie)
        d.addCallback(redirect_home)
        d.addErrback(self.redirect_login, request=request)
        return NOT_DONE_YET

class HomePage(HTTPResource):
    # Token has been authenticated! Display the
    # page html to the client.
    def render_page(self, http_response: HTTPResponse | None, request):
        assert isinstance(http_response, HTTPResponse) or http_response == None
        request.write(f'''<!DOCTYPE html>
                        <html>
                            <head>
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                <meta charset='utf-8'>
                                <title>
                                </title>
                            </head>
                            <body>
                                <div>
                                    {self._generate_link("Search", "/search")}
                                </div>
                                <div>
                                    {self._generate_link("Barcode Bruteforcer", "/barcode_bruteforcer")}
                                </div>
                            </body>
                        </html>'''.encode("utf-8"))
        request.finish()

    def render_GET(self, request):
        '''Allow user to navigate between search and data addition.'''

        # Define the callback chain
        d = Deferred()
        d.addCallback(self.render_page, request=request)

        # Fire the callback chain off!
        d.callback(None)
        return NOT_DONE_YET

class SecureHomePage(HomePage, SecureResource):
    def render_GET(self, request):
        '''Allow user to navigate between search and data addition.'''
        d = self._verify_session(request, auth_server_url=self._auth_server_url)
        d.addCallback(self.render_page, request=request)
        d.addErrback(self.redirect_login, request=request)
        return NOT_DONE_YET

class BarcodeBruteforcerPage(HTTPResource):
    MOD_INVERSE_3_B10 = 7
    UPC_LEN = 12
    DEFAULT_MARKER = "x"

    def __init__(self):
        self._bc_generator = UPCBarcodeGenerator(50, add_checksum=False)
        self._pat_extractor = PatternExtractor()

    def calculate_checksum(self,
                           upc: str):
        assert isinstance(upc, str)
        assert len(upc) <= self.UPC_LEN
        odd_total = 0
        even_total = 0

        for i, char in enumerate(upc):
            if (i + 1) % 2 == 0 and (i + 1) != self.UPC_LEN:
                even_total += int(char)

            elif (i + 1) % 2 == 1:
                odd_total += int(char)

        c = 10 - (even_total + 3 * odd_total) % 10
        c = c % 10
        return c

    def solve_digit(self,
                    upc: str,
                    digit_marker: str) -> list:
        ''' Return all valid UPCs given a partial UPC
        of either 1 or 2 missing digits.'''
        assert isinstance(upc, str)
        assert isinstance(digit_marker, str)
        assert len(upc) == self.UPC_LEN
        assert len(digit_marker) == 1
        markers_found = 0

        for char in upc:
            if char == digit_marker:
                markers_found += 1

        assert markers_found > 0, "No markers found!"
        assert markers_found <= 2, "There cannot be more than 2 markers!"

        if markers_found == 1:
            return self.solve_digit_one(upc, digit_marker)

        else:
            return self.solve_digit_two(upc, digit_marker)

    def solve_digit_two(self,
                        upc: str,
                        digit_marker: str) -> list:
        ''' Calculate the two missing digits and return
        the list of all valid UPCs.'''
        assert isinstance(upc, str)
        assert len(upc) == self.UPC_LEN
        assert isinstance(digit_marker, str)
        
        # Allow only two markers to be present
        # to denote the missing digits.
        marker_indices = []

        # Observe that the checksum digit is derived as follows:
        # 10 - [(3 * O) + E] mod 10 = CHECKSUM
        odd_total = 0
        even_total = 0

        # Offset the indices by one.
        # Don't read from 0. Start from 1
        for i, char in enumerate(upc):
            try:
                digit = int(char)

            except ValueError:
                if char == digit_marker:
                    assert len(marker_indices) != 2

                marker_indices.append(i + 1)

            else:
                # Remember to not count the checksum digit in our total
                # of evens!
                if (i + 1) != len(upc) and (i + 1) % 2 == 0:
                    even_total += digit

                elif (i + 1) % 2 == 1:
                    odd_total += digit

        # Ensure that two missing digits were marked
        assert len(marker_indices) == 2, "Two missing digits must be marked!"

        # All checks have passed!
        # Check the indices of the marked digits.
        # From now on, E will refer to an even index chosen,
        # whereas O will refer to an odd index chosen,
        # and C will refer to the checksum index being chosen.
        valid_upcs = []
        x_i = marker_indices[0]
        y_i = marker_indices[1]
        check = lambda i: i == len(upc)
        odd = lambda i: i % 2 == 1
        even = lambda i: i % 2 == 0

        # Case 1: {O, C}
        # 10 - (E + 3O + 3x) mod 10 = C
        if (odd(x_i) and check(y_i)):
            for i in range(10):
                x = i
                c = 10 - (even_total + 3 * odd_total + 3 * i) % 10
                c = c % 10
                valid_upc = upc[:x_i - 1] + str(x) + upc[x_i: -1] + str(c)
                valid_upcs.append(valid_upc)

        # Case 2: {E, C}
        # 10 - (E + x + 3O) mod 10 = C
        elif (even(x_i) and check(y_i)):
            for i in range(10):
                x = i
                c = 10 - (even_total + i + 3 * odd_total) % 10
                c = c % 10
                valid_upc = upc[:x_i - 1] + str(x) + upc[x_i: -1] + str(c)
                valid_upcs.append(valid_upc)

        # Case 3: {E, E}
        # 10 - C - (E + 3O) mod 10 = (x + y) mod 10
        # Or: (x, y) = (i, ((10 - C - (E + 3O) mod 10) - i) mod 10)
        # for i in [0, 9].
        elif (even(x_i) and even(y_i)):
            c = int(upc[11])

            for i in range(10):
                x = i
                y = ((10 - c - (even_total + 3 * odd_total) % 10 - i)) % 10
                left_x_i = upc[:x_i - 1]
                between_x_y = upc[x_i: y_i - 1]
                right_y_i = upc[y_i:]
                valid_upc = left_x_i + str(x) + between_x_y + str(y) + right_y_i
                valid_upcs.append(valid_upc)
        
        # Case 4: {O, E}
        # 10 - C - (E + 3O) mod 10 = (x + 3y) mod 10
        # Or, (x, y) = (i, (10 - C - (E + 3O) mod 10 - 3i) mod 10)
        # for i in [0, 9]
        elif (odd(x_i) and even(y_i)):
            c = int(upc[11])

            for i in range(10):
                x = i
                y = 10 - c - (even_total + 3 * odd_total) % 10 - 3 * i
                y = y % 10

                left_x_i = upc[:x_i - 1]
                between_x_y = upc[x_i: y_i - 1]
                right_y_i = upc[y_i:]
                valid_upc = left_x_i + str(x) + between_x_y + str(y) + right_y_i
                valid_upcs.append(valid_upc)

        # Case 5: {E, O}
        # 10 - C - (E + 3O) mod 10 = (x + 3y) mod 10
        # Or, (x, y) = ((10 - C - (E + 3O) mod 10 - 3i) mod 10), i)
        # for i in [0, 9]
        elif (even(x_i) and odd(y_i)):
            c = int(upc[11])

            for i in range(10):
                y = i
                x = 10 - c - (even_total + 3 * odd_total) % 10 - 3 * i
                x = x % 10

                left_x_i = upc[:x_i - 1]
                between_x_y = upc[x_i: y_i - 1]
                right_y_i = upc[y_i:]
                valid_upc = left_x_i + str(x) + between_x_y + str(y) + right_y_i
                valid_upcs.append(valid_upc)



        # Case 5: {O, O}
        # 10 - C - (E + 3O) = 3(x + y) mod 10
        # -> 3^-1 = 7
        # -> (x + y) mod 10 = 7(10 - C - (E + 3O)) mod 10
        # Hence, (x, y) = (i, (7(10 - C - (E + 3O) mod 10 - i) mod 10)
        elif (odd(x_i) and odd(y_i)):
            c = int(upc[11])

            for i in range(10):
                x = i
                y = self.MOD_INVERSE_3_B10 * (10 - c - (even_total + 3 * odd_total) % 10) - i
                y = y % 10
                left_x_i = upc[:x_i - 1]
                between_x_y = upc[x_i: y_i - 1]
                right_y_i = upc[y_i:]
                valid_upc = left_x_i + str(x) + between_x_y + str(y) + right_y_i
                valid_upcs.append(valid_upc)

        assert len(valid_upcs) == 10, breakpoint()
        return valid_upcs

    def solve_digit_one(self,
                        upc: str,
                    digit_marker: str) -> list:
        ''' Derive the missing digit in a UPC (12 digit) code.'''
        assert isinstance(upc, str)
        assert len(upc) == self.UPC_LEN, "The barcode must be 12 digits long!"
        assert isinstance(digit_marker, str)

        # Allow only one marker to be present
        # to denote the missing digit.
        marker_index = None

        # Observe that the checksum digit is derived as follows:
        # 10 - [(3 * O) + E] mod 10 = CHECKSUM
        odd_total = 0
        even_total = 0
        
        # Offset the indices by one.
        # Don't read from 0. Start from 1.
        for i, char in enumerate(upc):
            try:
                digit = int(char)

            except ValueError:
                if char == digit_marker:
                    assert not marker_index, "There are more than 1 markers!"

                marker_index = i + 1

            else:
                # Remember to not count the checksum digit in our
                # total of evens!
                if (i + 1) != len(upc) and (i + 1) % 2 == 0:
                    even_total += digit

                elif (i + 1) % 2 == 1:
                    odd_total += digit

        # Ensure that a missing digit was marked
        assert marker_index, "No missing digit was marked!"

        # All checks have passed.
        # Case 1: the missing digit is the checksum digit!
        # Proceed with the forward calculation from the formula
        # established above. mod 10 is reapplied twice to account
        # for the possibility of 3 * odd_total + even_total already being
        # a multiple of 10, hence preventing a nonsense result of 10 - 0 = 10.
        if marker_index == len(upc):
            c = (10 - (3 * odd_total + even_total) % 10) % 10
            return [upc[:-1] + str(c)]

        # Case 2:
        # Suppose that the digit is on an odd index. The formula is:
        # 10 - [(E + 3 * O) + 3x] mod 10 = CHECKSUM
        # => [(E + 3 * O) + 3x] mod 10 = 10 - CHECKSUM
        # Try to derive the least value of x such that
        # the equation is true.
        checksum_digit = int(upc[11])

        if marker_index % 2 == 1:
            for x in range(10):
                if (((3 * odd_total + even_total) % 10) + (3 * x)) % 10 == 10 - checksum_digit:
                    return [upc[:marker_index - 1] + str(x) + upc[marker_index:]]

        # Suppose that the digit is on an even index.
        # We proceed very similarly:
        # 10 - [(E + 3 * O) + x] mod 10 = CHECKSUM
        # => [(E + 3 * O) + x] mod 10 = 10 - CHECKSUM
        # Again, try to derive the least value of x such
        # that the equation is true.
        else:
            for x in range(10):
                if (((3 * odd_total + even_total) % 10) + x) % 10 == 10 - checksum_digit:
                    return [upc[:marker_index-1] + str(x) + upc[marker_index:]]


    # Display the page to the user!
    def render_page(self, _, request):
        html = self._generate_html()
        request.write(html.encode("utf-8"))
        request.finish()

    # Display all possible barcodes on the page.
    # E.g, for 012345x23450, display the barcodes of
    # 012345023450, 012345123450, ...
    def render_barcodes_new(self, upc_barcode: str, request):
        if upc_barcode != None:
            upcs = self.solve_digit(upc_barcode, self.DEFAULT_MARKER)

            # Write all barcodes into streams
            streams = []

            for upc in upcs:
                stream = io.BytesIO()
                self._bc_generator.write(upc, stream)
                streams.append(stream)

            # Render them all onto the page
            to_render = """<!DOCTYPE HTML>
            <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <meta charset='utf-8'>
                    <title>Barcodes</title>
                    <style>
                        body {
                            display: flex;
                            flex-direction: column; /* Arrange items vertically */
                            align-items: center; /* Center align the barcodes */
                            gap: 20px; /* Add spacing between barcodes */
                            font-family: Arial, sans-serif;
                        }
                    </style>
                </head>
                <body>
            """

            for stream in streams:
                to_render += f"<div>{str(stream.getvalue(), 'utf-8')}</div>"

            to_render += """
                </body>
            </html>
            """
            request.write(to_render.encode("utf-8"))
            request.finish()

    # Verify that the client input is valid!
    # The barcode must be 12 digits total
    # (including the x).
    def check_input(self, _, request):
        def style_msg(msg: str,
                      colour: str,
                      font_family: str,
                      font_size: int):
            return f'''<pre style="color: {colour}; font-family: {font_family}; font-size: {font_size}px;">{msg}</pre>'''

        error_size = 13
        upc_barcode = request.args[b"upc_barcode"][0].decode("utf-8")
        
        # Check length of the input
        assert len(upc_barcode) == 12, \
        request.write(bytes(style_msg("The input must be 12 characters.", \
                                        colours.red, \
                                        fonts.menlo, \
                                        error_size), "utf-8"))

        # Check how many digits are marked
        one_x_pat = r"\b(?:" + \
            r"|(?:[^xX]*[xX][^xX]*)" + \
            r")\b"

        two_x_pat = r"\b(?:" + \
            r"|(?:[^xX]*[xX][^xX]*[xX][^xX]*)" + \
            r")\b"

        self._pat_extractor.set_pattern(one_x_pat)
        matches_one = self._pat_extractor.get_matches(upc_barcode)
        self._pat_extractor.set_pattern(two_x_pat)
        matches_two = self._pat_extractor.get_matches(upc_barcode)

        assert len(matches_one) != 0 or len(matches_two) != 0, \
        request.write(bytes(style_msg("Only one or two missing digits\nmust be marked with the character 'x'",
                                      colours.red,
                                      fonts.menlo,
                                      error_size), "utf-8"))

        # Verify the input charset
        valid_pattern = r"\b(?:" + \
            r"|(?:\d*[xX]\d+)" + \
            r"|(?:\d+[xX]\d*)" + \
            r"|(?:\d*[xX]\d*[xX]\d+)" + \
            r"|(?:\d+[xX]\d*[xX]\d*)" + \
            r"|(?:\d*[xX]\d+[xX]\d*)" + \
            r")\b"

        self._pat_extractor.set_pattern(valid_pattern)
        print(f"Matches: {self._pat_extractor.get_matches(upc_barcode)}")
        assert len(self._pat_extractor.get_matches(upc_barcode)) != 0, request.write(bytes(style_msg("Input pattern was invalid.", \
                                                                                                     colours.red, \
                                                                                                     fonts.menlo, \
                                                                                                     error_size), "utf-8"))

        # All checks passed! Bubble upc_barcode
        # for further processing
        return upc_barcode

    def _generate_html(self):
        to_render = f'''<!DOCTYPE HTML>
                        <html>
                            <head>
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
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

        d = Deferred()
        d.addCallback(self.render_page, request=request)
        d.callback(None)
        return NOT_DONE_YET
        
    def render_POST(self, request: Request):
        ''' With the inputted UPC barcode (11 digits with x),
        dynamically generate all barcodes and display on the page.'''

        d = Deferred()
        d.addCallback(self.check_input, request=request)
        d.addCallbacks(self.render_barcodes_new, self.render_page,
                    callbackKeywords={"request": request}, errbackKeywords={"request": request})
        d.callback(None)
        return NOT_DONE_YET

class SecureBarcodeBruteforcerPage(BarcodeBruteforcerPage, SecureResource):
    def __init__(self, auth_server_url: str):
        BarcodeBruteforcerPage.__init__(selff)
        SecureResource.__init__(self, auth_server_url)

    def render_GET(self, request: Request):
        ''' Allow the user to input a UPC barcode (12 digits),
        with an x signifying a missing digit.'''

        d = self._verify_session(request, auth_server_url=self._auth_server_url)
        d.addCallbacks(self.render_page, self.redirect_login,
                       callbackKeywords={"request": request}, errbackKeywords={"request": request})
        return NOT_DONE_YET

    def render_POST(self, request: Request):
        ''' With the inputted UPC barcode (11 digits with x),
        dynamically generate all barcodes and display on the page.'''

        d = self._verify_session(request, auth_server_url=self._auth_server_url)
        d.addCallbacks(self.check_input, self.redirect_login,
                       callbackKeywords={"request": request}, errbackKeywords={"request": request})
        d.addCallbacks(self.render_barcodes, self.render_page,
                       callbackKeywords={"request": request}, errbackKeywords={"request": request})
        return NOT_DONE_YET
 
class SearchPage(HTTPResource):
    INDENT_SPACES = 4
    INVALID_CHARS = "{}[]()<>^"
    MAX_REGEX_SIZE = 500

    def __init__(self,
                 api_url: str):
        self._api_url = api_url
        self._db_client = MongoClientSync(api_url)

        # Initialize the indexes on all
        # department databases to allow for
        # text search.
        valid_databases = [
            GROCERY_NAME,
            HOME_BEAUTY_BABY_NAME,
            JF_NAME
        ]
        for db in valid_databases:
            try:
                self._db_client.select_collection(db, today())
                self._db_client.create_text_index("$**")

            except OperationFailure:
                pass

        self._bc_generator = UPCBarcodeGenerator(50, add_checksum=False)

    def render_GET(self,
                   request):
        # Define chain of events
        d = Deferred()
        d.addCallback(self.check_query, request=request)
        d.addCallbacks(self.search_database, self.render_page,
                    callbackKeywords={"request": request}, errbackKeywords={"request": request})
        d.addCallback(self.display_nonjson, request=request)
        # Fire off chain of events
        d.callback(None)
        return NOT_DONE_YET

    # Check whether there was a query sent
    # in the request.
    def check_query(self,
                    http_response: HTTPResponse,
                    request):
        assert isinstance(http_response, HTTPResponse) or http_response == None
        search_query = request.args[b"search"][0].decode("utf-8")
        search_query = html.escape(search_query)
        department_selected = request.args[b"department"][0].decode("utf-8")
        department_selected = html.escape(department_selected)
        print(f"{search_query} {department_selected}")
        return (search_query, department_selected)

    # Display the
    # page html to the client.
    def render_page(self,
                    failure: Failure,
                    request):
        if isinstance(failure, Failure):
            valid_databases = [GROCERY_NAME,
                                HOME_BEAUTY_BABY_NAME,
                                JF_NAME]
            options_html = "\n".join(f'<option value="{db}">{db}</option>' for db in valid_databases)
            to_render = f'''<!DOCTYPE HTML>
                            <html>
                                <head>
                                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
                                            <select id="department" name="department">
                                                {options_html}
                                            </select>
                                        </div>
                                        <div>
                                            <button type="submit"></button>
                                        </div>
                                    </form>
                                </body>
                            </html>'''
            request.write(to_render.encode("utf-8"))
            request.finish()

    # Query the item server to perform a recursive search
    def search_database(self,
                        query_department: tuple,
                        request):
        assert isinstance(query_department, tuple)
        assert len(query_department) == 2
        search_query, department = query_department
        assert isinstance(search_query, str)
        assert isinstance(department, str)
        print(f"Search query: {search_query}")
        print(f"Department: {department}")

        # Select the department in the database.
        # Always choose the most recent collection (today)
        # per department.
        todays_date = today()
        self._db_client.select_collection(department, todays_date)
        query_matches = {}

        if search_query != None:
            headers = {}
            headers["Connection"] = "close"
            cookies = {}
            session_cookie = ICookie(request.getSession()).value
            cookies[SESSION_ID_KEY] = session_cookie

            # Get all matches for the query.
            # Sort them by text relevance.
            tokens = search_query.strip().split(" ")
            phrases_str= " ".join([f"\"{t}\"" for t in tokens])
            query = {"$text": {"$search": f'"{phrases_str}"'}}
            cursor = self._db_client.find(query).sort("score", {"$meta": "textScore"})
            query_matches = {item["_id"]: item for item in cursor}
        return query_matches

    # Pretty print all data for the client on the page.
    def display_json(self,
                     data: dict,
                     request):
        assert isinstance(data, dict)
        request.write(b"<pre>" + bytes(json.dumps(data, indent=4), "utf-8") + b"</pre>")
        request.finish()

    def display_nonjson(self,
                        matches: dict,
                        request):
        assert isinstance(matches, dict)
        for _, product in matches.items():
            title = product["product_title"]
            brand = "(brand n/a)" if product["product_brand"] == "" else product["product_brand"]
            link = product["product_url"]
            id = product["product_id"]
            pps = product["product_package_size"]
            product_listing = [self._generate_link(title, f"https://realcanadiansuperstore.ca{link}"), brand, id, pps]
            
            for datum in product_listing:
                if datum == "":
                    product_listing.remove(datum)
            product_listing_str = "\n".join(product_listing) + "\n"

            # Price info (nested)
            for key, price in product["prices"].items():
                if price != "":
                    product_listing_str += f"{key}: {price}\n".replace("_", " ")

            # Code info (nested)
            for key, code in product["codes"].items():
                if code != "":
                    product_listing_str += f"{key}: {code}\n"
                    
                    if key.strip() == "upc":
                        stream = io.BytesIO()
                        try:
                            self._bc_generator.write(code, stream)
                            product_listing_str += f"<div>{str(stream.getvalue(), 'utf-8')}</div>"
                            
                        except Exception as e:
                            print(e)
                            pass

            # Write all data to the page
            request.write(b"<pre>" + bytes(product_listing_str, "utf-8") + b"</pre>")
        request.finish()
        # <------- Helper Functions ------>
    def _check_valid_regex(self, regex):
        ''' Check whether the regex string
        qualifies for search.'''
        assert isinstance(regex, str)

        if len(regex) > SearchPage.MAX_REGEX_SIZE:
            return False

        for c in SearchPage.INVALID_CHARS:
            if c in regex:
                return False

        return True

    def _has_match(self,
                  regex: str,
                  dictionary: dict) -> bool:
        ''' Check whether the dictionary has a value field
        which matches the regex.
        Key fields are ignored from regex search.'''
        assert isinstance(regex, str)
        assert isinstance(dictionary, dict)
        
        # Start matching by iterating through each key.
        # If the string is present in the item
        # title, return the entire item. If the string is present
        # as a key value of the item, return the entire item.
        # pattern_str = ".*%s.*" % regex
        pattern_str = "%s" % regex
        pattern_compiled = re.compile(re.escape(pattern_str), re.IGNORECASE)

        # Prevent redundant recompilation of regex
        # pattern through the driver.
        def recursive_driver(pattern_compiled,
                                dictionary: dict):
            for key in dictionary:
                assert isinstance(key, str)
                value = dictionary[key]
                assert isinstance(value, str) or isinstance(value, dict)

                if isinstance(value, str):
                    if pattern_compiled.search(value) == None:
                        continue
                    
                    else:
                        return True

                elif isinstance(value, dict):
                    return recursive_driver(pattern_compiled, value)

        # Begin recursion
        return recursive_driver(pattern_compiled, dictionary)

    def _clean_whitespace(self,
                          string: str):
        assert isinstance(string, str)
        return " ".join(string.split())

    def _get_matches(self,
                    query: str,
                    items: list) -> list:
        assert isinstance(query, str)
        assert isinstance(items, list)
        matches = []

        # If the query has any spaces,
        # treat them as seperate tokens!
        query = self._clean_whitespace(query)
        tokens = query.split(" ")

        # Start search for all items.
        # Note that for any given item,
        # all tokens must match within the dictionary.
        for item in items:
            assert isinstance(item, dict)
            item_matched = True

            for token in tokens:
                if not self._has_match(token, item):
                    item_matched = False

            if item_matched:
                matches.append(item)

        return matches

class SecureSearchPage(SearchPage, SecureResource):
    def __init__(self,
                 auth_server_url: str,
                 api_url: str):
        assert isinstance(auth_server_url, str)
        assert isinstance(api_url, str)
        SecureResource.__init__(self, auth_server_url)
        SearchPage.__init__(self, api_url)

    def render_GET(self, request: Request):
        ''' Allow the user to input information
            into a search bar to perform
            a recursive grep search.

            For all items returned in the search page,
            table them and display hyperlinks to each page.'''

        # Start processing!
        d = self._verify_session(request, auth_server_url=self._auth_server_url)
        d.addCallbacks(self.check_query, self.redirect_login, 
                       callbackKeywords={"request": request}, errbackKeywords={"request": request})
        d.addCallbacks(self.search_database, self.render_page,
                       callbackKeywords={"request": request}, errbackKeywords={"request": request})
        # d.addCallback(self.display_json, request=request)
        d.addCallback(self.display_nonjson, request=request)
        return NOT_DONE_YET

# -------- MAIN PROGRAM -------- #
def get_web_tree_no_auth(item_server_uri):
    root = Resource()
    # root.putChild(b"", HomePage())
    root.putChild(b"", HomePage())
    root.putChild(b"search", SearchPage(item_server_uri))
    root.putChild(b"barcode_bruteforcer", BarcodeBruteforcerPage())
    return root

def get_web_tree_auth(item_server_uri: str, auth_server_uri: str):
    root = Resource()
    root.putChild(b"login", LoginPage(auth_server_uri))
    root.putChild(b"", SecureHomePage(auth_server_uri))
    root.putChild(b"search", SecureSearchPage(auth_server_uri, item_server_uri))
    root.putChild(b"barcode_bruteforcer", SecureBarcodeBruteforcerPage(auth_server_uri))
    return root

    
if __name__ == "__main__":
    # Get the mongodb endpoint for our item server.
    parser = argparse.ArgumentParser()
    parser.add_argument("--item_server_uri", "-isuri", action="store", type=str, dest="item_server_uri", required=True)
    parser.add_argument("--auth_server_uri", "-asuri", action="store", type=str, dest="auth_server_uri")
    args = parser.parse_args()
    item_server_uri = args.item_server_uri
    auth_server_uri = args.auth_server_uri

    # If the auth_server_uri is provided,
    # then run the website with authentication.
    if auth_server_uri:
        root = get_web_tree_auth(item_server_uri, auth_server_uri)

    else:
        root = get_web_tree_no_auth(item_server_uri)

    # Serve the web tree
    factory = Site(root)

    # Serve connections
    endpoint = endpoints.TCP4ServerEndpoint(reactor, HTTP_PORT)
    endpoint.listen(factory)
    reactor.run()


