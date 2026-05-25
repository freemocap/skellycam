import React from "react";
import clsx from "clsx";

/**
 * =========================================
 * ICON BUTTON COMPONENT
 * =========================================
 *
 * Reusable icon-only button component with:
 *
 * - Dynamic icon support
 * - Click handling
 * - Disabled state
 * - Tooltip system
 * - Tooltip position support
 * - Custom className support
 *
 * -----------------------------------------
 * BASIC USAGE
 * -----------------------------------------
 *
 * <IconButton
 *   icon="close-icon"
 *   onClick={onClose}
 * />
 *
 * -----------------------------------------
 * DIFFERENT ICONS
 * -----------------------------------------
 *
 * <IconButton
 *   icon="copy-icon"
 * />
 *
 * <IconButton
 *   icon="trash-icon"
 * />
 *
 * -----------------------------------------
 * TOOLTIP USAGE
 * -----------------------------------------
 *
 * <IconButton
 *   icon="copy-icon"
 *   tooltip={true}
 *   tooltipText="Copy to clipboard"
 * />
 *
 * -----------------------------------------
 * TOOLTIP POSITIONS
 * -----------------------------------------
 *
 * - pos-bottom (default)
 * - pos-top
 * - pos-left
 * - pos-right
 *
 * -----------------------------------------
 * FULL EXAMPLE
 * -----------------------------------------
 *
 * <IconButton
 *   icon="close-icon"
 *   onClick={onClose}
 *   tooltip={true}
 *   tooltipText="Close modal"
 *   tooltipPosition="pos-left"
 * />
 *
 * =========================================
 */

type TooltipPosition =
  | "pos-top"
  | "pos-bottom"
  | "pos-left"
  | "pos-right";

interface IconButtonProps {
  icon: string;
  onClick?: () => void;
  onMouseDown?: (e: React.MouseEvent) => void;
  disabled?: boolean;
  title?: string;
  className?: string;
  iconSize?: string;

  // TOOLTIP
  tooltip?: boolean;
  tooltipText?: string;
  tooltipPosition?: TooltipPosition;
}

const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(({
  icon,
  onClick = () => {},
  onMouseDown,
  disabled = false,
  title,
  className = "icon-size-28",
  iconSize = "icon-size-20",

  // TOOLTIP
  tooltip = false,
  tooltipText = "",
  tooltipPosition = "pos-bottom",
}, ref) => {
  return (
    <button
      ref={ref}
      onClick={onClick}
      onMouseDown={onMouseDown}
      disabled={disabled}
      title={title}
      className={clsx(
        "button icon-button pos-rel br-1",
        className
      )}
    >
      {/* ICON */}
      <span
        className={clsx(
          "icon",
          icon,
          iconSize
        )}
      />

      {/* TOOLTIP */}
      {tooltip && tooltipText && (
        <div
          className={clsx(
            "tooltip-container elevated-sharp",
            tooltipPosition,
            "p-01 br-2 bg-dark"
          )}
        >
          <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid">
            <p className="text-white text md">
              {tooltipText}
            </p>
          </div>
        </div>
      )}
    </button>
  );
});

export default IconButton;