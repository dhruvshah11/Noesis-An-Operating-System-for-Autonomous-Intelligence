import globals from "globals";
import tseslint from "typescript-eslint";
import nextPlugin from "@next/eslint-plugin-next";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import js from "@eslint/js";

/** @satisfies {import('eslint').Linter.Config[]} */
export default tseslint.config(
  // ---- Global ignores (matches .gitignore-style) --------------------------
  { ignores: [".next/**", "node_modules/**", "coverage/**", "out/**", "public/**"] },

  // ---- Base (untyped, applies to ALL files including configs) -------------
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      next: { rootDir: import.meta.dirname },
    },
  },

  // ---- Source + app + test: strict type-checked ---------------------------
  ...tseslint.configs.strictTypeChecked.map((cfg) => ({ ...cfg, files: ["app/**/*.{ts,tsx}", "src/**/*.{ts,tsx}"] })),
  ...tseslint.configs.stylisticTypeChecked.map((cfg) => ({ ...cfg, files: ["app/**/*.{ts,tsx}", "src/**/*.{ts,tsx}"] })),
  {
    files: ["app/**/*.{ts,tsx}", "src/**/*.{ts,tsx}"],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "@next/next": nextPlugin,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      // eslint-plugin-react-hooks (strict)
      ...reactHooks.configs.recommended.rules,
      "react-hooks/exhaustive-deps": "error",

      // Next.js recommended + core-web-vitals (matches eslint-config-next intent)
      "@next/next/google-font-display": "error",
      "@next/next/google-font-preconnect": "warn",
      "@next/next/no-css-tags": "warn",
      "@next/next/no-head-element": "error",
      "@next/next/no-html-link-for-pages": "off", // App Router uses app/ not pages/
      "@next/next/no-img-element": "error",
      "@next/next/no-sync-scripts": "error",
      "@next/next/no-title-in-document-head": "warn",
      "@next/next/no-unwanted-polyfillio": "warn",
      "@next/next/inline-script-id": "error",
      "@next/next/next-script-for-ga": "warn",

      // typescript-eslint tuning
      "@typescript-eslint/no-confusing-void-expression": [
        "error",
        { ignoreArrowShorthand: true, ignoreVoidOperator: true },
      ],
      "@typescript-eslint/restrict-template-expressions": [
        "error",
        { allowNumber: true, allowBoolean: true },
      ],
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "separate-type-imports" },
      ],

      // Import ordering (I-equivalent of Ruff I) via TSESLint
      "sort-imports": [
        "error",
        { ignoreCase: true, ignoreDeclarationSort: true, ignoreMemberSort: false },
      ],

      // React 18 + Next 14 compat: global JSX is still used everywhere, React.JSX not mandated yet
      "@typescript-eslint/no-deprecated": "off",
      // Next RSC layouts typically export metadata + component; fast-refresh only applies to client components
      "react-refresh/only-export-components": "off",
    },
  },

  // ---- Config + script files: no type-checking (dev-only) -----------------
  ...(tseslint.configs.disableTypeChecked
    ? [tseslint.configs.disableTypeChecked].map((cfg) => ({
        ...cfg,
        files: [
          "next.config.*",
          "tailwind.config.*",
          "postcss.config.*",
          "vitest.config.*",
          "eslint.config.*",
          "scripts/**/*.ts",
          "*.config.{js,mjs,ts}",
        ],
      }))
    : []),
  {
    files: [
      "next.config.*",
      "tailwind.config.*",
      "postcss.config.*",
      "vitest.config.*",
      "eslint.config.*",
      "scripts/**/*.ts",
      "*.config.{js,mjs,ts}",
    ],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "sort-imports": "off",
    },
  },
);
