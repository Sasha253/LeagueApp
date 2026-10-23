import type { Position } from "../api/client";

export const POSITIONS: { value: Position; label: string }[] = [
  { value: "outfield", label: "Outfield" },
  { value: "goalkeeper", label: "Goalkeeper" },
  { value: "both", label: "Both" },
];
