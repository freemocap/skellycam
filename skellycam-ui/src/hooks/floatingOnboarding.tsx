// FloatingOnboarding.tsx ::::: Pooya Moradi M. 2026  <poamrd@gmail.com> :::::
/*
EXAMPLE USAGE: WITH PROMPTTOOLTIP

IMPORT BOTH
import {FloatingOnboarding} from "@/hooks/floatingOnboarding";
import PromptTooltip from "@/components/ui-components/promptTooltip";
ADD [data-onboarding="XXXXXX"] TO THE REFERENCE DOM DELEMENT TO ANCHOR TO



<FloatingOnboarding
          target='[data-onboarding="connect-cameras"]'
          
          offset={16}
        >
                    <PromptTooltip
                        show={true} // add condition when to show the prompt tooltip
                        title="Connect Cameras"
                        text="Make sure you have at least one camera plugged in, then hit Connect to start streaming."
                        position="pos-right"
                        variant="boarding"
                        onClose={() => {
                        // console.log("Tooltip closed");
                        }}
                    />
        </FloatingOnboarding>

        */

import React, {
  ReactNode,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  isValidElement,
  cloneElement,
} from "react";

import { createPortal } from "react-dom";

interface FloatingOnboardingProps {
  // CSS selector of target element
  target: string;

  // Tooltip / overlay content
  children: ReactNode;

  // Show / hide onboarding
  show?: boolean;
}

type Position = {
  top: number;
  left: number;
};

