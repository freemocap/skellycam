// Copyright (C) 2017 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

import QtQuick
import QtMultimedia
import "components"

Rectangle {
    id: singleCamera

    color: "black"
    height: 480
    width: 800
    function updateImage(imageFromPython) {
        qmlImage.image = imageFromPython
    }
    Image {
        id: qmlImage

        // set initial width and height
        width: parent.width
        height: parent.height

        // bind sourceSize to size to avoid unnecessary image scaling
        sourceSize.width: width
        sourceSize.height: height
    }
}
