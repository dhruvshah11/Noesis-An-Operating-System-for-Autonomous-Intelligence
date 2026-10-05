import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

// Ensure a deterministic timezone / Date baseline for components that render
// relative or absolute dates (snapshot tests, timeline bars).
const RealDate = Date;
vi.useFakeTimers({ toFake: ["Date"], now: new RealDate("2026-01-15T12:00:00Z").getTime() });

// jsdom does not implement matchMedia.  Vitest configs environment to 'jsdom',
// so we patch the missing web API that Recharts/Tailwind may query.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-explicit-any
  (window as any).matchMedia = (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: () => false,
  });
}

afterEach(() => {
  vi.clearAllMocks();
});

export {};
