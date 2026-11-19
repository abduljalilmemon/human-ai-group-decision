import { createContext, useContext, useId, useMemo, useRef, type CSSProperties, type ReactNode } from "react";
import { ANIMALS, SPARK_PATHS, dealAnimals, type AnimalKey } from "./animals";

// label -> animal for the current session. Dealt from the server's avatar_seed and the label list only.
const DealContext = createContext<Record<string, AnimalKey>>({});

export function AvatarDeal({ seed, labels, children }: { seed: string | null; labels: string[]; children: ReactNode }) {
  const key = labels.join("|"); // a new array with the same labels must not re-deal
  const deal = useMemo(() => dealAnimals(seed ?? "", key ? key.split("|") : []), [seed, key]);
  return <DealContext.Provider value={deal}>{children}</DealContext.Provider>;
}

const SIZE_PX = { sm: 28, md: 48, lg: 60, xl: 96 } as const;
type Size = keyof typeof SIZE_PX;

// Size alone decides how much animates (small avatars in lists stay calm), never the animal or the player.
const FULL_MOTION: Record<Size, boolean> = { sm: false, md: true, lg: true, xl: true };
const SPARK_ANGLES = [0, 120, 240];

interface Props {
  label: string;
  size?: Size;
  /** Changes when this player's message is delivered: the aura flares and a ring pulses once. */
  pulseKey?: number;
}

/**
 * A player's animal badge. Every animal uses the same markup, animation classes and timing.
 * The art is static trusted SVG from animals.ts; no user text is ever put into it.
 */
export function Avatar({ label, size = "sm", pulseKey }: Props) {
  const deal = useContext(DealContext);
  const animal = ANIMALS[deal[label] ?? "owl"];
  // useId gives ":r1:"; keep only characters that are safe inside url(#...).
  const gradId = useId().replace(/[^a-zA-Z0-9]/g, "");
  const art = useMemo(() => ({ __html: animal.art(gradId) }), [animal, gradId]);
  // Only deliveries after mount pulse, so opening a screen or a replay does not flash.
  const firstKey = useRef(pulseKey);
  const pulsing = pulseKey !== undefined && pulseKey !== firstKey.current;
  const full = FULL_MOTION[size];

  return (
    <span
      role="img"
      aria-label={`${label} avatar`}
      className="avatar"
      style={{ "--avatar-size": `${SIZE_PX[size]}px`, "--animal": animal.color } as CSSProperties}
    >
      {full && <span aria-hidden className="avatar-aura" />}
      {pulsing && <span aria-hidden key={`f${pulseKey}`} className="avatar-flare" />}
      {pulsing && <span aria-hidden key={`r${pulseKey}`} className="avatar-ring" />}
      {full && (
        <span aria-hidden className="avatar-orbit">
          {SPARK_ANGLES.map((deg) => (
            <span key={deg} className="avatar-spark-arm" style={{ transform: `rotate(${deg}deg)` }}>
              <svg viewBox="0 0 10 10" className="avatar-spark">
                <path d={SPARK_PATHS[animal.spark]} fill="var(--animal)" />
              </svg>
            </span>
          ))}
        </span>
      )}
      <span aria-hidden className={`avatar-badge ${full ? "avatar-bob" : ""}`}>
        <svg viewBox="0 0 100 100" className="avatar-art" dangerouslySetInnerHTML={art} />
      </span>
    </span>
  );
}
