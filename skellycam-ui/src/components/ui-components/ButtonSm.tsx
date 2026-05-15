import React from "react";
import clsx from "clsx";

interface ButtonSmProps {
  iconClass?: string;
  buttonType?: string;
  text: string;
  onClick?: () => void;
  rightSideIcon?: string;
  textColor?: string;
  title?: string;
  disabled?: boolean;
  className?: string; // <-- new prop for extra classes
}

const ButtonSm: React.FC<ButtonSmProps> = ({
  iconClass = "",
  buttonType = "",
  text,
  onClick = () => {},
  rightSideIcon = "",
  textColor = "text-gray",
  title,
  disabled = false,
  className = "", // <-- default empty
}) => {
  return (
    <button
      onClick={onClick}
      title={title}
      disabled={disabled}
      className={clsx(
        "gap-1 br-1 button sm fit-content flex-inline text-left items-center", // base styles
        buttonType, // existing classes
        rightSideIcon, // existing icon-based classes (can leave as is)
        className // <-- new extra classes
      )}
    >
      {/* LEFT ICON */}
      {iconClass && <span className={clsx("icon icon-size-16", iconClass)} />}

      {/* TEXT */}
      <p className={clsx(textColor, "text-nowrap text md text-align-left")}>
        {text}
      </p>
    </button>
  );
};

export default ButtonSm;