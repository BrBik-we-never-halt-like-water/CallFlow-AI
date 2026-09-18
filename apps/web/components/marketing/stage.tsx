"use client";

import { useSpring, useTransform, motion, type MotionValue } from "framer-motion";
import { useMediaQuery, usePrefersReducedMotion } from "@/lib/hooks/use-external-store";
import { cn } from "@/lib/cn";

/**
 * CSS-perspective staging for the marketing scenes.
 *
 * A `Stage` is the camera; the object inside it holds a rest pose (a static
 * tilt - still an image, so it survives reduced motion) and, on fine pointers
 * only, leans a few degrees toward the cursor. The lean is a spring, so it
 * settles rather than tracks - an instrument being glanced at, not a card
 * being dragged.
 *
 * Depth inside the object comes from `StageLayer`: plain translateZ against
 * the shared `--stage-perspective`, so the same depth reads the same distance
 * everywhere on the page.
 */

/** translateZ per depth level. 3 is the object plane; below sit behind it. */
const DEPTH_Z: Record<0 | 1 | 2 | 3 | 4 | 5, number> = {
  0: -110,
  1: -60,
  2: -24,
  3: 0,
  4: 34,
  5: 64,
};

export function useStageTilt({
  maxX = 3.5,
  maxY = 4.5,
}: { maxX?: number; maxY?: number } = {}): {
  enabled: boolean;
  rotateX: MotionValue<number>;
  rotateY: MotionValue<number>;
  onPointerMove: (e: React.PointerEvent<HTMLElement>) => void;
  onPointerLeave: () => void;
} {
  const reduced = usePrefersReducedMotion();
  const fine = useMediaQuery("(pointer: fine)");
  const enabled = fine && !reduced;

  // Springs around 0; the rest pose is added by the caller so the same hook
  // serves any scene regardless of its base angle.
  const rotateX = useSpring(0, { stiffness: 60, damping: 18, mass: 0.6 });
  const rotateY = useSpring(0, { stiffness: 60, damping: 18, mass: 0.6 });

  const onPointerMove = (e: React.PointerEvent<HTMLElement>) => {
    if (!enabled) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    // Pointer below centre tips the top toward the viewer: negative px/py map
    // to positive rotation the way a physical panel would give under a finger.
    rotateX.set(-py * 2 * maxX);
    rotateY.set(px * 2 * maxY);
  };

  const onPointerLeave = () => {
    rotateX.set(0);
    rotateY.set(0);
  };

  return { enabled, rotateX, rotateY, onPointerMove, onPointerLeave };
}

export function Stage({
  restX = 0,
  restY = 0,
  tilt = true,
  className,
  objectClassName,
  children,
}: {
  /** Rest pose in degrees - the pose the scene holds with nobody touching it. */
  restX?: number;
  restY?: number;
  /** Lean toward the pointer on fine-pointer devices. */
  tilt?: boolean;
  className?: string;
  objectClassName?: string;
  children: React.ReactNode;
}) {
  const { enabled, rotateX, rotateY, onPointerMove, onPointerLeave } = useStageTilt();

  const posedX = useTransform(() => restX + rotateX.get());
  const posedY = useTransform(() => restY + rotateY.get());

  return (
    <div
      className={cn("stage", className)}
      onPointerMove={tilt && enabled ? onPointerMove : undefined}
      onPointerLeave={tilt && enabled ? onPointerLeave : undefined}
    >
      <motion.div
        className={cn("stage-object", objectClassName)}
        style={{ rotateX: posedX, rotateY: posedY }}
      >
        {children}
      </motion.div>
    </div>
  );
}

/**
 * One depth plane inside a `Stage`'s object.
 *
 * `float` wraps the content in its own animating element rather than
 * animating this one - a keyframe transform on the same element would
 * overwrite the depth transform.
 */
export function StageLayer({
  depth,
  float = false,
  floatLate = false,
  className,
  children,
  ...props
}: {
  depth: 0 | 1 | 2 | 3 | 4 | 5;
  float?: boolean;
  floatLate?: boolean;
  className?: string;
  children: React.ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) {
  const content = float ? (
    <div className={cn("stage-float", floatLate && "stage-float-late")}>{children}</div>
  ) : (
    children
  );

  return (
    <div
      className={className}
      style={{ transform: `translateZ(${DEPTH_Z[depth]}px)` }}
      {...props}
    >
      {content}
    </div>
  );
}
