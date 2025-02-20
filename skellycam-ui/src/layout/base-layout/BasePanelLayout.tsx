import React from "react"
import {PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {MainContentPanel} from "@/layout/base-layout/sub-panels/MainContentPanel";
import {LeftSidePanel} from "@/layout/base-layout/sub-panels/LeftSidePanel";
import {BottomPanel} from "@/layout/base-layout/sub-panels/BottomPanel";
import {paperbaseTheme} from "@/layout/base-content/paperbase_theme/paperbase-theme"; // Import theme

import { css } from '@emotion/react'


export const BasePanelLayout = ({children}: { children: React.ReactNode }) => {
    return (
        <PanelGroup
            direction="vertical"
            autoSaveId="skellycam-panel-group"
            style={{height: "100vh", width: "100vw"}}
        >
            <PanelGroup direction="horizontal">
                <LeftSidePanel/>
                {/* Horizontal Resize Handle */}
                <PanelResizeHandle
                    style={{
                        width: "4px",
                        cursor: "col-resize",
                        backgroundColor: paperbaseTheme.palette.primary.light,
                        transition: "background-color 0.2s ease",
                        // "&:hover": {
                        //     backgroundColor: paperbaseTheme.palette.secondary.main
                        // }
                    }}
                />
                <MainContentPanel>
                    {children}
                </MainContentPanel>
            </PanelGroup>

            {/* Vertical Resize Handle */}
            <PanelResizeHandle
                style={{
                    height: "4px",
                    cursor: "row-resize",
                    backgroundColor: paperbaseTheme.palette.primary.light,
                    transition: "background-color 0.2s ease",
                    // ":hover": {
                    //     backgroundColor: paperbaseTheme.palette.secondary.main
                    // }
                }}
            />
            <BottomPanel/>
        </PanelGroup>
    )
}
