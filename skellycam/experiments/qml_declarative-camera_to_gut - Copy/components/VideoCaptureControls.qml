// Copyright (C) 2017 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import QtQuick
import QtMultimedia
import QtQuick.Layouts

FocusScope {
    id : captureControls
    property CaptureSession captureSession
    property bool previewAvailable : false

    property int buttonsmargin: 4
    property int buttonsPanelWidth
    property int buttonsPanelPortraitHeight
    property int buttonsWidth

    signal previewSelected
    signal photoModeSelected

    Rectangle {
        id: buttonPaneShadow
        color: Qt.rgba(0.8, 0.08, 0.08, 1)

        GridLayout {
            id: bottomColumn
            anchors.margins: buttonsmargin

            CameraListButton {
                implicitWidth: buttonsWidth
                onValueChanged: captureSession.camera.cameraDevice = value
                state: captureControls.state
            }


        }
    }

}
