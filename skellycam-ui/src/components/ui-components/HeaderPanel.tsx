import React from "react";
import ButtonSm from "./ButtonSm";
import DropdownButton from "./DropdownButton";
import { ServerConnectionStatus } from "@/components/ServerConnectionStatus";

/**
 * HeaderPanel Component
 *
 * ✅ Extracted from App.tsx for cleaner structure.
 *
 * 🔧 Future Developers:
 * - Place ALL top navigation / HeaderPanel-related components here.
 * - If you add more global buttons or menus (e.g., Settings, Profile),
 *   this is the right place.
 * - Keep logic/stateless UI in HeaderPanel. State management should stay in App or higher contexts.
 */
export default function HeaderPanel() {
  return (
    <div className="header-panel flex flex-row justify-content-space-between top-header br-2 h-25">
      <div className="flex left-section">
        {/* Connection status dropdown (wired to real server/websocket logic) */}
        <ServerConnectionStatus />
      </div>

      <div className="flex right-section gap-2">
        {/* Support button */}
        <ButtonSm
          iconClass="donate-icon"
          text="Support the freemocap"
          rightSideIcon="externallink"
          textColor="text-gray"
          onClick={() => {
            console.log("Support freemocap clicked");
          }}
        />

        {/* Help dropdown menu */}
        <DropdownButton
          containerClassName="align-end"
          buttonProps={{
            text: "Help",
            rightSideIcon: "dropdown",
            textColor: "text-gray",
            iconClass: "",
            onClick: () => console.log("help dropdown button clicked"),
          }}
          dropdownItems={[
            <ButtonSm
              key="FreeMocap Guide"
              rightSideIcon="externallink"
              buttonType="full-width"
              text="FreeMocap Guide"
              iconClass="learn-icon"
              onClick={() => console.log("FreeMocap Guide clicked")}
            />,
            <ButtonSm
              key="Ask Question on Discord"
              rightSideIcon="externallink"
              buttonType="full-width"
              text="Ask Question on Discord"
              iconClass="discord-icon"
              onClick={() => console.log("Ask Question on Discord clicked")}
            />,
            <ButtonSm
              key="tutorials"
              buttonType="full-width"
              text="Download Sample Videos"
              iconClass="download-icon"
              onClick={() => console.log("Download Sample Videos clicked")}
            />,
          ]}
        />
      </div>
    </div>
  );
}
