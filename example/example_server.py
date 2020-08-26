# coding=utf-8
import signal
from example_pb2 import HelloRequest, HelloResponse
from example_pb2_grpc import HelloServiceServicer, add_HelloServiceServicer_to_server

from kazoo.client import KazooClient
from zk_grpc import ZKRegister


class HelloService(HelloServiceServicer):

    def hello_world(self, request: HelloRequest, context):
        hello = request.hello
        return HelloResponse(hello=hello)


def run(host, port):

    from grpc import server
    from concurrent.futures import ThreadPoolExecutor

    server = server(ThreadPoolExecutor(50))
    add_HelloServiceServicer_to_server(HelloService(), server)

    server.add_insecure_port("{}:{}".format(host, port))
    server.start()


    kz = KazooClient(hosts="127.0.0.1:2181")
    kz.start()

    zk_register = ZKRegister(kz_client=kz)
    # register all servicers on gprc server obj, do not support aio grpc server
    zk_register.register_grpc_server(server, host, port)
    # or register servicer one by one
    # zk_register.register_server(HelloServiceServicer, host, port)

    def shutdown(*args, **kwargs):
        zk_register.stop()
        # close kazoo client after zk_register stoped
        kz.stop()
        kz.close()

        server.stop(0.5)

    signal.signal(signal.SIGTERM, shutdown)

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        shutdown()



if __name__ == '__main__':

    host = "127.0.0.1"
    port = 50052
    run(host, port)
