import { expect, test } from "@rstest/core";

import postcssConfig from "../../postcss.config.js";

test("anchors Tailwind package resolution to the frontend workspace", () => {
  expect(postcssConfig.plugins["@tailwindcss/postcss"].base).toBe(
    process.cwd(),
  );
});
