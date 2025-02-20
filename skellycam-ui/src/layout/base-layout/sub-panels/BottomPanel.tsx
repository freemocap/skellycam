import { Panel } from "react-resizable-panels";
import React from "react";
import {Typography} from "@mui/material";
import {TerminalDrawer} from "@/components/ui-components/TerminalDrawer";

export const BottomPanel = () => {
    return (
        <Panel collapsible defaultSize={20} minSize={10} collapsedSize={4}>
            {/*<TerminalDrawer/>*/}
            bottom panel
        </Panel>
    );
};
