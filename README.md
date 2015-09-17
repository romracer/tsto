The Simpsons Tapped Out tool
====

Installation

- install Python;
- install Google protobuf (protoc tool);
- install Google protobuf library for Python (using pip for example).

Prepare your version of LandData_pb2.py (or use from repo)

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

Supported commands

login email pass     - login origin account
download             - download LandMessage
showtimes            - show some times variables from LandMessage
friends              - show friends info
friendsdrop days=90  - drop friends who not playing more then given amount
frienddrop ORIGINID  - drop friend by its Origin id
resetnotif           - clear neighbor handshakes
protocurrency        - show ProtoCurrency information
upload               - upload current LandMessage to mayhem server
uploadextra          - upload current ExtraLandMessage to mayhem server
config               - show current game config variables

tokenstore           - store current logined token in home dir
tokenlogin           - login by token stored in file in home dir

load filepath        - load LandMessage from local filepath
save filepath        - save LandMessage to local filepath
astext               - save LandMessage text representation into file

vs name[,name] val   - set variable(s) to value
vars [name[,name]]   - print variables with given names or all
donuts count         - set donuts for logined acc to count
ia ids type count=1  - add item(s) with id and type into inventory
ic id type count     - set count item with id and type
spendable id count   - set count spendable with id
money count          - set money count
skins 1,2,3          - set skins to (see: skinsmasterlist.xml)
setlevel level       - set current level (be careful)
qc id                - complete quest with id
quests               - show not completed quests
hurry                - done all jobs and rewards
bm id x y flip       - set positions for all buildings with id
cleanr               - clear roads, rivers, broadwalk
cleandebris          - clean debris in subland 1 and 2
std email pass       - execute std routines for acc
help                 - this message
quit                 - exit