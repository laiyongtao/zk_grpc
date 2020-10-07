# coding=utf-8
import contextlib
import socket
import platform

system = platform.system()


@contextlib.contextmanager
def reserve_port():

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # if system == "Windows":
    #     sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    #     if sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) == 0:
    #         raise RuntimeError("Failed to set SO_REUSEADDR.")
    # else:
    #     sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    #     if sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT) == 0:
    #         raise RuntimeError("Failed to set SO_REUSEPORT.")

    sock.bind(('0.0.0.0',0))
    try:
        port = sock.getsockname()[1]
        sock.close()
        yield port
    finally:
        sock.close()


def get_ip():
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        if s: s.close()
    return ip

if __name__ == '__main__':
    print(get_ip())

    with reserve_port() as port:
        print(port)