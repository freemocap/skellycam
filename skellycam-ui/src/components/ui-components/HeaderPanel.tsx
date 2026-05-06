import React from "react";
import ButtonSm from "./ButtonSm";
import DropdownButton from "./DropdownButton";
import { ServerConnectionStatus } from "@/components/ServerConnectionStatus";
import { EXTERNAL_URLS } from "@/constants/external-urls";

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
          text="Support FreeMoCap"
          rightSideIcon="externallink"
          textColor="text-gray"
          onClick={() => window.open(EXTERNAL_URLS.DONATE, "_blank")}
        />

        {/* Help dropdown menu */}
        <DropdownButton
          containerClassName="align-end"
          buttonProps={{
            text: "Help",
            rightSideIcon: "dropdown",
            textColor: "text-gray",
            iconClass: ""
          }}
          dropdownItems={[
            <ButtonSm
              key="Skellycam Documentation"
              rightSideIcon="externallink"
              buttonType="full-width"
              text="Skellycam Documentation"
              iconClass="learn-icon"
              onClick={() => window.open(EXTERNAL_URLS.DOCS_INTRO, "_blank")}
            />,
            <ButtonSm
              key="Ask Question on Discord"
              rightSideIcon="externallink"
              buttonType="full-width"
              text="Ask Question on Discord"
              iconClass="discord-icon"
              onClick={() => window.open(EXTERNAL_URLS.DISCORD, "_blank")}
            />,
          ]}
        />
      </div>
    </div>
  );
}
