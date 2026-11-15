import { fireEvent, screen } from "@testing-library/react"

/** Open a Radix Select trigger with the keyboard and choose an option by its accessible name. */
export function chooseSelectOption(trigger: HTMLElement, name: string | RegExp) {
  trigger.focus()
  fireEvent.keyDown(trigger, { key: "Enter" })
  const option = screen.getByRole("option", { name })
  fireEvent.keyDown(option, { key: "Enter" })
}
