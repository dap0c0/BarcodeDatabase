# Factory that glues ports to HTTPChannels (transports)
from twisted.web.server import Site

# ?
from twisted.web.static import File

# Drives asynchronous processing
from twisted.internet import reactor

# Creates listening sockets
from twisted.internet import endpoints

# Point resource to serve from
resource = File("./../../user-pass/")

# Asynchronously create protocols for service
# on httpchannels upon connectoin to the endpoint.
factory = Site(resource)

# Start listening on port 8080.
# Transport done through TCP4
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)

# run!
reactor.run()
