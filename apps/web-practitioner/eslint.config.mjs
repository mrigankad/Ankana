import tseslint from "typescript-eslint";

/**
 * Design-system guard: native form controls and browser dialogs are banned outside components/ui.
 * Use Select/Combobox, DateField/TimeField, Checkbox/RadioGroup/SegmentedControl, ConfirmDialog/useToast.
 */
const NATIVE_INPUT_TYPES = "date|time|datetime-local|month|week|checkbox|radio|color|range";

const message = (what, use) => `Native ${what} is banned. Use ${use} from "@/components/ui".`;

export default [
  { linterOptions: { reportUnusedDisableDirectives: "off" } },
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    ignores: ["components/ui/**", "**/*.test.{ts,tsx}"],
    languageOptions: { parser: tseslint.parser, parserOptions: { ecmaFeatures: { jsx: true } } },
    plugins: { "react-hooks": { rules: { "exhaustive-deps": { meta: { schema: [] }, create: () => ({}) } } }, "@next/next": { rules: { "no-img-element": { meta: { schema: [] }, create: () => ({}) } } } },
    rules: {
      "no-restricted-syntax": [
        "error",
        { selector: "JSXOpeningElement[name.name='select']", message: message("<select>", "Select or Combobox") },
        { selector: "JSXOpeningElement[name.name='datalist']", message: message("<datalist>", "Combobox") },
        {
          selector: `JSXOpeningElement[name.name='input'] > JSXAttribute[name.name='type'][value.value=/^(${NATIVE_INPUT_TYPES})$/]`,
          message: message("input type date/time/checkbox/radio/color/range", "DateField, TimeField, Checkbox, RadioGroup, Switch"),
        },
        {
          selector: `CallExpression[callee.name='createElement'][arguments.0.value='select']`,
          message: message("select", "Select"),
        },
      ],
      "no-restricted-globals": [
        "error",
        { name: "alert", message: "Use useToast() or Banner." },
        { name: "confirm", message: "Use ConfirmDialog." },
        { name: "prompt", message: "Use Dialog with an Input." },
      ],
      "no-restricted-properties": [
        "error",
        { object: "window", property: "alert", message: "Use useToast() or Banner." },
        { object: "window", property: "confirm", message: "Use ConfirmDialog." },
        { object: "window", property: "prompt", message: "Use Dialog with an Input." },
      ],
    },
  },
];
