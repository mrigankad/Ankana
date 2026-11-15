import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ClientIntakeForm } from "./client-intake-form";

describe("ClientIntakeForm", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("requires a confirmed location before enabling chart generation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      json: async () => ({
        results: [
          {
            providerPlaceId: "geo_varanasi_in",
            displayName: "Varanasi, Uttar Pradesh, India",
            latitude: 25.3176,
            longitude: 82.9739,
            timezoneName: "Asia/Kolkata",
            confidence: "high",
            countryCode: "IN",
          },
        ],
      }),
    } as Response);

    render(React.createElement(ClientIntakeForm));

    const generateButton = screen.getByRole("button", { name: /generate chart/i });

    expect(generateButton).toBeDisabled();

    const date = screen.getByRole("group", { name: /birth date/i });
    fireEvent.change(within(date).getByLabelText("Day"), { target: { value: "01" } });
    fireEvent.change(within(date).getByLabelText("Month"), { target: { value: "01" } });
    fireEvent.change(within(date).getByLabelText("Year"), { target: { value: "1990" } });
    const time = screen.getByRole("group", { name: /birth time/i });
    fireEvent.change(within(time).getByLabelText("Hour"), { target: { value: "10" } });
    fireEvent.change(within(time).getByLabelText("Minute"), { target: { value: "30" } });

    // Date and time alone are not enough: the place must be confirmed too.
    expect(generateButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/birth place/i), {
      target: { value: "Varanasi, India" },
    });
    fireEvent.click(screen.getByRole("button", { name: /search location/i }));
    const confirmButton = await screen.findByRole("button", {
      name: /confirm varanasi/i,
    });
    fireEvent.click(confirmButton);

    expect(generateButton).toBeEnabled();
  });
});
