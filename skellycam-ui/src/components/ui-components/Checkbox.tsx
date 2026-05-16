import React from "react";

/**
 * Reusable Checkbox Component
 * ----------------------------
 * - Combines a native <input type="checkbox"> with a text label (<p> tag).
 * - Use the `label` prop to change the string next to the checkbox.
 * - `checked` + `onChange` make this component controllable from parent state.
 * - The entire container is clickable to toggle the checkbox.
 * - `inputClassName` allows adding extra classes to the <input> without breaking existing styles.
 */

interface CheckboxProps {
  label: string; // text shown next to the checkbox
  checked?: boolean; // optional controlled state
  onChange?: (event: React.ChangeEvent<HTMLInputElement>) => void; // handler for state changes
  inputClassName?: string; // extra classes to add to the <input>
}

const Checkbox: React.FC<CheckboxProps> = ({
  label,
  checked,
  onChange,
  inputClassName = "", // default to empty string
}) => {
  const handleContainerClick = (e: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    if (onChange) {
      // Create a synthetic event with the toggled checked state
      const syntheticEvent = {
        ...e,
        target: {
          ...e.target,
          checked: !checked,
        },
      } as React.ChangeEvent<HTMLInputElement>;
      onChange(syntheticEvent);
    }
  };

  return (
    <div
      className="text-nowrap button checkbox gap-1 flex flex-row items-center p-2"
      onClick={handleContainerClick}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className={`button ${inputClassName}`.trim()} // merge default + extra classes
      />
      <p className="text-gray text sm text-align-left">{label}</p>
    </div>
  );
};

export default Checkbox;