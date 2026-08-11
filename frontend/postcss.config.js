export default {
  plugins: {
    "@tailwindcss/postcss": {
      // Next workers can resolve the Git root as cwd; dependencies live here.
      base: process.cwd(),
    },
  },
};
