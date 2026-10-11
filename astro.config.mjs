import { defineConfig } from 'astro/config';

// GitHub Pages serves project sites under a sub-path (e.g. /usecase/). The
// Pages workflow passes SITE_URL / BASE_PATH from actions/configure-pages;
// local dev and CI validation builds fall back to the site root.
export default defineConfig({
  site: process.env.SITE_URL || 'https://vibewatch.github.io',
  base: process.env.BASE_PATH || '/',
});
