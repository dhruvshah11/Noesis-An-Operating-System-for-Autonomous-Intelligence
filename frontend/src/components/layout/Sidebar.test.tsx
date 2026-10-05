import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sidebar } from "@/components/layout/Sidebar";

describe("<Sidebar /> layout (navigation)", () => {
  it("renders all 9 navigation items when compact=false", () => {
    render(<Sidebar />);
    [
      "Dashboard",
      "Conversations",
      "Agents",
      "Bench Runner",
      "Execution Timeline",
      "Memory Explorer",
      "Documents",
      "Observability",
      "Settings",
    ].forEach((label) => {
      expect(screen.getByText(label)).toBeTruthy();
    });
  });

  it("renders compact-mode class (w-[76px]) when compact=true", () => {
    const { container } = render(<Sidebar compact />);
    const aside = container.querySelector("aside");
    expect(aside?.className).toContain("w-[76px]");
    expect(aside?.className).not.toContain("w-64");
  });

  it("renders Demo Admin footer tile with avatar fallback initials", () => {
    render(<Sidebar />);
    expect(screen.getByText("Demo Admin")).toBeTruthy();
    expect(screen.getByText("DX")).toBeTruthy();
  });
});
