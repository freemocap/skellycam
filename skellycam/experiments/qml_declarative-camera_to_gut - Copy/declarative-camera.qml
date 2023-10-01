// Copyright (C) 2017 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import QtQuick
import QtMultimedia
import "components"

Rectangle {
    id : cameraUI

    width: 800
    height: 480
    color: "black"
    state: "VideoCapture"


    states: [
        State {
            name: "VideoCapture"
            StateChangeScript {
                script: {
                    camera.start()
                }
            }
        },
        State {
            name: "VideoPreview"
            StateChangeScript {
                script: {
                    camera.stop()
                }
            }
        }
    ]

    CaptureSession {
        id: captureSession
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
        videoOutput: viewfinder
    }
    VideoPreview {
        id : videoPreview
        anchors.fill : parent
        onClosed: cameraUI.state = "VideoCapture"
        visible: (cameraUI.state === "VideoPreview")
        focus: visible

        //don't load recorded video if preview is invisible
        source: visible ? recorder.actualLocation : ""
    }

    VideoOutput {
        id: viewfinder
        visible: true
        anchors.fill: parent
        //        autoOrientation: true
    }


    VideoCaptureControls {
        id: videoControls
        state: stillControls.state
        anchors.fill: parent
        buttonsWidth: stillControls.buttonsWidth
        buttonsPanelPortraitHeight: cameraUI.buttonsPanelPortraitHeight
        buttonsPanelWidth: cameraUI.buttonsPanelLandscapeWidth
        captureSession: captureSession
        visible: (cameraUI.state === "VideoCapture")
        onPreviewSelected: cameraUI.state = "VideoPreview"
    }
}
