import React from "react"
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {paperbaseTheme} from "@/layout/paperbase_theme/paperbase-theme";
import {LeftSidePanelContent} from "@/components/ui-components/LeftSidePanelContent";
import { TerminalPanelContent } from "@/components/ui-components/TerminalPanelContent";

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
                    <Panel collapsible defaultSize={20} minSize={10} collapsedSize={4}>
                        <LeftSidePanelContent/>
                    </Panel>
                    {/* Horizontal Resize Handle
                    - like meaning the line is vertical and it lets you
                     resize the horizontal size of the panel */}
                    <PanelResizeHandle
                        style={{
                            width: "4px",
                            cursor: "col-resize",
                            backgroundColor: paperbaseTheme.palette.primary.light,
                        }}
                    />

                    {/*Main/Central Content Panel*/}
                    <Panel defaultSize={50} minSize={10}>
                        {children}
                    </Panel>
                </PanelGroup>
            </Panel>

            {/* Vertical Resize Handle  - like meaning the line is horizontal
            and it lets you resize the vertical size of the panel */}
            <PanelResizeHandle
                style={{
                    height: "4px",
                    cursor: "row-resize",
                    backgroundColor: paperbaseTheme.palette.primary.light,

                }}
            />


            <Panel collapsible defaultSize={20} minSize={10} collapsedSize={4}>
                <TerminalPanelContent/>
            </Panel>
        </PanelGroup>
    )
}
