import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import {
  AGENT_CODENAMES,
  AGENT_PALETTE_MAP,
  getBadgeColorForCodename,
  getPaletteClassForCodename,
  getPaletteHexForCodename,
  getPaletteHexForId,
  PALETTE,
} from "@/lib/agents_codenames";
import { DemoPipelineSankey } from "@/lib/demo";
import type { DemoWorkflowNode } from "@/lib/demo";

const PURPLE_500 = "#6E56CF";
const GREEN_500 = "#22c55e";
const RED_500 = "#ef4444";
const AMBER_500 = "#f59e0b";
const CYAN_500 = "#06b6d4";
const PURPLE_700 = "#5b21b6";

function stripAlpha(anyColor: string): string {
  const rgba = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(anyColor);
  if (rgba) {
    const r = parseInt(rgba[1] ?? "", 10).toString(16).padStart(2, "0");
    const g = parseInt(rgba[2] ?? "", 10).toString(16).padStart(2, "0");
    const b = parseInt(rgba[3] ?? "", 10).toString(16).padStart(2, "0");
    return `#${r}${g}${b}`;
  }
  const hash = /^#([0-9a-f]{6})/i.exec(anyColor);
  if (hash) {
    const hex = hash[1];
    if (hex) return `#${hex.toLowerCase()}`;
  }
  return anyColor.toLowerCase();
}

describe("PALETTE constants — 6 brand colors", () => {
  it("purple500 = #6E56CF (Planning/Analysis/Research/Supervisory/Memory)", () => {
    expect(stripAlpha(PALETTE.purple500)).toBe(PURPLE_500.toLowerCase());
  });

  it("green500 = #22c55e (Coding/Testing)", () => {
    expect(stripAlpha(PALETTE.green500)).toBe(GREEN_500.toLowerCase());
  });

  it("amber500 = #f59e0b (Tooling/Execution)", () => {
    expect(stripAlpha(PALETTE.amber500)).toBe(AMBER_500.toLowerCase());
  });

  it("red500 = #ef4444 (Security)", () => {
    expect(stripAlpha(PALETTE.red500)).toBe(RED_500.toLowerCase());
  });

  it("cyan500 = #06b6d4 (Critique/Synthesis)", () => {
    expect(stripAlpha(PALETTE.cyan500)).toBe(CYAN_500.toLowerCase());
  });

  it("purple700 = #5b21b6 (Paalak fallback)", () => {
    expect(stripAlpha(PALETTE.purple700)).toBe(PURPLE_700.toLowerCase());
  });
});

describe("AGENT_PALETTE_MAP — 12 agents → 6 colors (core 3 verified: Manan/Vidya/Rakshak)", () => {
  it("Manan → purple500", () => {
    expect(AGENT_PALETTE_MAP.manan).toBe("purple500");
  });

  it("Vidya → green500", () => {
    expect(AGENT_PALETTE_MAP.vidya).toBe("green500");
  });

  it("Rakshak → red500", () => {
    expect(AGENT_PALETTE_MAP.rakshak).toBe("red500");
  });

  it("Paalak → purple500 (primary, not fallback)", () => {
    expect(AGENT_PALETTE_MAP.paalak).toBe("purple500");
  });

  it("Karmakarta → amber500", () => {
    expect(AGENT_PALETTE_MAP.karmakarta).toBe("amber500");
  });

  it("Vivechak → cyan500", () => {
    expect(AGENT_PALETTE_MAP.vivechak).toBe("cyan500");
  });
});

describe("AGENT_CODENAMES entries carry paletteHex & paletteKey", () => {
  it("Manan = paletteKey=purple500, paletteHex=#6E56CF", () => {
    const a = AGENT_CODENAMES.find((x) => x.id === "manan");
    expect(a).toBeDefined();
    if (!a) return;
    expect(a.paletteKey).toBe("purple500");
    expect(stripAlpha(a.paletteHex)).toBe(PURPLE_500.toLowerCase());
  });

  it("Vidya = paletteKey=green500, paletteHex=#22c55e", () => {
    const a = AGENT_CODENAMES.find((x) => x.id === "vidya");
    expect(a).toBeDefined();
    if (!a) return;
    expect(a.paletteKey).toBe("green500");
    expect(stripAlpha(a.paletteHex)).toBe(GREEN_500.toLowerCase());
  });

  it("Rakshak = paletteKey=red500, paletteHex=#ef4444", () => {
    const a = AGENT_CODENAMES.find((x) => x.id === "rakshak");
    expect(a).toBeDefined();
    if (!a) return;
    expect(a.paletteKey).toBe("red500");
    expect(stripAlpha(a.paletteHex)).toBe(RED_500.toLowerCase());
  });
});

