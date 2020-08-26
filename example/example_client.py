# coding=utf-8
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