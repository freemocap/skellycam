import { Panel } from "react-resizable-panels";
import React from "react";
import {LeftSidebarDrawer} from "@/components/ui-components/LeftSidebarDrawer";

export const LeftSidePanel = () => {
    return (
        <Panel collapsible defaultSize={20} minSize={10} collapsedSize={4}>
            left side
            {/*<LeftSidebarDrawer/>*/}
        </Panel>
    );
};
