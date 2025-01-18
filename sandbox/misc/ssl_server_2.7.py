import BaseHTTPServer
import SimpleHTTPServer
import ssl

class SecureHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def setup(self):
        self.connection = self.request
        self.rfile = self.connection.makefile("rb", self.rbufsize)
        self.wfile = self.connection.makefile("wb", self.wbufsize)

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hello, World!")

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])

        # Parse body of post request
        body = self.rfile.read(content_length)

        # Send data back to client
        self.send_response(200)
        self.end_headers()
        response = b"This is a POST request.\n"
        response += body
        self.wfile.write(response)

if __name__ == "__main__":
    address = ("localhost", 4443)
    httpd = BaseHTTPServer.HTTPServer(address, SecureHTTPRequestHandler)


    # Wrap socket in ssl context
    fkey = "key.pem"
    fcert = "cert.pem"
    httpd.socket = ssl.wrap_socket(httpd.socket,
                                keyfile=fkey,
                                certfile=fcert, server_side=True)
    
    # Start running server
    print("Running server on %s:%s" % (address[0], address[1]))
    httpd.serve_forever()
