from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor, endpoints

class PaymentRequired(Resource):
    def render_GET(self, request):
        # Respond with a code 402
        request.setResponseCode(402)
        return b"<html><body>Please swipe your credit card.</body></html>"

# start running server
root = Resource()
root.putChild(b"buy", PaymentRequired())

# Serve the tree!
factory = Site(root)

# Upon connection at an endpoint, create a factory to service the transport.
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)

# run!
reactor.run()
