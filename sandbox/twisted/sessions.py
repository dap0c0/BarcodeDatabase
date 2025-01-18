from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.internet import endpoints, reactor

class ShowSession(Resource):
    def render_GET(self, request):
        return b"Your session id is: " + request.getSession().uid

class ExpireSession(Resource):
    def render_GET(self, request):
        session_id = request.getSession().uid
        request.getSession().expire()
        return b"Your session " + session_id + b" has expired."

class ObserveSession(Resource):
    def render_GET(self, request):
        session = request.getSession()
        attributes = session.__dict__
        print(attributes)
        return bytes(attributes, "utf-8")

root = ShowSession()
root.putChild(b"expire", ExpireSession())
root.putChild(b"observe", ObserveSession())
factory = Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)
reactor.run()
