from abc import ABC, abstractmethod
from MongoClient import MongoClientSync
from HTTPResponse import HTTPResponse
from SimpleHTTPFactory import SimpleHTTPFactory
from AuthServer import AuthServerCookie
from BarcodeGenerator import BarcodeGenerator, UPCBarcodeGenerator
from PatternExtractor import PatternExtractor
from twisted.web.server import Site, NOT_DONE_YET, Session
from twisted.python.components import registerAdapter
from zope.interface import Interface, Attribute, implementer
from twisted.web.resource import Resource
from twisted.web.http import Request
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.internet import reactor, endpoints, ssl
from Globals import GROCERY_NAME, HOME_BEAUTY_BABY_NAME, JF_NAME
from DateFormatter import DateFormatter
from assets import fonts, colours
from pymongo.errors import OperationFailure
from bs4 import BeautifulSoup
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

class NoPriceRateExtracted(AssertionError):
    pass

class HTTPResource(Resource, ABC):
    def __init__(self):
        Resource.__init__(self)
        self._df = DateFormatter()

    def _generate_link(self, link_text: str, redirect: str, link_class: str=""):
        assert isinstance(link_text, str)
        assert isinstance(redirect, str)
        result = f'<a href="{redirect}"' + \
            (f' class="{link_class}"' if link_class != "" else "") + \
            f">{link_text.strip()}</a>"

        return result

    def _gen_upc_barcode_str(self,
                                bc_generator: UPCBarcodeGenerator,
                                upc_code: str) -> str:
        assert isinstance(upc_code, str)
        assert len(upc_code) == 11 or len(upc_code) == 12
        assert int(upc_code) # UPC should be all integer characters
        stream = io.BytesIO()
        self._bc_generator.write(upc_code, stream)
        return str(stream.getvalue(), "utf-8").replace('''<!DOCTYPE svg
  PUBLIC '-//W3C//DTD SVG 1.1//EN'
  'http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd'>''', '')

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


class RealProduct():
    # 1 kg = 2.20462262 lbs
    KG_TO_LBS_RATIO = 2.20462262

    def __init__(self,
                    weight: float | None,
                    w_in_kg: bool,
                    plu: int,
                    price_rate: float,
                    pr_unit: str):
        assert isinstance(weight, float) or weight == None
        assert isinstance(w_in_kg, bool)
        assert isinstance(plu, int)
        assert isinstance(price_rate, float)
        assert isinstance(pr_unit, str)
        self.weight = weight
        self.w_in_kg = w_in_kg
        self.plu = plu
        self.price_rate = price_rate
        self.pr_unit = pr_unit
        self.total_price = self._calculate_total_price()

    def _calculate_total_price(self):
        total_price = float()

        if self.weight:
            if self.w_in_kg:
                # Weight: kg, Rate: $/kg
                if self.pr_unit == "kg":
                    total_price = self.weight * self.price_rate

                # Weight: kg, Rate: $/lb
                # Convert kgs => lbs
                elif self.pr_unit == "lb":
                    total_price = self.weight * RealProduct.KG_TO_LBS_RATIO * self.price_rate

            else:
                # Weight: lb, rate: $/kg
                # Convert lbs => kgs
                if self.pr_unit == "kg":
                    total_price = (self.weight / RealProduct.KG_TO_LBS_RATIO) * self.price_rate

                # Weight: lb, rate: $/lb
                elif self.pr_unit == "lb":
                    total_price = self.weight * self.price_rate

        else:
            assert self.pr_unit == "ea"
            total_price = self.price_rate

        assert total_price > 0
        return total_price

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
                                <div>
                                    {self._generate_link("PLU Barcode Generator", "/plu_barcode_generator")}
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

        assert len(valid_upcs) == 10
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

