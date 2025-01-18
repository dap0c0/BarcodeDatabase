from ScryptPasswordDB import ScryptPasswordDB
from SessionHandler import SessionHandler
from twisted.internet import reactor, endpoints, ssl
from twisted.internet.defer import Deferred
from twisted.web.server import Site, NOT_DONE_YET, Session
from twisted.web.resource import Resource
from twisted.web.http import Request
from abc import ABC, abstractmethod
import secrets
import base64
import html
DEFAULT_PORT = 3191

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

class AuthServer(ABC, Resource):
    ''' Allow front-end and back-end to validate sessions
        and login credentials.'''
    def __init__(self, pass_db: ScryptPasswordDB):
        assert isinstance(pass_db, ScryptPasswordDB)

        # Somehow, changing from Resource() to Resource fixed the bug.
        # Resource.__init__(self)
        Resource.__init__(self)
        self._login_authenticator = LoginAuthenticator(pass_db)

    @abstractmethod
    def _verify_user(self, to_auth: object):
        ''' Authenticate either token or cookie.'''
        pass

    def _verify_login(self, username: str, password: str):
        return self._login_authenticator.authenticate_params(username, password)

class AuthServerCookie(AuthServer):
    ''' Provides authentication for session cookies.'''
    DEFAULT_TOKEN_LENGTH = 128
    SESSION_COOKIE_NAME = "session_id"

    def __init__(self, pass_db: ScryptPasswordDB):
        super().__init__(pass_db)
        self._session_handler = SessionHandler()

    def _generate_token(self, num_bytes: int=DEFAULT_TOKEN_LENGTH) -> str:
        ''' Generate a random base64 cookie for the client.'''
        assert isinstance(num_bytes, int)
        assert num_bytes > 0
        return secrets.token_hex(num_bytes)
        
    def _verify_user(self, to_auth: object):
        ''' Verify that the session cookie
            exists in our session handler.'''
        assert isinstance(to_auth, bytes)
        return self._session_handler.verify_session(str(to_auth, "utf-8"))

    def render_GET(self, request: Request):
        ''' Receive GET request from clients (front-end and back-end).
        Check the client's session_id cookie. Then, check the basic auth header
        for base64 encoding of login parameters.

        If authenticated, return the session_id to the client.
        If not authenticated, return an empty response.'''
        assert isinstance(request, Request)
        breakpoint()
        
        # Check the session_id cookie.
        try:
            session_id = request.getCookie(bytes(AuthServerCookie.SESSION_COOKIE_NAME, "utf-8"))
            print(f"session_id: {session_id}")

            if self._verify_user(session_id):
                return session_id

            else:
                return b""

        # No session_id cookie exists!
        # Attempt to check the authorization header.
        except:
            try:
                auth = request.getHeader("Authorization")
                auth = html.escape(auth)
                print(f"Auth is {auth}")

                # Continue with login authorization
                _, auth = auth.split(" ")
                decoded = base64.b64decode(auth)
                username, password = decoded.split(b":")

                # Supply token to client upon authentication
                if self._verify_login(str(username, "utf-8"), str(password, "utf-8")):
                    token = self._generate_token()
                    self._session_handler.add_session(token)
                    print(f"Token generated: {token}")

                    # Responses are what observed by the clients
                    # for reusablility purposes.
                    # request.addCookie(k="session_id", v=token)
                    return bytes(token, "utf-8")

                # Inputs fail authentication
                else:
                    return b""

            # It's possible that no input was supplied,
            # or the authorization parameter was invalid
            except:
                return b""

    def getChild(self, name, request):
        return self

def run_https(server_class: AuthServer,
               pass_db: ScryptPasswordDB,
               pkey_file: str,
               crt_file: str,
              port: int=DEFAULT_PORT):
    ''' Run server through SSL.'''
    assert isinstance(pass_db, ScryptPasswordDB)
    assert isinstance(pkey_file, str)
    assert isinstance(crt_file, str)
    assert isinstance(port, int)
    assert port >= 0
    server = server_class(pass_db)

    # Create an ssl context
    ssl_context = ssl.DefaultOpenSSLContextFactory(
        pkey_file,
        crt_file
    )
    
    # Establish endpoint via ssl context
    ssl_endpoint = endpoints.SSL4ServerEndpoint(reactor,
                                            port,
                                            ssl_context)
    # Serve data on this endpoint
    root = Resource()
    root.putChild(b"test_auth", server)
    factory = Site(root)
    ssl_endpoint.listen(factory)
    reactor.run()
    
if __name__ == "__main__":
    run_https(AuthServerCookie,
              ScryptPasswordDB(),
              "key.pem",
              "crt.pem")
