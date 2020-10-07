# coding=utf-8
import signal
import functools

import asyncio
from example_pb2 import HelloRequest, HelloResponse
from example_pb2_grpc import HelloServiceServicer, add_HelloServiceServicer_to_server

from kazoo.client import KazooClient
from zk_grpc.aio import AIOZKRegister


class HelloService(HelloServiceServicer):

    async def hello_world(self, request: HelloRequest, context):
        hello = request.hello
        return HelloResponse(hello=hello)


async def run(host, port):

    from grpc.experimental.aio import server
    from concurrent.futures import ThreadPoolExecutor
    server = server(ThreadPoolExecutor(50))
    add_HelloServiceServicer_to_server(HelloService(), server)

    server.add_insecure_port("{}:{}".format(host, port))
    await server.start()

    kz = KazooClient(hosts="127.0.0.1:2181")
    kz.start()

    zk_register = AIOZKRegister(kz_client=kz)

    await zk_register.register_server(HelloServiceServicer, host, port)

    async def shutdown(*args, **kwargs):
        await zk_register.stop()
        # close kazoo client after zk_register stoped
        kz.stop()
        kz.close()

        await server.stop(0.5)

    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM,
                                                functools.partial(asyncio.ensure_future, shutdown()))

    await server.wait_for_termination()


if __name__ == '__main__':

    host = "127.0.0.1"
    from socket_util import reserve_port
    with reserve_port() as port:
        asyncio.run(run(host, port))