class PLUBarcodeGeneratorPage(HTTPResource):
    PLU_MAX_LEN = 6
    PRICE_TOTAL_MAX_LEN = 5 # max number price digits in plu barcode
    MAX_UPC_BARCODE_LEN = 11 # Not 12, because we don't need the checksum.

    def __init__(self):
        self._bc_generator = UPCBarcodeGenerator(50, add_checksum=False)

    def _generate_html(self):
        ''' Prompt the client for weight data,
        price per unit (kg or lb), PLU, and/or total
        calculated price.'''
        
        to_render = '''<!DOCTYPE HTML>
                            <html>
                                <head>
                                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                    <meta charset='utf-8'>
                                    <style>
                                        .input-group {
                                            display: flex;
                                            align-items: center;
                                            gap: 10px; /* Adds spacing between elements */
                                        }
                                        .radio-group {
                                            display: flex;
                                            gap: 10px; /* Space between radio buttons */
                                        }
                                        input[type="text"] {
                                            padding: 5px;
                                            font-size: 16px;
                                        }
                                    </style>
                                </head>
                                <body>
                                    <form method="GET">
                                        <!-- Weight input with radio buttons -->
                                        <div class="input-group">
                                            <input type="text" name="weight" placeholder="weight" />
                                            <div class="radio-group">
                                                <label>
                                                    <input type="radio" name="wunit" value="kg" checked> kgs
                                                </label>
                                                <label>
                                                    <input type="radio" name="wunit" value="lb"> lbs
                                                </label>
                                            </div>
                                        </div>

                                        <!-- PLU input -->
                                        <div>
                                            <input type="text" name="plu" placeholder="plu"/>
                                        </div>

                                        <!-- Price Rate Override input with radio buttons -->
                                        <div class="input-group">
                                            <input type="text" name="price_rate" placeholder="price rate"/>
                                            <div class="radio-group">
                                                <label>
                                                    <input type="radio" name="prunit" value="kg" checked> $/kgs
                                                </label>
                                                <label>
                                                    <input type="radio" name="prunit" value="lb"> $/lbs
                                                </label>
                                                <label>
                                                    <input type="radio" name="prunit" value="ea"> $/ea
                                                </label>
                                            </div>
                                        </div>

                                        <!-- Submit button -->
                                        <div>
                                            <button type="submit">Submit</button>
                                        </div>
                                    </form>
                                </body>
                            </html>
                            '''
        return to_render

    # Display the page to the user!
    def render_page(self, failure: Failure, request):
        if isinstance(failure, Failure):
            html = self._generate_html()
            request.write(html.encode("utf-8"))
            request.finish()

    def check_params(self, http_response: HTTPResponse | None , request):
        assert isinstance(http_response, HTTPResponse) or http_response == None

        # Start retrieving all parameters
        # from the get request.
        weight = request.args[b"weight"][0].decode("utf-8")
        weight = html.escape(weight)
        wunit = request.args[b"wunit"][0].decode("utf-8")
        wunit = html.escape(wunit)

        plu = request.args[b"plu"][0].decode("utf-8")
        plu = html.escape(plu)

        price_rate = request.args[b"price_rate"][0].decode("utf-8")
        price_rate = html.escape(price_rate)
        prunit = request.args[b"prunit"][0].decode("utf-8")
        prunit = html.escape(prunit)

        # Organize data and redirect it
        # to the next callback to generate
        # the appropriate barcode.
        w_in_kg = wunit == "kg"
        try:
            weight = float(weight) # Possible failure: value error
            assert weight > 0
        except ValueError:
            weight = None

        plu = int(plu) # Possible failure: value error
        assert plu > 0
        price_rate = float(price_rate) # Possible failure: value error
        assert price_rate > 0
        return RealProduct(weight, w_in_kg, plu, price_rate, prunit)
    
    def generate_barcode(self, real_product: RealProduct, request: Request):
        assert isinstance(real_product, RealProduct)
        plu = real_product.plu
        total_price = real_product.total_price
        assert isinstance(plu, int)
        assert plu > 0
        assert isinstance(total_price, float)
        assert total_price > 0

        # Note that PLUs in our store
        # are always prepended with a 2. To make
        # 6 digits of our UPC barcode, we fill any
        # remaining spaces with 0.
        plu = str(plu)
        assert 0 < len(plu) and len(plu) <= PLUBarcodeGeneratorPage.PLU_MAX_LEN
        if len(plu) != 6:
            plu = "2" + \
                "".join(["0" for _ in range(PLUBarcodeGeneratorPage.PLU_MAX_LEN - 1 - len(plu))]) + \
                plu

        # Check the total price's amount of digits.
        # We may have any of the following presentations
        # of prices: $123.45, $12.34, $1.34
        total_price = "%.2f" % round(total_price, 2)
        total_price = "".join(total_price.split("."))
        upc_barcode = plu + \
            "".join(["0" for _ in range(PLUBarcodeGeneratorPage.PRICE_TOTAL_MAX_LEN - len(total_price))]) + \
            total_price
        assert len(upc_barcode) == PLUBarcodeGeneratorPage.MAX_UPC_BARCODE_LEN
        return (real_product, upc_barcode)

    def render_barcode(self, real_product_upc_barcode: tuple, request):
        real_product, upc_barcode = real_product_upc_barcode

        if upc_barcode != None:
            assert len(upc_barcode) == PLUBarcodeGeneratorPage.MAX_UPC_BARCODE_LEN

            # Write the barcode into a stream
            stream = io.BytesIO()
            self._bc_generator.write(upc_barcode, stream)

            # Render it onto the page
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
            plu = real_product.plu
            total_price = real_product.total_price
            to_render += f"<div>PLU: {plu}</div>"
            to_render += f"<div>Total Price: ${total_price}</div>"
            to_render += f"<div>{str(stream.getvalue(), 'utf-8')}</div>"
            to_render += """
                </body>
            </html>
            """
            request.write(to_render.encode("utf-8"))
            request.finish()

    def render_GET(self, request: Request):
        REQ_DICT = {"request": request}
        d = Deferred()
        d.addCallback(self.check_params, request=request)
        d.addCallback(self.generate_barcode, request=request)
        d.addCallbacks(self.render_barcode, self.render_page,
                       callbackKeywords=REQ_DICT, errbackKeywords=REQ_DICT)
        d.callback(None)
        return NOT_DONE_YET

