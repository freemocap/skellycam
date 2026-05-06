// skellycam-ui/src/components/ui-components/BottomPanelContent.tsx
import React from 'react';
import {LogTerminal} from "@/components/LogTerminal";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import FramerateViewerPanel from "@/components/framerate-viewer/FrameRateViewer";

export default function BottomPanelContent() {
    return (
        <div className="bottom-info-container border-1 border-black br-2 flex h-full overflow-hidden">
            <PanelGroup direction="horizontal" style={{direction: "ltr"}}>
                <Panel defaultSize={30} minSize={15}>
                    <FramerateViewerPanel />
                </Panel>

                <PanelResizeHandle className="info-panel-divider" />

                <Panel defaultSize={70} minSize={20}>
                    <LogTerminal />
                </Panel>
            </PanelGroup>
        </div>
    );
}
