import { defineConfig } from 'astro/config';

// The site is served at the root of its own Pages custom domain
// (usecase.genisisiq.com). The Pages workflow passes SITE_URL / BASE_PATH from
// actions/configure-pages, so a sub-path deployment also works unchanged.
export default defineConfig({
  site: process.env.SITE_URL || 'https://usecase.genisisiq.com',
  base: process.env.BASE_PATH || '/',
  build: { assets: 'assets' },
  // Neutral, hash-only asset names (no framework or component names in URLs).
  vite: {
    build: {
      // Inline page scripts into the HTML (no separately named script files) — but
      // never fonts: inlined, every unicode-range subset would load on every page.
      assetsInlineLimit: (filePath, content) =>
        /\.(woff2?|ttf|otf)$/.test(filePath) ? false : content.length < 100 * 1024,
      rollupOptions: {
        output: {
          entryFileNames: 'assets/[hash].js',
          chunkFileNames: 'assets/[hash].js',
          assetFileNames: 'assets/[hash][extname]',
        },
      },
    },
  },
});
