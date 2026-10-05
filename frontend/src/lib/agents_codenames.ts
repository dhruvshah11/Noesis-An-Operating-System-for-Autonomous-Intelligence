export const PALETTE = {
  purple500: "#6E56CF",
  purple700: "#5b21b6",
  green500: "#22c55e",
  amber500: "#f59e0b",
  red500: "#ef4444",
  cyan500: "#06b6d4",
} as const;

export type PaletteColorKey = keyof typeof PALETTE;

export const PALETTE_CLASSES: Record<PaletteColorKey, { text: string; bg: string; border: string; fill: string }> = {
  purple500: {
    text: "text-[#6E56CF]",
    bg: "bg-[#6E56CF]",
    border: "border-[#6E56CF]/50",
    fill: "fill-[#6E56CF]",
  },
  purple700: {
    text: "text-[#5b21b6]",
    bg: "bg-[#5b21b6]",
    border: "border-[#5b21b6]/50",
    fill: "fill-[#5b21b6]",
  },
  green500: {
    text: "text-[#22c55e]",
    bg: "bg-[#22c55e]",
    border: "border-[#22c55e]/50",
    fill: "fill-[#22c55e]",
  },
  amber500: {
    text: "text-[#f59e0b]",
    bg: "bg-[#f59e0b]",
    border: "border-[#f59e0b]/50",
    fill: "fill-[#f59e0b]",
  },
  red500: {
    text: "text-[#ef4444]",
    bg: "bg-[#ef4444]",
    border: "border-[#ef4444]/50",
    fill: "fill-[#ef4444]",
  },
  cyan500: {
    text: "text-[#06b6d4]",
    bg: "bg-[#06b6d4]",
    border: "border-[#06b6d4]/50",
    fill: "fill-[#06b6d4]",
  },
};

export interface AgentCodenameEntry {
  readonly id: string;
  readonly role: string;
  readonly codename: string;
  readonly badgeColor: string;
  readonly paletteKey: PaletteColorKey;
  readonly paletteHex: string;
  readonly paletteClass: string;
  readonly paletteBorderClass: string;
  readonly paletteBgClass: string;
}

export const AGENT_PALETTE_MAP: Readonly<Record<string, PaletteColorKey>> = {
  manan: "purple500",
  darshak: "purple500",
  anveshak: "purple500",
  nirikshak: "purple500",
  paalak: "purple500",
  vidya: "green500",
  parikshak: "green500",
  karmakarta: "amber500",
  kriyakari: "amber500",
  rakshak: "red500",
  vivechak: "cyan500",
  samanyaka: "cyan500",
};

export const AGENT_CODENAMES: readonly AgentCodenameEntry[] = [
  { id: "manan",      role: "Planner",      codename: "Manan",       badgeColor: "text-[#6E56CF]",       paletteKey: "purple500", paletteHex: PALETTE.purple500, paletteClass: PALETTE_CLASSES.purple500.text, paletteBorderClass: PALETTE_CLASSES.purple500.border, paletteBgClass: PALETTE_CLASSES.purple500.bg },
  { id: "darshak",    role: "Analyst",      codename: "Darshak",     badgeColor: "text-[#6E56CF]",       paletteKey: "purple500", paletteHex: PALETTE.purple500, paletteClass: PALETTE_CLASSES.purple500.text, paletteBorderClass: PALETTE_CLASSES.purple500.border, paletteBgClass: PALETTE_CLASSES.purple500.bg },
  { id: "vidya",      role: "Coder",        codename: "Vidya",       badgeColor: "text-[#22c55e]",       paletteKey: "green500",  paletteHex: PALETTE.green500,  paletteClass: PALETTE_CLASSES.green500.text,  paletteBorderClass: PALETTE_CLASSES.green500.border,  paletteBgClass: PALETTE_CLASSES.green500.bg },
  { id: "parikshak",  role: "Tester",       codename: "Parikshak",   badgeColor: "text-[#22c55e]",       paletteKey: "green500",  paletteHex: PALETTE.green500,  paletteClass: PALETTE_CLASSES.green500.text,  paletteBorderClass: PALETTE_CLASSES.green500.border,  paletteBgClass: PALETTE_CLASSES.green500.bg },
  { id: "karmakarta", role: "Tooler",       codename: "Karmakarta",  badgeColor: "text-[#f59e0b]",       paletteKey: "amber500",  paletteHex: PALETTE.amber500,  paletteClass: PALETTE_CLASSES.amber500.text,  paletteBorderClass: PALETTE_CLASSES.amber500.border,  paletteBgClass: PALETTE_CLASSES.amber500.bg },
  { id: "anveshak",   role: "Researcher",   codename: "Anveshak",    badgeColor: "text-[#6E56CF]",       paletteKey: "purple500", paletteHex: PALETTE.purple500, paletteClass: PALETTE_CLASSES.purple500.text, paletteBorderClass: PALETTE_CLASSES.purple500.border, paletteBgClass: PALETTE_CLASSES.purple500.bg },
  { id: "vivechak",   role: "Critic",       codename: "Vivechak",    badgeColor: "text-[#06b6d4]",       paletteKey: "cyan500",   paletteHex: PALETTE.cyan500,   paletteClass: PALETTE_CLASSES.cyan500.text,   paletteBorderClass: PALETTE_CLASSES.cyan500.border,   paletteBgClass: PALETTE_CLASSES.cyan500.bg },
  { id: "paalak",     role: "Memory",       codename: "Paalak",      badgeColor: "text-[#6E56CF]",       paletteKey: "purple500", paletteHex: PALETTE.purple500, paletteClass: PALETTE_CLASSES.purple500.text, paletteBorderClass: PALETTE_CLASSES.purple500.border, paletteBgClass: PALETTE_CLASSES.purple500.bg },
  { id: "rakshak",    role: "Security",     codename: "Rakshak",     badgeColor: "text-[#ef4444]",       paletteKey: "red500",    paletteHex: PALETTE.red500,    paletteClass: PALETTE_CLASSES.red500.text,    paletteBorderClass: PALETTE_CLASSES.red500.border,    paletteBgClass: PALETTE_CLASSES.red500.bg },
  { id: "samanyaka",  role: "Synthesizer",  codename: "Samanyak\u0101",   badgeColor: "text-[#06b6d4]",   paletteKey: "cyan500",   paletteHex: PALETTE.cyan500,   paletteClass: PALETTE_CLASSES.cyan500.text,   paletteBorderClass: PALETTE_CLASSES.cyan500.border,   paletteBgClass: PALETTE_CLASSES.cyan500.bg },
  { id: "kriyakari",  role: "Executor",     codename: "Kriyak\u0101r\u012b", badgeColor: "text-[#f59e0b]", paletteKey: "amber500",  paletteHex: PALETTE.amber500,  paletteClass: PALETTE_CLASSES.amber500.text,  paletteBorderClass: PALETTE_CLASSES.amber500.border,  paletteBgClass: PALETTE_CLASSES.amber500.bg },
  { id: "nirikshak",  role: "Supervisor",   codename: "Nirikshak",   badgeColor: "text-[#6E56CF]",       paletteKey: "purple500", paletteHex: PALETTE.purple500, paletteClass: PALETTE_CLASSES.purple500.text, paletteBorderClass: PALETTE_CLASSES.purple500.border, paletteBgClass: PALETTE_CLASSES.purple500.bg },
] as const;

