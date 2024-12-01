from ItemDatabase import ItemDatabase
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor, endpoints, ssl
import json
import html

class ItemProtocol(Resource):
    ''' HTTP protocol for serving items from the 
        supplied item database.'''
    isLeaf = True

    def __init__(self, file_path, indents: int=4):
        Resource.__init__(self)
        self._indents = indents
        self._item_database = ItemDatabase(file_path)

    def render_GET(self, request):
        '''Client must search through URL api as such:
        localhost:port/?search=foo+bar.

        The protocol will return all recursive grep matches
        in json format.'''

        # Get the value of the search key and parse it for security
        search_arg = request.args[b"search"][0].decode("utf-8")
        arg_escaped = html.escape(search_arg)
        matches = self._item_database.search_matches_iterative(arg_escaped)

        # Send back response to the client
        response = json.dumps(matches, indent=self._indents).encode("utf-8")
        return response

    def render_POST(self, request):
        pass

class ItemServer(object):
    def __init__(self, protocol):
        assert isinstance(protocol, ItemProtocol)
        self.protocol = protocol

    def run_http(self, port=8080):
        ''' Serve items through http at the
        supplied port.'''
        assert isinstance(port, int)
        factory = Site(self.protocol)
        http_endpoint = endpoints.TCP4ServerEndpoint(reactor, port)
        http_endpoint.listen(factory)
        reactor.run()

    def run_https(self, cert_file, key_file, port=443):
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
        factory = Site(self.protocol)
        ssl_endpoint.listen(factory)
        reactor.run()

item_server = ItemServer(ItemProtocol("test_file.json"))
item_server.run_https(cert_file="crt.pem", key_file="key.pem")
