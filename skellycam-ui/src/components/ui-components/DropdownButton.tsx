import React, { useState, useEffect, useRef, ReactNode } from "react";
import clsx from "clsx";
import ButtonSm from "./ButtonSm";

interface DropdownButtonProps {
  buttonProps: {
    text: string;
    iconClass?: string;
    rightSideIcon?: string;
    textColor?: string;
    buttonType?: string;
    onClick?: () => void;
  };
  dropdownItems?: ReactNode;
  containerClassName?: string;
}

export default function DropdownButton({
  buttonProps,
  dropdownItems,
  containerClassName,
}: DropdownButtonProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleButtonClick = () => {
    setOpen((prev) => !prev);
    buttonProps.onClick?.();
  };

  return (
    <div
      ref={containerRef}
      className={clsx("flex flex-col z-2", containerClassName)}
    >
      <ButtonSm {...buttonProps} onClick={handleButtonClick} />

      {open && (
        <div className="reveal slide-down dropdown-container border-1 border-black bg-middark br-2 flex flex-col gap-1 p-1">
          {dropdownItems}
        </div>
      )}
    </div>
  );
}
