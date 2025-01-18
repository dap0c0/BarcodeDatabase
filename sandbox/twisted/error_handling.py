from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor, endpoints
from calendar import calendar
from twisted.web.pages import notFound


class YearPage(Resource):
    def __init__(self, year):
        # Inherit all attributes from resource
        Resource.__init__(self)
        self.year = year

    def render_GET(self, request):
        cal = calendar(self.year)
        return (b"<!DOCTYPE html><html><head><meta charset='utf-8'>"
                b"<title></title></head><body><pre>" + cal.encode('utf-8') + b"</pre>")

class Calendar(Resource):
    def getChild(self, name, request):
        try:
            year = int(name)

        except ValueError:
            return notFound()

        else:
            return YearPage(year)

root = Calendar()
factory = Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8080)
endpoint.listen(factory)
reactor.run()
