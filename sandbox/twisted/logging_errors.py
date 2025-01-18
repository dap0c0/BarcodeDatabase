from twisted.internet import endpoints, reactor
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.python.log import err

class DelayedResource(Resource):
    def _delayedRender(self, request):
        request.write(b"<html><body>Sorry to keep you waiting.....</body></html>")
        request.finish()

    def _responseFailed(self, failure, call):
        err(failure, b"Async response demo interrupted response")
        call.cancel()

    def render_GET(self, request):
        # call = reactor.callLater(5, self._delayedRender, request)
        reactor.callLater(5, self._delayedRender, request)
        # request.notifyFinish().addErrback(self._responseFailed, call)
        return NOT_DONE_YET

resource = DelayedResource()
factory = Site(resource)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)
reactor.run()

