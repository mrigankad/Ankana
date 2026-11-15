import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React, { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Combobox } from "./combobox";
import { DateField, TimeField } from "./date-time-fields";
import { ConfirmDialog } from "./dialog";
import { Select } from "./select";
import { chooseSelectOption } from "./test-utils";

afterEach(cleanup);

const OPTS = [
  { value: "a", label: "Lahiri", description: "Standard", group: "Ayanamsa" },
  { value: "b", label: "Raman", group: "Ayanamsa" },
  { value: "c", label: "Disabled one", disabled: true },
];

describe("Select", () => {
  it("opens with Enter, shows a listbox with groups and picks with the keyboard", () => {
    const onValueChange = vi.fn();
    render(<Select aria-label="Ayanamsa" value="a" onValueChange={onValueChange} options={OPTS} />);
    const trigger = screen.getByRole("combobox", { name: "Ayanamsa" });
    expect(trigger).toHaveTextContent("Lahiri");
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "Enter" });
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getByText("Ayanamsa")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Disabled one/ })).toHaveAttribute("aria-disabled", "true");
    chooseSelectOption(trigger, "Raman");
    expect(onValueChange).toHaveBeenCalledWith("b");
  });

  it("closes on Escape without changing the value", () => {
    const onValueChange = vi.fn();
    render(<Select aria-label="X" value="a" onValueChange={onValueChange} options={OPTS} />);
    const trigger = screen.getByRole("combobox");
    fireEvent.keyDown(trigger, { key: "Enter" });
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(onValueChange).not.toHaveBeenCalled();
  });

  it("supports an empty-string option", () => {
    const onValueChange = vi.fn();
    render(<Select aria-label="X" value="a" onValueChange={onValueChange} options={[{ value: "", label: "First available" }, ...OPTS]} />);
    chooseSelectOption(screen.getByRole("combobox"), "First available");
    expect(onValueChange).toHaveBeenCalledWith("");
  });
});

describe("Combobox", () => {
  it("filters, selects with Enter and offers create", async () => {
    const onChange = vi.fn();
    const onCreate = vi.fn(() => ({ value: "new", label: "Kanp" }));
    render(
      <Combobox
        aria-label="Place"
        value={null}
        onChange={onChange}
        onCreate={onCreate}
        options={[{ value: "kanpur", label: "Kanpur" }, { value: "pune", label: "Pune" }]}
      />,
    );
    fireEvent.click(screen.getByRole("combobox", { name: "Place" }));
    const input = await screen.findByPlaceholderText("Search");
    fireEvent.change(input, { target: { value: "Kanp" } });
    expect(screen.queryByRole("option", { name: "Pune" })).toBeNull();
    expect(screen.getByRole("option", { name: /Create "Kanp"/ })).toBeInTheDocument();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("kanpur", expect.objectContaining({ label: "Kanpur" }));
  });

  it("loads options asynchronously", async () => {
    const loadOptions = vi.fn(async (q: string) => [{ value: "x", label: `Result ${q}` }]);
    render(<Combobox aria-label="Client" value={null} onChange={() => {}} loadOptions={loadOptions} />);
    fireEvent.click(screen.getByRole("combobox"));
    expect(await screen.findByRole("option", { name: /Result/ }, { timeout: 2000 })).toBeInTheDocument();
    expect(loadOptions).toHaveBeenCalled();
  });
});

describe("Dialog", () => {
  it("ConfirmDialog confirms with the button and cancels with Escape", async () => {
    const onConfirm = vi.fn();
    function Host() {
      const [open, setOpen] = useState(true);
      return <ConfirmDialog open={open} onOpenChange={setOpen} title="Delete it?" confirmLabel="Delete" tone="danger" onConfirm={onConfirm} />;
    }
    render(<Host />);
    expect(screen.getByRole("alertdialog", { name: "Delete it?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
    cleanup();
    render(<Host />);
    fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe("DateField and TimeField", () => {
  function DateHost({ onIso }: { onIso: (v: string) => void }) {
    const [v, setV] = useState("");
    return <DateField aria-label="Birth date" value={v} onChange={(x) => { setV(x); onIso(x); }} />;
  }
  it("emits ISO for a real date and echoes the weekday", () => {
    const onIso = vi.fn();
    render(<DateHost onIso={onIso} />);
    fireEvent.change(screen.getByLabelText("Day"), { target: { value: "14" } });
    fireEvent.change(screen.getByLabelText("Month"), { target: { value: "11" } });
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: "1992" } });
    expect(onIso).toHaveBeenLastCalledWith("1992-11-14");
    expect(screen.getByText("Saturday")).toBeInTheDocument();
  });
  it("rejects impossible dates", () => {
    const onIso = vi.fn();
    render(<DateHost onIso={onIso} />);
    fireEvent.change(screen.getByLabelText("Day"), { target: { value: "31" } });
    fireEvent.change(screen.getByLabelText("Month"), { target: { value: "02" } });
    fireEvent.change(screen.getByLabelText("Year"), { target: { value: "1992" } });
    expect(screen.getByText("That date does not exist")).toBeInTheDocument();
    expect(onIso).not.toHaveBeenCalledWith(expect.stringMatching(/1992/));
  });
  it("TimeField converts 12 hour input to 24 hour", () => {
    const onChange = vi.fn();
    function Host() {
      const [v, setV] = useState("");
      return <TimeField aria-label="Birth time" value={v} onChange={(x) => { setV(x); onChange(x); }} />;
    }
    render(<Host />);
    fireEvent.change(screen.getByLabelText("Hour"), { target: { value: "06" } });
    fireEvent.change(screen.getByLabelText("Minute"), { target: { value: "45" } });
    expect(onChange).toHaveBeenLastCalledWith("06:45");
    fireEvent.click(screen.getByRole("radio", { name: "PM" }));
    expect(onChange).toHaveBeenLastCalledWith("18:45");
  });
});
