from zope.interface import Interface, Attribute, implementer
from twisted.python.components import registerAdapter
from twisted.web.server import Session
from twisted.internet import reactor

class ICounter(Interface):
    value = Attribute("An int value which counts up once per page view.")

@implementer(ICounter)
class Counter(object):
    def __init__(self, session):
        self.value = 0

registerAdapter(Counter, Session, ICounter)

# Count!
from twisted.web.resource import Resource
class CounterResource(Resource):
    def render_GET(self, request):
        session = request.getSession()
        counter = ICounter(session)
        counter.value += 1
        return (b"<!DOCTYPE html><html><head><meta charset='utf-8'>"
                b"<title></title></head><body>"
                b"Visit #" + str(counter.value).encode("utf-8") +
                b" for you!")

from twisted.internet import endpoints, reactor
from twisted.web.server import Site
root = Resource()
root.putChild(b"count", CounterResource())
factory = Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)
reactor.run()
