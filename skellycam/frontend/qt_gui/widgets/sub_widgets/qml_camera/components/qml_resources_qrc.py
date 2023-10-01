# Resource object code (Python 3)
# Created by: object code
# Created by: The Resource Compiler for Qt version 6.5.2
# WARNING! All changes made in this file will be lost!

from PySide6 import QtCore

qt_resource_data = b"\
\x00\x00\x02\xfe\
 \
// Gear icon\x0d\x0a  \
  Rectangle {\x0d\x0a \
       id: circu\
larBackground\x0d\x0a \
       color: \x22#\
80000000\x22 // Sem\
i-transparent bl\
ack\x0d\x0a        wid\
th: gearIcon.wid\
th-10\x0d\x0a        h\
eight: gearIcon.\
height-10\x0d\x0a     \
   radius: width\
 / 2 // Makes th\
e rectangle circ\
ular\x0d\x0a        an\
chors.top: paren\
t.top\x0d\x0a        a\
nchors.right: pa\
rent.right\x0d\x0a\x0d\x0a  \
      Text {\x0d\x0a  \
          id: ge\
arIcon\x0d\x0a        \
    text: \x22\xe2\x9a\x99\x22 \
// Replace with \
your gear emoji\x0d\
\x0a            fon\
t.pixelSize: 50\x0d\
\x0a            col\
or: \x22white\x22\x0d\x0a   \
         anchors\
.centerIn: paren\
t // Centers the\
 text inside the\
 rectangle\x0d\x0a    \
        MouseAre\
a {\x0d\x0a           \
     anchors.fil\
l: parent\x0d\x0a     \
           onCli\
cked: {\x0d\x0a       \
             con\
trolsMenu.visibl\
e = !controlsMen\
u.visible\x0d\x0a     \
           }\x0d\x0a  \
          }\x0d\x0a   \
     }\x0d\x0a    }\
"

qt_resource_name = b"\
\x00\x05\
\x00o\xa6S\
\x00i\
\x00c\x00o\x00n\x00s\
\x00\x0c\
\x04\x16]\xdc\
\x00G\
\x00e\x00a\x00r\x00I\x00c\x00o\x00n\x00.\x00q\x00m\x00l\
"

qt_resource_struct = b"\
\x00\x00\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x01\
\x00\x00\x00\x00\x00\x00\x00\x00\
\x00\x00\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x02\
\x00\x00\x00\x00\x00\x00\x00\x00\
\x00\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\
\x00\x00\x01\x8a\xec\xf2,\xb1\
"

def qInitResources():
    QtCore.qRegisterResourceData(0x03, qt_resource_struct, qt_resource_name, qt_resource_data)

def qCleanupResources():
    QtCore.qUnregisterResourceData(0x03, qt_resource_struct, qt_resource_name, qt_resource_data)

qInitResources()
