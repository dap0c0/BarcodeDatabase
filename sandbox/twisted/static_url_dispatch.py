from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor, endpoints
from twisted.web.static import File

# Create directory tree for http service
root = Resource()
root.putChild(b"foo", File("/tmp"))
root.putChild(b"bar", File("/opt"))
root.putChild(b"baz", File("test"))

# Asynchronously handle connections for the tree.
factory = Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)
reactor.run()