export const CODENAME_BY_ROLE: Readonly<Record<string, string>> = AGENT_CODENAMES.reduce<Record<string, string>>(
  (acc, entry) => {
    acc[entry.role.toLowerCase()] = entry.codename;
    return acc;
  },
  {},
);

export const CODENAME_BY_ID: Readonly<Record<string, string>> = AGENT_CODENAMES.reduce<Record<string, string>>(
  (acc, entry) => {
    acc[entry.id] = entry.codename;
    return acc;
  },
  {},
);

export const BADGE_COLOR_BY_CODENAME: Readonly<Record<string, string>> = AGENT_CODENAMES.reduce<Record<string, string>>(
  (acc, entry) => {
    acc[entry.codename] = entry.badgeColor;
    return acc;
  },
  {},
);

export const PALETTE_HEX_BY_CODENAME: Readonly<Record<string, string>> = AGENT_CODENAMES.reduce<Record<string, string>>(
  (acc, entry) => {
    acc[entry.codename] = entry.paletteHex;
    return acc;
  },
  {},
);

export const PALETTE_CLASS_BY_CODENAME: Readonly<Record<string, string>> = AGENT_CODENAMES.reduce<Record<string, string>>(
  (acc, entry) => {
    acc[entry.codename] = entry.paletteClass;
    return acc;
  },
  {},
);

export const PALETTE_BORDER_CLASS_BY_CODENAME: Readonly<Record<string, string>> = AGENT_CODENAMES.reduce<Record<string, string>>(
  (acc, entry) => {
    acc[entry.codename] = entry.paletteBorderClass;
    return acc;
  },
  {},
);

export const PALETTE_BG_CLASS_BY_CODENAME: Readonly<Record<string, string>> = AGENT_CODENAMES.reduce<Record<string, string>>(
  (acc, entry) => {
    acc[entry.codename] = entry.paletteBgClass;
    return acc;
  },
  {},
);

export const PALETTE_KEY_BY_ID: Readonly<Record<string, PaletteColorKey>> = AGENT_CODENAMES.reduce<Record<string, PaletteColorKey>>(
  (acc, entry) => {
    acc[entry.id] = entry.paletteKey;
    return acc;
  },
  {},
);

export function getCodenameForRole(role: string): string | undefined {
  return CODENAME_BY_ROLE[role.toLowerCase()];
}

export function getCodenameForId(id: string): string | undefined {
  return CODENAME_BY_ID[id.toLowerCase()];
}

export function getBadgeColorForCodename(codename: string): string {
  return BADGE_COLOR_BY_CODENAME[codename] ?? PALETTE_CLASSES.purple500.text;
}

export function getPaletteHexForId(id: string): string {
  const key = PALETTE_KEY_BY_ID[id.toLowerCase()];
  return key ? PALETTE[key] : PALETTE.purple500;
}

export function getPaletteHexForCodename(codename: string): string {
  return PALETTE_HEX_BY_CODENAME[codename] ?? PALETTE.purple500;
}

export function getPaletteClassForCodename(codename: string): string {
  return PALETTE_CLASS_BY_CODENAME[codename] ?? PALETTE_CLASSES.purple500.text;
}

export function getPaletteBorderClassForCodename(codename: string): string {
  return PALETTE_BORDER_CLASS_BY_CODENAME[codename] ?? PALETTE_CLASSES.purple500.border;
}

export function getPaletteBgClassForCodename(codename: string): string {
  return PALETTE_BG_CLASS_BY_CODENAME[codename] ?? PALETTE_CLASSES.purple500.bg;
}

export function getPaletteKeyForId(id: string): PaletteColorKey {
  return AGENT_PALETTE_MAP[id.toLowerCase()] ?? "purple500";
}
