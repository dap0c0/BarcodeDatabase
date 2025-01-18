from twisted.web.server import Site, Session
from twisted.web.resource import Resource
from twisted.internet import reactor, endpoints

class ShortSession(Session):
    sessionTimeout = 30

class ExpirationLogger(Resource):
    sessions = set()

    def render_GET(self, request):
        ''' Keep track of sessions if new one applied.'''
        session = request.getSession()

        if session.uid not in self.sessions:
            self.sessions.add(session.uid)
            session.notifyOnExpire(lambda: self._expired(session.uid))

        return ""

    def _expired(self, uid):
        print("Session", uid, "has expired.")
        self.sessions.remove(uid)

root = Resource()
root.putChild(b"logme", ExpirationLogger())
factory = Site(root)
factory.sessionFactory = ShortSession

endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)
reactor.run()
