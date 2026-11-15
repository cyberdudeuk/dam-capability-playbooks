// JavaScript linter (OpenSSF warnings criterion; secure development standing rule, 15 Nov 2026).
// CI installs the pinned versions below and runs `npx eslint .`, which fails on any finding.
// eslint@9.39.5, @eslint/js@9.39.5, globals@16.5.0
import js from "@eslint/js";
import globals from "globals";

export default [
  {ignores: ["node_modules/**", "**/vendor/**", "**/*.min.js", "dist/**", "site/**"]  /* site/ is the built output, copied from site_src/ */},
  js.configs.recommended,
  {files: ["**/*.js", "**/*.cjs"], languageOptions: {ecmaVersion: 2024, sourceType: "script", globals: {...globals.browser}}},
  {files: ["**/*.mjs"], languageOptions: {ecmaVersion: 2024, sourceType: "module", globals: {...globals.node}}},
  // Unused catch bindings and empty catches are allowed: storage is optional and fails closed and silently.
  {rules: {"no-unused-vars": ["error", {varsIgnorePattern: "^_", argsIgnorePattern: "^_", caughtErrors: "none"}], "no-empty": ["error", {allowEmptyCatch: true}]}},
];
