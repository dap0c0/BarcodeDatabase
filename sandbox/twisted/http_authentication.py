from zope.interface import implementer
from twisted.web.server import Site
from twisted.cred.portal import IRealm
from twisted.web.static import File
from twisted.internet import endpoints, reactor

@implementer(IRealm)
class PublicHTMLRealm(object):
    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return (IResource, File("./%s/test.txt" % (avatarId,)), lambda: None)
        raise NotImplementedError()

from twisted.cred.portal import Portal
from twisted.cred.checkers import FilePasswordDB
portal = Portal(PublicHTMLRealm(), [FilePasswordDB(filename="httpd.password")])

# Check credentials
from twisted.web.guard import DigestCredentialFactory
credentialFactory = DigestCredentialFactory("md5", "localhost:80")

# handle authentications
from twisted.web.guard import HTTPAuthSessionWrapper
resource = HTTPAuthSessionWrapper(portal, [credentialFactory])

factory = Site(resource)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 80)
endpoint.listen(factory)
reactor.run()