class SecureBarcodeBruteforcerPage(BarcodeBruteforcerPage, SecureResource):
    def __init__(self, auth_server_url: str):
        BarcodeBruteforcerPage.__init__(self)
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
        HTTPResource.__init__(self)
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
                self._db_client.select_collection(db, self._df.date_offset_today(0))
                self._db_client.create_text_index("$**")

            except OperationFailure:
                pass

        self._bc_generator = UPCBarcodeGenerator(50, add_checksum=False)
        self._pattern_extractor = PatternExtractor()


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
        todays_date = self._df.date_offset_today(0)
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

    def display_nonjson(self,
                        matches: dict,
                        request):
        assert isinstance(matches, dict)
        page_html = ""

        for _, product in matches.items():
            title = product["product_title"]
            brand = "(brand n/a)" if product["product_brand"] == "" else product["product_brand"]
            link = product["product_url"]
            id = product["product_id"]
            pps = product["product_package_size"]
            product_listing = [
                self._generate_link(title, f"https://realcanadiansuperstore.ca{link}", "link"),
                brand, id, pps]
            product_html = "<div>"

            # General info
            for datum in product_listing:
                if datum == "":
                    product_listing.remove(datum)
            product_html += "\n".join([f"<div>{i}</div>" for i in product_listing]) + "\n"

            # Price info (nested)
            for key, price in product["prices"].items():
                if price != "":
                    product_html += f"<div>{key}: {price}</div>".replace("_", " ")

            # Code info (nested)
            for key, code in product["codes"].items():
                if code != "" and key.strip() == "upc":
                    try:
                        product_html += f"<div>{self._gen_upc_barcode_str(self._bc_generator, code)}</div>"
                        
                    except Exception:
                        pass
                        
                # Allow the client to redirect to
                # the PLUBarcodeGeneratorPage to generate
                # a scannable barcode given a certain weight.
                if code != "" and key.strip() == "plu":
                    product_html += f"{key}: {code}\n"
                    # In order of preference from kg -> lb -> ea,
                    # extract the first price rate that presents itself
                    price_rate, prunit = self._get_pr_prunit(product)
                    wunit = "kg"
                    plu = code
                    weight_line = (
                        '<input type="hidden" name="weight" />' if prunit == "ea"
                        else '<input type="text" name="weight" placeholder="Weight (kg)" required/>')

                    form_html = f'''<form method="GET" action="/plu_barcode_generator">
                                {weight_line}
                                <button type="submit">Generate Barcode</button>
                                <input type="hidden" name="wunit" value="{wunit}"/>
                                <input type="hidden" name="plu" value="{plu}"/>
                                <input type="hidden" name="price_rate" value="{price_rate}"/>
                                <input type="hidden" name="prunit" value="{prunit}"/>
                            </form>'''
                    product_html += form_html
            product_html += '<div style="border-bottom: 1px solid #ccc; margin-top: 10px;"></div>'
            product_html += "</div>"
            page_html += product_html

        # Write all data to the page
        soup = BeautifulSoup(page_html, "html.parser")
        page_html = '''<!DOCTYPE html>
                            <html>
                                <head>
                                    <style>
                                        body {
                                            display: flex;
                                            flex-direction: column;
                                            white-space: normal;
                                            font-family: Menlo;
                                            font-size: 14px;
                                            min-height: 100vh;
                                            padding: 5px
                                            margin: 0;
                                        }
                                        .link {
                                            white-space: pre-wrap;
                                            font-size: inherit;
                                            word-wrap: break-word;
                                            max-width: 30ch;
                                            font-size: inherit;
                                            font-family: inherit;
                                        }
                                        input[type="text"] {
                                            padding: 5px;
                                            width: 100px;
                                            font-size: inherit;
                                            font-family: inherit;
                                        }
                                        button {
                                            font-size; inherit;
                                            font-family: inherit;
                                        }
                                        form {
                                            display: flex;
                                            width: 10px;
                                            margin: 0;
                                            padding: 0;
                                        }
                                    </style>
                                </head>''' + \
                            f'''<body>
                                    {str(soup)}
                                </body>
                        </html>
                            '''
        request.write(bytes(page_html, "utf-8"))
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

    def _get_pr_prunit(self, product: dict):
        ''' Extract (<price_rate>, <prunit>) from the given product.'''
        price_map = {f"dol_per_{unit}": unit for unit in ["kg", "lb", "ea"]}
        pps = product["product_package_size"]
        price_rate = prunit = None
        try:
            for key, pr in self._get_price(pps).items():
                if pr != None and key in price_map:
                    price_rate, prunit = pr, price_map[key]
                    break

        # The data in pps (price descriptor string) contains no
        # price rate per unit. It is something simple yet
        # strange like '1 ea' or '1 kg'.
        except NoPriceRateExtracted:
            for _, price in product["prices"].items():
                if price != "":
                    price_rate = float(price.split("$")[1].strip())
                    prunit = "ea"
                    break
        finally:
            assert price_rate != None and prunit != None, breakpoint()
            return (price_rate, prunit)

    def _get_price(self, price_descriptor: str) -> dict:
        ''' Attempt to extract the price rate(s)
        from the supplied price description string, like:
       "$21.58/1kg $9.79/1lb" or "1.5 kg, $1.53/100g"'''
        price_descriptor = price_descriptor.strip()
        data = {
            "dol_per_kg": None,
            "dol_per_lb": None,
            "dol_per_ea": None
        }
        gen_rate_pat = r"(?:\$(\d+\.\d{2})/(?:(\d+)(kg|g|lb|ea)))"
        self._pattern_extractor.set_pattern(gen_rate_pat)
        matches = self._pattern_extractor.get_matches(price_descriptor)
        data_filled = False

        for match in matches:
            price, num_units, unit = match
            price = float(price)
            num_units = int(num_units)

            if unit == "kg":
                data["dol_per_kg"] = price / num_units
                data_filled = True

            # Note: there are 1000g/kg
            if unit == "g":
                data["dol_per_kg"] = (price / num_units) * 1000
                data_filled = True

            if unit == "lb":
                data["dol_per_lb"] = price / num_units
                data_filled = True

            if unit == "ea":
                data["dol_per_ea"] = price / num_units
                data_filled = True
            
        if not data_filled:
            raise NoPriceRateExtracted(f"No price rate extracted from {price_descriptor}")

        return data

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
        # d.addCallback(suelf.display_json, request=request)
        d.addCallback(self.display_nonjson, request=request)
        return NOT_DONE_YET

# -------- MAIN PROGRAM -------- #
def get_web_tree_no_auth(item_server_uri):
    root = Resource()
    # root.putChild(b"", HomePage())
    root.putChild(b"", HomePage())
    root.putChild(b"search", SearchPage(item_server_uri))
    root.putChild(b"barcode_bruteforcer", BarcodeBruteforcerPage())
    root.putChild(b"plu_barcode_generator", PLUBarcodeGeneratorPage())
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


