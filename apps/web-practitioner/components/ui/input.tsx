import * as React from "react"

import { cn } from "@/lib/utils"
import { FIELD_CLASS } from "@/components/ui/field"

/** Text input. For dates, times, choices and booleans use DateField, TimeField, Select, Switch, Checkbox. */
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return <input type={type} data-slot="input" className={cn(FIELD_CLASS, className)} {...props} />
}

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(FIELD_CLASS, "h-auto min-h-[84px] resize-y py-2.5 leading-5", className)}
      {...props}
    />
  )
}

export { Input, Textarea }
