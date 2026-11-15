import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { chooseSelectOption } from "@/components/ui/test-utils";
import { BirthCalendar } from "./birth-calendar";

afterEach(cleanup);

describe("BirthCalendar", () => {
  it("selects a day and reports ISO date", () => {
    const onChange = vi.fn();
    render(<BirthCalendar value="" onChange={onChange} />);

    chooseSelectOption(screen.getByLabelText(/calendar year/i), "1990");
    chooseSelectOption(screen.getByLabelText(/calendar month/i), "January");
    fireEvent.click(screen.getByRole("gridcell", { name: /January 1, 1990/i }));

    expect(onChange).toHaveBeenCalledWith("1990-01-01");
  });
});
