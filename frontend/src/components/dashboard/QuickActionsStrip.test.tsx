import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { QuickActionsStrip } from "@/components/dashboard/QuickActionsStrip";

describe("<QuickActionsStrip />", () => {
  it("renders all 6 CTA tiles with labels", () => {
    render(<QuickActionsStrip />);
    const labels = [
      "New conversation",
      "Agent playground",
      "Upload document",
      "Query memory",
      "Quick shell",
      "Generate patch",
    ];
    for (const l of labels) {
      expect(screen.getByText(l)).toBeTruthy();
    }
  });
});
