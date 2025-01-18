from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler
from OpenSSL import SSL
from socketserver import BaseServer
import socket, os

class SecureHTTPServer(HTTPServer):
    def __init__(self, server_address: tuple, HandlerClass: SimpleHTTPRequestHandler):
        # Wrap the base socket server with HTTP
        BaseServer.__init__(self, server_address, HandlerClass)

        # Wrap the server in an HTTP context
        ctx = SSL.Context(SSL.SSLv23_METHOD)

        # Use private key and certificate
        fkey = "key.pem"
        fcert = "cert.pem"
        ctx.use_privatekey_file(fkey)
        ctx.use_certificate_file(fcert)

        # Wrap the socket in an ssl context
        self.socket = SSL.Connection(ctx, socket.socket(self.address_family, self.socket_type))

        # Activate the server
        self.server_bind()
        self.server_activate()

class SecureHTTPRequestHandler(SimpleHTTPRequestHandler):
    def setup(self):
        self.connection = self.request
        print(dir(self.connection))
        print(self.connection.makefile)

def run_server(HandlerClass: SimpleHTTPRequestHandler = SecureHTTPRequestHandler,
               ServerClass: HTTPServer = SecureHTTPServer):
    # Initiate server and run it
    server_address = ("localhost", 4443)
    server = ServerClass(server_address, HandlerClass)
    running_address = server.socket.getsockname()
    print(f"Serving HTTPS on {running_address[0]}:{running_address[1]}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