describe("Helper lookups: getPaletteHexForId / getPaletteHexForCodename", () => {
  it("getPaletteHexForId('manan') → #6E56CF purple", () => {
    expect(stripAlpha(getPaletteHexForId("manan"))).toBe(PURPLE_500.toLowerCase());
  });

  it("getPaletteHexForId('vidya') → #22c55e green", () => {
    expect(stripAlpha(getPaletteHexForId("vidya"))).toBe(GREEN_500.toLowerCase());
  });

  it("getPaletteHexForId('rakshak') → #ef4444 red", () => {
    expect(stripAlpha(getPaletteHexForId("rakshak"))).toBe(RED_500.toLowerCase());
  });

  it("getPaletteHexForCodename('Manan') → purple", () => {
    expect(stripAlpha(getPaletteHexForCodename("Manan"))).toBe(PURPLE_500.toLowerCase());
  });

  it("getPaletteHexForCodename('Vidya') → green", () => {
    expect(stripAlpha(getPaletteHexForCodename("Vidya"))).toBe(GREEN_500.toLowerCase());
  });

  it("getPaletteHexForCodename('Rakshak') → red", () => {
    expect(stripAlpha(getPaletteHexForCodename("Rakshak"))).toBe(RED_500.toLowerCase());
  });

  it("getPaletteClassForCodename('Manan') references #6E56CF in class token", () => {
    expect(getPaletteClassForCodename("Manan")).toContain("6E56CF");
  });

  it("getBadgeColorForCodename('Vidya') references #22c55e in class token", () => {
    expect(getBadgeColorForCodename("Vidya")).toContain("22c55e");
  });
});

function buildNodes(): DemoWorkflowNode[] {
  return AGENT_CODENAMES.map((entry, idx): DemoWorkflowNode => ({
    id: `demo-node-${idx}`,
    role: entry.role,
    codename: entry.codename,
    status: idx < 6 ? "success" : idx === 6 ? "running" : "pending",
    progress: idx < 6 ? 100 : idx === 6 ? 42 : 0,
    description: `${entry.role} description`,
    depends_on: idx === 0 ? [] : [idx - 1],
    accent: entry.paletteBorderClass,
    paletteBorderClass: entry.paletteBorderClass,
    paletteBgClass: entry.paletteBgClass,
    paletteHex: entry.paletteHex,
    paletteTextClass: entry.paletteClass,
  }));
}

const codenameOf = (id: string): string => {
  const found = AGENT_CODENAMES.find((a) => a.id === id);
  if (!found) throw new Error(`codenameOf: unknown id ${id}`);
  return found.codename;
};