export function FloatingOnboarding({
  target,
  children,
  show = true,
}: FloatingOnboardingProps) {
  // =========================================================
  // REFS
  // =========================================================

  const tooltipRef =
    useRef<HTMLDivElement | null>(null);

  // =========================================================
  // STATE
  // =========================================================

  const [mounted, setMounted] =
    useState(false);

  const [targetElement, setTargetElement] =
    useState<HTMLElement | null>(null);

  const [position, setPosition] =
    useState<Position>({
      top: 0,
      left: 0,
    });

  // NEW:
  // Internal auto-unmount state
  const [isActive, setIsActive] =
    useState(true);

  // =========================================================
  // CONFIG AREA
  // =========================================================

  const VIEWPORT_PADDING = 12;

  const OFFSET_X = 0;

  const OFFSET_Y = 0;

  const Z_INDEX = 999999;

  const POSITION_TRANSITION =
    "top 0.01s linear, left 0.01s linear";

  // =========================================================
  // FIND TARGET ELEMENT
  // =========================================================

  useEffect(() => {
    const findTarget = () => {
      const el = document.querySelector(
        target
      ) as HTMLElement | null;

      if (el) {
        setTargetElement(el);
        return true;
      }

      return false;
    };

    if (findTarget()) return;

    const observer = new MutationObserver(
      () => {
        if (findTarget()) {
          observer.disconnect();
        }
      }
    );

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    return () => observer.disconnect();
  }, [target]);

  // =========================================================
  // MOUNTED STATE
  // =========================================================

  useEffect(() => {
    setMounted(true);
  }, []);

  // =========================================================
  // POSITION ENGINE
  // =========================================================

  const updatePosition = () => {
    if (!targetElement) return;

    if (!tooltipRef.current) return;

    // =====================================================
    // GET TARGET POSITION
    // =====================================================

    const targetRect =
      targetElement.getBoundingClientRect();

    // =====================================================
    // MATCH TARGET SIZE
    // =====================================================

    const targetWidth = targetRect.width;
    const targetHeight = targetRect.height;

    tooltipRef.current.style.width =
      `${targetWidth}px`;

    tooltipRef.current.style.height =
      `${targetHeight}px`;

    tooltipRef.current.style.minWidth =
      `${targetWidth}px`;

    tooltipRef.current.style.minHeight =
      `${targetHeight}px`;

    // =====================================================
    // GET TOOLTIP SIZE
    // =====================================================

    const tooltipRect =
      tooltipRef.current.getBoundingClientRect();

    // =====================================================
    // CENTER ALIGNMENT
    // =====================================================

    let left =
      targetRect.left +
      targetRect.width / 2 -
      tooltipRect.width / 2;

    let top =
      targetRect.top +
      targetRect.height / 2 -
      tooltipRect.height / 2;

    // =====================================================
    // OPTIONAL CUSTOM OFFSETS
    // =====================================================

    left += OFFSET_X;
    top += OFFSET_Y;

    // =====================================================
    // EDGE DETECTION
    // =====================================================

    if (left < VIEWPORT_PADDING) {
      left = VIEWPORT_PADDING;
    }

    if (
      left + tooltipRect.width >
      window.innerWidth - VIEWPORT_PADDING
    ) {
      left =
        window.innerWidth -
        tooltipRect.width -
        VIEWPORT_PADDING;
    }

    if (top < VIEWPORT_PADDING) {
      top = VIEWPORT_PADDING;
    }

    if (
      top + tooltipRect.height >
      window.innerHeight -
        VIEWPORT_PADDING
    ) {
      top =
        window.innerHeight -
        tooltipRect.height -
        VIEWPORT_PADDING;
    }

    // =====================================================
    // APPLY POSITION
    // =====================================================

    setPosition({
      top,
      left,
    });
  };

  // =========================================================
  // INITIAL POSITION
  // =========================================================

  useLayoutEffect(() => {
    updatePosition();
  }, [targetElement]);

  // =========================================================
  // AUTO UPDATE ENGINE
  // =========================================================

  useEffect(() => {
    if (!targetElement) return;

    updatePosition();

    const handleUpdate = () => {
      updatePosition();
    };

    // =====================================================
    // SCROLL LISTENER
    // =====================================================

    window.addEventListener(
      "scroll",
      handleUpdate,
      true
    );

    // =====================================================
    // WINDOW RESIZE
    // =====================================================

    window.addEventListener(
      "resize",
      handleUpdate
    );

    // =====================================================
    // RESIZE OBSERVER
    // =====================================================

    const resizeObserver =
      new ResizeObserver(() => {
        updatePosition();
      });

    resizeObserver.observe(targetElement);

    if (tooltipRef.current) {
      resizeObserver.observe(
        tooltipRef.current
      );
    }

    // =====================================================
    // RAF LOOP
    // =====================================================

    let frame = 0;

    const loop = () => {
      updatePosition();

      frame = requestAnimationFrame(loop);
    };

    frame = requestAnimationFrame(loop);

    // =====================================================
    // CLEANUP
    // =====================================================

    return () => {
      window.removeEventListener(
        "scroll",
        handleUpdate,
        true
      );

      window.removeEventListener(
        "resize",
        handleUpdate
      );

      resizeObserver.disconnect();

      cancelAnimationFrame(frame);
    };
  }, [targetElement]);

  // =========================================================
  // AUTO-INJECT UNMOUNT CALLBACK
  // =========================================================

  let content = children;

  if (isValidElement(children)) {
    content = cloneElement(
      children as React.ReactElement<any>,
      {
        __floatingOnboardingUnmount:
          () => {
            setIsActive(false);
          },
      }
    );
  }

  // =========================================================
  // RENDER GUARDS
  // =========================================================

  if (!mounted) return null;

  if (!show) return null;

  if (!targetElement) return null;

  // NEW:
  // Auto-remove container
  if (!isActive) return null;

  // =========================================================
  // PORTAL RENDER
  // =========================================================

  return createPortal(
    <div
      className="prompt-tooltip-reference-container"
      ref={tooltipRef}
      style={{
        position: "fixed",

        top: position.top,
        left: position.left,

        zIndex: Z_INDEX,

        boxSizing: "border-box",

        transition:
          POSITION_TRANSITION,

        pointerEvents: "none",

        userSelect: "none",
        WebkitUserSelect: "none",

        touchAction: "none",

        WebkitTouchCallout: "none",
      }}
    >
      {content}
    </div>,
    document.body
  );
}