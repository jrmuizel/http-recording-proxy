#!/bin/sh -
"exec" "python" "-O" "$0" "$@"

__doc__ = """Tiny HTTP Proxy.

This module implements GET, HEAD, POST, PUT and DELETE methods
on BaseHTTPServer, and behaves as an HTTP proxy.  The CONNECT
method is also implemented experimentally, but has not been
tested yet.

Any help will be greatly appreciated.		SUZUKI Hisao
"""

__version__ = "0.2.1"

replay = False

import BaseHTTPServer, select, socket, SocketServer, urlparse, urllib
import os

prefix = "log"

class ProxyHandler (BaseHTTPServer.BaseHTTPRequestHandler):
    __base = BaseHTTPServer.BaseHTTPRequestHandler
    __base_handle = __base.handle

    server_version = "TinyHTTPProxy/" + __version__
    rbufsize = 0                        # self.rfile Be unbuffered

    def handle(self):
        (ip, port) =  self.client_address
        if hasattr(self, 'allowed_clients') and ip not in self.allowed_clients:
            self.raw_requestline = self.rfile.readline()
            if self.parse_request(): self.send_error(403)
        else:
            self.__base_handle()

    def _connect_to(self, netloc, soc):
        i = netloc.find(':')
        if i >= 0:
            host_port = netloc[:i], int(netloc[i+1:])
        else:
            host_port = netloc, 80
        print "\t" "connect to %s:%d" % host_port
        try: soc.connect(host_port)
        except socket.error, arg:
            try: msg = arg[1]
            except: msg = arg
            self.send_error(404, msg)
            return 0
        return 1

    def do_CONNECT(self):
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if self._connect_to(self.path, soc):
                self.log_request(200)
                self.wfile.write(self.protocol_version +
                                 " 200 Connection established\r\n")
                self.wfile.write("Proxy-agent: %s\r\n" % self.version_string())
                self.wfile.write("\r\n")
                self._read_write(soc, 300)
        finally:
            print "\t" "bye"
            soc.close()
            self.connection.close()


    def do_GET(self):
        # we use this function to remove insignificant parts of the url
	def substitute(url):
            substrs = []
            # here's an example of some filtered urls
            '''
	    substrs = ['http%3A%2F%2Fby126w.bay126.mail.live.com%2Fmail%2FInboxLight.aspx%3FFolderID%3D00000000-0000-0000-0000-000000000001%26InboxSortAscending%3DFalse%26InboxSortBy%3DDate%26n%3D',
		       'http%3A%2F%2Fby126w.bay126.mail.live.com%2Fmail%2Fmail.fpp%3Fcnmn%3DMicrosoft.Msn.Hotmail.Ui.Fpp.MailBox.GetInboxData%26a%3D',
		       'http%3A%2F%2Fh.msn.com%2Fc.gif%3FRF%3D%26PI%3D44318%26DI%3D5692%26PS%3D9',
		       'http%3A%2F%2Fb.rad.msn.com%2FADSAdClient31.dll%3FGetSAd%3D%26DPJS%3D4%26PN%3DMSFT%26ID%3D0A555474DA3B1282CFAFA6FAFFFFFFFF%26MUID%3Dd392f5886b2b4cbfba761ac3b08d8fb0%26AP%3D1',
		       'http%3A%2F%2Fas.casalemedia.com%2Fj%3Fs%3D111152%26u%3D%26a%3D5%26id%3D',
		       'http%3A%2F%2Fbellcan.adbureau.net%2Fjserver%2Fsite%3DENSYMP.wlm%2Farea%3Dmale.25to34%2Faamsz%3D']
	    '''
            for s in substrs:
                # check if the url starts with 's'
                if url.find(s) != -1:
		    return s
	    return url


        (scm, netloc, path, params, query, fragment) = urlparse.urlparse(
            self.path, 'http')
        # chop the quoted path so that we don't over run any filesystem limits
	current_file_name = urllib.quote(self.path, "")[:250]

	current_file_name = substitute(current_file_name)
	
	if replay:
		result = open(prefix + "/" + current_file_name, "r")
		print urllib.quote(self.path, "")
		self.connection.send(result.read())
		self.connection.close()
                self.log_request()
		return
	self.current_file = open(prefix + "/" + current_file_name, "w+")
        if scm != 'http' or fragment or not netloc:
            self.send_error(400, "bad url %s" % self.path)
            return
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if self._connect_to(netloc, soc):
                self.log_request()
                soc.send("%s %s %s\r\n" % (
                    self.command,
                    urlparse.urlunparse(('', '', path, params, query, '')),
                    self.request_version))
                self.headers['Connection'] = 'close'
                del self.headers['Proxy-Connection']
                for key_val in self.headers.items():
		    # ignore accept-encoding headers so that we don't get gziped data
		    if key_val[0] != 'accept-encoding':
                        soc.send("%s: %s\r\n" % key_val)
                soc.send("\r\n")
                self._read_write(soc)
        finally:
            print "\t" "bye"
	    self.current_file.close()
            soc.close()
            self.connection.close()

    def _read_write(self, soc, max_idling=20):
        iw = [self.connection, soc]
        ow = []
        count = 0
        while 1:
            count += 1
            (ins, _, exs) = select.select(iw, ow, iw, 3)
            if exs: break
            if ins:
                for i in ins:
                    if i is soc:
                        out = self.connection
                    else:
                        out = soc
                    data = i.recv(8192)
		    self.current_file.write(data)
                    if data:
                        out.send(data)
                        count = 0
            else:
                print "\t" "idle", count
            if count == max_idling: break

    do_HEAD = do_GET
    do_POST = do_GET
    do_PUT  = do_GET
    do_DELETE=do_GET

class ThreadingHTTPServer (SocketServer.ThreadingMixIn,
                           BaseHTTPServer.HTTPServer): pass

if __name__ == '__main__':
    from sys import argv
    try:
        os.mkdir(prefix)
    except:
	pass

    if argv[1:]:
	if argv[1] in ('-h', '--help'):
	    print argv[0], "[port [allowed_client_name ...]]"
	    sys.exit(1)
	if argv[1] in ('--replay'):
	    replay = True
	    del argv[1]
	    print "Replaying..."
    if argv[2:]:
	"""
	allowed = []
	for name in argv[2:]:
	    client = socket.gethostbyname(name)
	    allowed.append(client)
	    print "Accept: %s (%s)" % (client, name)
	ProxyHandler.allowed_clients = allowed
	del argv[2:]
"""
    else:
	print "Any clients will be served..."
    BaseHTTPServer.test(ProxyHandler, ThreadingHTTPServer)