describe("<DemoPipelineSankey /> palette classes + inline styles applied (Manan=purple, Vidya=green, Rakshak=red)", () => {
  let nodes: DemoWorkflowNode[];

  beforeAll(() => {
    nodes = buildNodes();
  });

  it("renders sankey wrapper with data-testid", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    expect(screen.getByTestId("demo-pipeline-sankey")).toBeTruthy();
  });

  it("Manan node wrapper: data-palette-hex=#6E56CF + border inline style purple RGB", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const el = screen.getByTestId("sankey-node-manan");
    expect(el.getAttribute("data-palette-hex")?.toLowerCase()).toBe(PURPLE_500.toLowerCase());
    const borderColor = el.style.borderColor;
    expect(borderColor).toBeTruthy();
    expect(stripAlpha(borderColor)).toBe(PURPLE_500.toLowerCase());
  });

  it("Manan codename Badge: inline color style = purple #6E56CF RGB", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const badge = screen.getByTestId("sankey-codename-manan");
    expect(stripAlpha(badge.style.color)).toBe(PURPLE_500.toLowerCase());
  });

  it("Manan node number badge: text color = purple RGB", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const b = screen.getByTestId("sankey-node-badge-manan");
    expect(stripAlpha(b.style.color)).toBe(PURPLE_500.toLowerCase());
  });

  it("Vidya node wrapper: data-palette-hex=#22c55e green", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const el = screen.getByTestId("sankey-node-vidya");
    expect(el.getAttribute("data-palette-hex")?.toLowerCase()).toBe(GREEN_500.toLowerCase());
  });

  it("Vidya codename Badge: inline color style = green #22c55e RGB", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const badge = screen.getByTestId("sankey-codename-vidya");
    expect(stripAlpha(badge.style.color)).toBe(GREEN_500.toLowerCase());
  });

  it("Vidya node number badge: text color = green RGB", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const b = screen.getByTestId("sankey-node-badge-vidya");
    expect(stripAlpha(b.style.color)).toBe(GREEN_500.toLowerCase());
  });

  it("Rakshak node wrapper: data-palette-hex=#ef4444 red", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const el = screen.getByTestId("sankey-node-rakshak");
    expect(el.getAttribute("data-palette-hex")?.toLowerCase()).toBe(RED_500.toLowerCase());
  });

  it("Rakshak codename Badge: inline color style = red #ef4444 RGB", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const badge = screen.getByTestId("sankey-codename-rakshak");
    expect(stripAlpha(badge.style.color)).toBe(RED_500.toLowerCase());
  });

  it("Rakshak node number badge: text color = red RGB", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const b = screen.getByTestId("sankey-node-badge-rakshak");
    expect(stripAlpha(b.style.color)).toBe(RED_500.toLowerCase());
  });

  it("Karmakarta (Tooler) node uses amber500 palette data attr", () => {
    render(<DemoPipelineSankey nodes={nodes} />);
    const el = screen.getByTestId("sankey-node-karmakarta");
    expect(el.getAttribute("data-palette-hex")?.toLowerCase()).toBe(AMBER_500.toLowerCase());
  });

  it("Samanyaka (Synthesizer) node uses cyan500 palette via dynamic codename lookup", () => {
    const cn = codenameOf("samanyaka");
    const testId = `sankey-node-${cn.toLowerCase()}`;
    render(<DemoPipelineSankey nodes={nodes} />);
    const el = screen.getByTestId(testId);
    expect(el.getAttribute("data-palette-hex")?.toLowerCase()).toBe(CYAN_500.toLowerCase());
  });

  it("Kriyakārī (Executor) codename badge text color = amber RGB", () => {
    const cn = codenameOf("kriyakari");
    const testId = `sankey-codename-${cn.toLowerCase()}`;
    render(<DemoPipelineSankey nodes={nodes} />);
    const badge = screen.getByTestId(testId);
    expect(stripAlpha(badge.style.color)).toBe(AMBER_500.toLowerCase());
  });
});

describe("Palette distribution sanity = 5 purple + 2 green + 2 amber + 1 red + 2 cyan = 12", () => {
  it("purple500 bucket = 5 agents", () => {
    expect(AGENT_CODENAMES.filter((a) => a.paletteKey === "purple500")).toHaveLength(5);
  });

  it("green500 bucket = 2 agents", () => {
    expect(AGENT_CODENAMES.filter((a) => a.paletteKey === "green500")).toHaveLength(2);
  });

  it("amber500 bucket = 2 agents", () => {
    expect(AGENT_CODENAMES.filter((a) => a.paletteKey === "amber500")).toHaveLength(2);
  });

  it("red500 bucket = 1 agent (Rakshak)", () => {
    expect(AGENT_CODENAMES.filter((a) => a.paletteKey === "red500")).toHaveLength(1);
  });

  it("cyan500 bucket = 2 agents", () => {
    expect(AGENT_CODENAMES.filter((a) => a.paletteKey === "cyan500")).toHaveLength(2);
  });

  it("total Sanskrit codenames = 12", () => {
    expect(AGENT_CODENAMES).toHaveLength(12);
    expect(5 + 2 + 2 + 1 + 2).toBe(12);
  });
});
