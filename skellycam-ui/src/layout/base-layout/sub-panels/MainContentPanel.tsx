// components/ui-components/MainContentPanel.tsx
import React from "react";
import { Panel } from "react-resizable-panels";

export const MainContentPanel = ({ children }: { children: React.ReactNode }) => {
    return (
        <Panel defaultSize={50} minSize={10}>
            {/*{children}*/}
            main window
        </Panel>
    );
};
