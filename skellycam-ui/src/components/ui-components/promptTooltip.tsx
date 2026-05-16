import React, { useEffect, useState } from "react";
import clsx from "clsx";

// COMPONENTS
import IconButton from "./IconButton";
import ButtonSm from "./ButtonSm";

type TooltipPosition =
  | "pos-top"
  | "pos-bottom"
  | "pos-left"
  | "pos-right";

type TooltipVariant =
  | "default"
  | "warning"
  | "boarding";

interface PromptTooltipProps {
  show?: boolean;

  // CONTENT
  title?: string;
  text: string;

  // IMAGE
  image?: boolean;
  imageSrc?: string;

  // BUTTON
  button?: boolean;
  buttonText?: string;
  buttonType?: string;
  buttonIcon?: string;
  onButtonClick?: () => void;

  // CLOSE
  onClose?: () => void;

  // STYLING
  position?: TooltipPosition;
  variant?: TooltipVariant;
  className?: string;
  innerClassName?: string;
}

const PromptTooltip: React.FC<PromptTooltipProps> = ({
  show = false,

  // CONTENT
  title = "",
  text,

  // IMAGE
  image = false,
  imageSrc = "",

  // BUTTON
  button = false,
  buttonText = "Continue",
  buttonType = "",
  buttonIcon = "",
  onButtonClick = () => {},

  // CLOSE
  onClose = () => {},

  // STYLING
  position = "pos-right",
  variant = "default",
  className = "",
  innerClassName = "",
}) => {
  /**
   * =========================================
   * INTERNAL VISIBILITY STATE
   * =========================================
   */

  const [isVisible, setIsVisible] = useState(show);

  useEffect(() => {
    setIsVisible(show);
  }, [show]);

  if (!isVisible) return null;

  const variantClasses = {
    default: "border-gray800",
    warning: "border-red",
    boarding: "border-blue",
  };

  /**
   * =========================================
   * CLOSE HANDLER
   * =========================================
   */

  const handleClose = () => {
    setIsVisible(false);
    onClose();
  };

  return (
    <div
      className={clsx(
        "prompt-tooltip-container text-wrap border-1 border-solid border-mid-black tooltip-container elevated-sharp",
        position,
        "p-01 br-3 bg-dark",
        className
      )}
    >
      <div
        className={clsx(
          "tooltip-inner",
          "gap-2",
          "flex",
          "flex-col",
          "pos-rel",
          "br-2",
          "border-1 border-solid",
          "p-2",
          variantClasses[variant],
          innerClassName
        )}
      >
        {/* CLOSE BUTTON */}
        <div className="icon-button-holder flex flex-row pos-abs top-0 right-0 z-2">
          <IconButton
            icon="close-icon"
            onClick={handleClose}
          />
        </div>

        {/* TITLE */}
        {title && (
          <div className="tooltip-title-holder flex flex-row pos-rel">
            <h3 className="text-white text lg mb-2">
              {title}
            </h3>
          </div>
        )}

        {/* IMAGE */}
        {image && imageSrc && (
          <div className="tooltip-image-holder br-1 overflow-hidden flex flex-row pos-rel">
            <div className="image-container width-200 height-80 overflow-hidden flex flex-row pos-rel">
              <img
                src={imageSrc}
                className="object-contain width-full height-full"
              />
            </div>
          </div>
        )}

        {/* TEXT */}
        <div className="tooltip-description-holder flex flex-row pos-rel">
          <p className="text-white text md">
            {text}
          </p>
        </div>

        {/* BUTTON */}
        {button && (
          <div className="tooltip-button-holder flex flex-row flex-1 items-center gap-1 fit-content w-full min-w-full">
            <ButtonSm
              text={buttonText}
              iconClass={buttonIcon}
              buttonType={buttonType}
              onClick={onButtonClick}
              className="flex-1 full-width flex-inline text-left items-center full-width justify-center"
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default PromptTooltip;