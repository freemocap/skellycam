import QtQuick 2.15
import QtMultimedia 5.15
import QtQuick.Controls 2.15

ApplicationWindow {
    visible: true
    width: 640
    height: 480
    title: "QML Camera"

    Camera {
        id: camera
    }

    VideoOutput {
        anchors.fill: parent
        source: camera
        focus : visible // to receive focus and capture key events when visible
    }

    Button {
        text: camera.recording ? "Stop Recording" : "Start Recording"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        onClicked: camera.recording ? camera.stop() : camera.start()
    }
}