import { describe, expect, it } from "vitest";
import { formatMoney, replayStateAt, representativeScenarios } from "./fixtures";

describe("institutional replay fixtures", () => {
  it("advances deterministically", () => {
    const scenario = representativeScenarios[0];
    expect(scenario).toBeDefined();
    if (!scenario) return;
    expect(replayStateAt(scenario, 0)).toBe("INITIATED");
    expect(replayStateAt(scenario, scenario.duration)).toBe(scenario.expected_state);
  });

  it("formats financial amounts with an explicit currency", () => {
    expect(formatMoney(1_250_000, "CNY")).toContain("1,250,000");
  });
});
