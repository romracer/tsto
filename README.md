The Simpsons Tapped Out tool
====

Installation

- install Python;
- install libraries requests and protobuf for Python (using pip for example);
- install protobuf (protoc tool).

Prepare LandData_pb2.py

    protoc --python_out=. LandData.proto

Usage examples

List of supported commands:

    python tsto.py
    help
    quit

Add 1000 donuts to your account email@host.com:

    python tsto.py
    login email@host.com password
    download
    donuts 1000
    upload
    quit

Store your town status into ./land.backup file:

    python tsto.py
    login email@host.com password
    download
    save land.backup
    quit

Add 100 squidport tiles(5000), 999 golden scratchers (44), 999 buddah (9):

    python tsto.py
    login email@host.com password
    download
    ia 5000 2 100
    ia 44 2 999
    ia 9 2 999
    upload
    quit
