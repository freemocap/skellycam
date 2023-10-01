// Copyright (C) 2017 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import QtQuick
import QtMultimedia
import "components/icons" as Icons

Rectangle {
    id: cameraUI
    color: "black"
    height: 480
    width: 800

    CaptureSession {
        id: captureSession

        videoOutput: viewfinder

        camera: Camera {
            id: camera
            Component.onCompleted: camera.start() // Starts the camera once the component is completed
        }
        imageCapture: ImageCapture {
            id: imageCapture
        }
        recorder: MediaRecorder {
            id: recorder
        }
    }

    VideoOutput {
        id: viewfinder
        anchors.fill: parent
        visible: True
    }

    Icons.GearIcon {
        anchors.top: parent.top
        anchors.right: parent.right
    }

    // Controls menu
    Rectangle {
        id: controlsMenu
        color: "lightgrey"
        width: parent.width / 3
        height: parent.height / 2
        anchors.top: parent.top
        anchors.right: parent.right
        visible: false

        // Control Camera Exposure

    }
}