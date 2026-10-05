/**
 * Noesis brand constants.  One source of truth for product identity so that
 * future rebrands (AstraOS->Noesis, thesis title variants) can be propagated
 * across the entire UI without grep-replace.
 */
export const NOESIS_BRAND = {
  product: "Noesis",
  codename: "Noesis",
  tagline: "Autonomic multi-agent operating system for research, coding & planning",
  vendor: "Noesis Project · @dhruvshah11",
  milestone: "Milestone 5",
  dashboardTitle: "Noesis — Autonomous Multi-Agent OS",
  appName: "Noesis Dashboard",
  memory: {
    t1: "Indriya (Sensory)",
    t2: "Kushalata (Skill)",
    t3: "Gyān (Knowledge)",
    t4: "Ranniti (Strategy)",
    t5: "Yojana (Planning)",
    t6: "Tattva (Essence)",
  } as const,
  primaryHue: 252,
} as const;

export const NOESIS_SANSKRIT_AGENTS = [
  { id: "manan",        code: "Planner",      label: "Manan" },
  { id: "darshak",      code: "Analyst",      label: "Darshak" },
  { id: "vidya",        code: "Coder",        label: "Vidya" },
  { id: "parikshak",    code: "Tester",       label: "Parikshak" },
  { id: "karmakarta",   code: "Tooler",       label: "Karmakarta" },
  { id: "anveshak",     code: "Researcher",   label: "Anveshak" },
  { id: "vivechak",     code: "Critic",       label: "Vivechak" },
  { id: "paalak",       code: "Memory",       label: "Paalak" },
  { id: "rakshak",      code: "Security",     label: "Rakshak" },
  { id: "samanyaka",    code: "Synthesizer",  label: "Samanyakā" },
  { id: "kriyakari",    code: "Executor",     label: "Kriyakārī" },
  { id: "nirikshak",    code: "Supervisor",   label: "Nirikshak" },
] as const;
