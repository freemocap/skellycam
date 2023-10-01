// Copyright (C) 2017 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import QtQuick
import QtMultimedia

Rectangle {
    id: cameraUI

    color: "black"
    height: 480
    state: "VideoCapture"
    width: 800

    states: [
        State {
            name: "VideoCapture"
            StateChangeScript {
                script: {
                    camera.start();
                }
            }
        },
        State {
            name: "VideoPreview"
            StateChangeScript {
                script: {
                    camera.stop();
                }
            }
        }
    ]

    CaptureSession {
        id: captureSession

        videoOutput: viewfinder

        camera: Camera {
            id: camera

        }
        imageCapture: ImageCapture {
            id: imageCapture

        }
        recorder: MediaRecorder {
            id: recorder

            //             resolution: "640x480"
            //             frameRate: 30
        }
    }
    VideoOutput {
        id: viewfinder

        anchors.fill: parent
        //        autoOrientation: true
        visible: True
    }

}
