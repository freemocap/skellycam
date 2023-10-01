 // Gear icon
    Rectangle {
        id: circularBackground
        color: "#80000000" // Semi-transparent black
        width: gearIcon.width-10
        height: gearIcon.height-10
        radius: width / 2 // Makes the rectangle circular
        anchors.top: parent.top
        anchors.right: parent.right

        Text {
            id: gearIcon
            text: "⚙" // Replace with your gear emoji
            font.pixelSize: 50
            color: "white"
            anchors.centerIn: parent // Centers the text inside the rectangle
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    controlsMenu.visible = !controlsMenu.visible
                }
            }
        }
    }