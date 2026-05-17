// FloatingOnboarding.tsx

import React, {
  ReactNode,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
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

  // =========================================================
  // CONFIG AREA
  // =========================================================

  // CHANGE THIS:
  // Prevents tooltip touching viewport edges
  const VIEWPORT_PADDING = 12;

  // CHANGE THIS:
  // Move tooltip horizontally
  // positive = right
  // negative = left
  const OFFSET_X = 0;

  // CHANGE THIS:
  // Move tooltip vertically
  // positive = down
  // negative = up
  const OFFSET_Y = 0;

  // CHANGE THIS:
  // Layer priority
  const Z_INDEX = 999999;

  // CHANGE THIS:
  // Smooth movement transition
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

    // Immediate lookup
    if (findTarget()) return;

    // Watch DOM if target renders later
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

    // IMPORTANT:
    // Floating container always matches
    // target element dimensions

const targetWidth = targetRect.width;
const targetHeight = targetRect.height;

// Exact size
tooltipRef.current.style.width =
  `${targetWidth}px`;

tooltipRef.current.style.height =
  `${targetHeight}px`;

// Minimum size protection
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

    // Tooltip always centered
    // horizontally + vertically
    // relative to target element

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

    // Prevent overflow left
    if (left < VIEWPORT_PADDING) {
      left = VIEWPORT_PADDING;
    }

    // Prevent overflow right
    if (
      left + tooltipRect.width >
      window.innerWidth - VIEWPORT_PADDING
    ) {
      left =
        window.innerWidth -
        tooltipRect.width -
        VIEWPORT_PADDING;
    }

    // Prevent overflow top
    if (top < VIEWPORT_PADDING) {
      top = VIEWPORT_PADDING;
    }

    // Prevent overflow bottom
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

    // true = captures nested scrolling containers
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

    // Watches:
    // - target resizing
    // - tooltip resizing
    // - responsive layout changes

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

    // Handles:
    // - transitions
    // - animations
    // - layout shifts
    // - sidebar opening
    // - dynamic UI movement

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
  // RENDER GUARDS
  // =========================================================

  if (!mounted) return null;

  if (!show) return null;

  if (!targetElement) return null;

  // =========================================================
  // PORTAL RENDER
  // =========================================================

  return createPortal(
    <div
    className="prompt-tooltip-reference-container"
      ref={tooltipRef}
      style={{
        // IMPORTANT:
        // fixed bypasses overflow:hidden clipping
        position: "fixed",
        
        top: position.top,
        left: position.left,

        zIndex: Z_INDEX,

        // Allows tooltip interaction
        pointerEvents: "auto",

        // Better sizing behavior
        boxSizing: "border-box",

        // CHANGE THIS:
        // Optional visual debug border
        // border: "2px solid red",

        // CHANGE THIS:
        // Optional debug background
        // background: "rgba(255,0,0,0.1)",

        // CHANGE THIS:
        // Smooth repositioning
        transition: POSITION_TRANSITION,

            // Prevent mouse/touch interaction
        pointerEvents: "none",

        // Prevent text selection
        userSelect: "none",
        WebkitUserSelect: "none",

        // Disable touch behaviors
        touchAction: "none",

        // Optional (iOS Safari)
        WebkitTouchCallout: "none",


      }}
    >
      {children}
    </div>,
    document.body
  );
}