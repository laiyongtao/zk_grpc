# zk_grpc
a zookeeper registration center manager for python grpcio 

Requires: Python 3.5, grpcio, kazoo
### install
```shell
pip install zk-grpc
```
####How to update 0.0.1 to 0.1.0
```text
1. Update the Client server which use with ZKGrpc or AIOZKGrpc to v0.1.0 zk-grpc first.
2. Then update the server which use with ZKRegister or AIOZKRegister.
```
**Notice: Can not use V0.0.1 ZKGrpc class with v0.1.0 ZKRegister class**

##### [More Eaxmples](https://github.com/laiyongtao/zk_grpc/tree/master/example)

## Service Register
```python
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
```
## Service Discovery
```python
from example_pb2 import HelloRequest
from example_pb2_grpc import HelloServiceStub
from kazoo.client import KazooClient
from zk_grpc import ZKGrpc

def run():
    # before useing
    kz = KazooClient(hosts="127.0.0.1:2181")
    kz.start()

    zk_g = ZKGrpc(kz_client=kz)

    # get stub
    stub = zk_g.wrap_stub(HelloServiceStub)

    # call grpc api
    resp = stub.hello_world(HelloRequest(hello="hello"))
    print(resp.hello)

    # before exit
    zk_g.stop()
    kz.stop()
    kz.close()

if __name__ == '__main__':
    run()
```