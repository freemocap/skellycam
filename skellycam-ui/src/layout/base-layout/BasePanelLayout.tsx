import React from "react"
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {MainContentPanel} from "@/layout/base-layout/sub-panels/MainContentPanel";
import {LeftSidePanel} from "@/layout/base-layout/sub-panels/LeftSidePanel";
import {BottomPanel} from "@/layout/base-layout/sub-panels/BottomPanel";
import {paperbaseTheme} from "@/layout/base-content/paperbase_theme/paperbase-theme";


export const BasePanelLayout = ({children}: { children: React.ReactNode }) => {
    return (
        <PanelGroup
            direction="vertical"
            autoSaveId="skellycam-panel-group"
            style={{height: "100vh", width: "100vw"}}
        >
            {/* Top section (horizontal panels) - 80% height */}
            <Panel defaultSize={80} minSize={20}>
                <PanelGroup direction="horizontal">
                    <LeftSidePanel/>
                    {/* Horizontal Resize Handle
                    - like meaning the line is vertical and it lets you
                     resize the horizontal size of the panel */}
                    <PanelResizeHandle
                        style={{
                            width: "4px",
                            cursor: "col-resize",
                            backgroundColor: paperbaseTheme.palette.primary.light,
                            // transition: "background-color 0.2s ease",
                            // "&:hover": {
                            //     backgroundColor: paperbaseTheme.palette.secondary.main
                            // }
                        }}
                    />
                    <MainContentPanel>
                        {children}
                    </MainContentPanel>
                </PanelGroup>
            </Panel>
            {/* Vertical Resize Handle  - like meaning the line is horizontal
            and it lets you resize the vertical size of the panel */}
            <PanelResizeHandle
                style={{
                    height: "4px",
                    cursor: "row-resize",
                    backgroundColor: paperbaseTheme.palette.primary.light,
                    // transition: "background-color 0.2s ease",
                    // ":hover": {
                    //     backgroundColor: paperbaseTheme.palette.secondary.main
                    // }
                }}
            />
            {/* Bottom section - 20% height */}
            <Panel collapsible defaultSize={20} minSize={10} collapsedSize={4}>
                <BottomPanel/>
            </Panel>
        </PanelGroup>
    )
}
