from ItemDatabase import ItemDatabase
from ScryptPasswordDB import ScryptPasswordDB
from SessionHandler import SessionHandler
from twisted.web.server import Site, Session
from twisted.web.resource import Resource
from twisted.internet import reactor, endpoints, ssl
import base64
import json
import html

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

        # Get the value of the search key and parse it for security
        search_arg = request.args[b"search"][0].decode("utf-8")
        arg_escaped = html.escape(search_arg)
        matches = self._item_database.search_matches_iterative(arg_escaped)

        # Send back response to the client
        response = json.dumps(matches, indent=self._indents).encode("utf-8")
        return response

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
       
        # Get the data. Assure that it is json.
        # If json, ensure that it is the correct format
        # for submission of data.
        data = request.content.read()
        
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
    def _authenticate_request(self, request):
        pass

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
                        print(sub_key)
                        return False
        return True

class ItemServer(object):
    DEFAULT_PORT = 1931
    def __init__(self, protocol):
        assert isinstance(protocol, ItemProtocol)
        self._protocol = protocol

    def run_https(self, cert_file, key_file, port=DEFAULT_PORT):
        '''Serve items through https at the previously
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
