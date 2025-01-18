from warnings import warn
from twisted.web.resource import Resource
from twisted.web.server import Site, NOT_DONE_YET
from twisted.internet import reactor, endpoints
from twisted.web.pages import notFound

class DelayedResource(Resource):
    def __init__(self, seconds: int | float):
        assert isinstance(seconds, int) or isinstance(seconds, float)
        self.seconds = seconds

    def _delayedRender(self, request):
        request.write(b"<html><body>Sorry to keep you waiting</body></html>")
        request.finish()

    def render_GET(self, request):
        reactor.callLater(self.seconds, self._delayedRender, request)
        return NOT_DONE_YET

class Waiter(Resource):
    def getChild(self, name, request):
        try:
            seconds = float(name)

        except ValueError:
            return notFound()

        else:
            return DelayedResource(seconds)

waiter = Waiter()
factory = Site(waiter)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)
reactor.run()
