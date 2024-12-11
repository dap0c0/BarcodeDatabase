from ItemServer import ItemProtocol, ItemServer
from ScryptPasswordDB import ScryptPasswordDB
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor, endpoints, ssl
from twisted.web.util import redirectTo
import html
import base64

# Possibly unused
class LoginAuthenticator():
    ''' Authenticates logins by comparing the decoded
    base64 token with the hashes for respective users.'''
    def __init__(self, pass_database: ScryptPasswordDB):
        assert isinstance(pass_database, ScryptPasswordDB)
        self._pass_database = pass_database

    def authenticate_params(self, username: str, password: str):
        ''' Regenerate hash from the supplied
        username and password. Compare it with the one
        stored in the password database.

        Returns True upon match, False if not.'''
        assert isinstance(username, str)
        assert isinstance(password, str)
        
        if username != "" and \
            password != "" and \
            self._pass_database.verify_pass_file(
                username,
                bytes(password, "utf-8")
            ):
            return True

        return False

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
        search_query = request.args[b"search"][0].decode("utf-8")
        search_query = html.escape(search_query)

        if not search_query:
            html = f'''<!DOCTYPE HTML>
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
            return html.encode("utf-8")

# Create the resource
root = Resource()
root.putChild(b"login", LoginPage(LoginAuthenticator(ScryptPasswordDB())))
root.putChild(b"home", HomePage())
root.putChild(b"search", SearchPage())

# Serve the web tree
factory = Site(root)

# Serve connections
endpoint = endpoints.TCP4ServerEndpoint(reactor, 80)
endpoint.listen(factory)
reactor.run()
