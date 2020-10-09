import os
from setuptools import setup, find_packages

DIR = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(DIR, "README.md")) as f:
    long_desc = f.read()

desc = '''a zookeeper registration center manager for python grpcio'''


setup(
    name="zk-grpc",
    version="0.1.0",
    author="laiyongtao",
    author_email="laiyongtao6908@163.com",
    url="https://github.com/laiyongtao/zk_grpc" ,
    license="MIT License",
    description=desc,
    long_description=long_desc,
    long_description_content_type="text/markdown",
    platforms="all",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    keywords = ("grpc", "zookeeper", "kazoo", "registration", "discovery"),
    packages=find_packages(exclude=["example"]),
    install_requires=[
        "grpcio",
        "kazoo",
    ],
    python_requires=">3.5.*, <4",
)
