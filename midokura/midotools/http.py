#!/usr/bin/python
import SimpleHTTPServer
import SocketServer


class myHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    # Handler for the GET requests
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        # Send the html message
        self.wfile.write('Hello world!')
        return


class myHTTPServer:

    def __init__(self, port=8087, ip='localhost'):
        self.PORT = port
        # Create a web server and define the handler to manage the
        # incoming request
        self.server = SocketServer.TCPServer((ip, self.PORT), myHandler)

    def start(self):
        try:
            print "serving at port", self.PORT
            # Wait forever for incoming htto request
            self.server.serve_forever()

        except KeyboardInterrupt:
            print '^C received, shutting down the web server'
            self.server.socket.close()

    def stop(self):
        self.server.socket.close()
