"""Only the two fixture ports and loopback ephemeral OS socketpairs are allowed."""
import socket

_original={}
def pytest_sessionstart(session):
    allowed={15435,16381}
    def require(address):
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','::1','localhost') or not (address[1] in allowed or 49152<=address[1]<=65535):
            raise RuntimeError('phase3_probe_external_network_denied')
    _original.update(connect=socket.socket.connect,connect_ex=socket.socket.connect_ex,getaddrinfo=socket.getaddrinfo)
    def connect(sock,address):require(address);return _original['connect'](sock,address)
    def connect_ex(sock,address):require(address);return _original['connect_ex'](sock,address)
    def getaddrinfo(host,port,*args,**kwargs):
        require((host,int(port)));return _original['getaddrinfo'](host,port,*args,**kwargs)
    socket.socket.connect=connect;socket.socket.connect_ex=connect_ex;socket.getaddrinfo=getaddrinfo

def pytest_sessionfinish(session,exitstatus):
    if _original:
        socket.socket.connect=_original['connect'];socket.socket.connect_ex=_original['connect_ex'];socket.getaddrinfo=_original['getaddrinfo']
