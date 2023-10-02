// Copyright (C) 2017 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import QtQuick
import QtMultimedia
import "components"

Rectangle {
    id: cameraUI

    color: "black"
    height: 480
    width: 800

    Component.onCompleted: camera.start()

    CaptureSession {
        id: captureSession
        videoOutput: viewfinder

        camera: Camera {
            id: camera
        }
    }
    VideoOutput {
        id: viewfinder
        anchors.fill: parent
        visible: true
    }
}
