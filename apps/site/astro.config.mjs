import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Served at https://mrigankad.github.io/Ankana/ (GitHub Pages project site).
export default defineConfig({
  site: 'https://mrigankad.github.io',
  base: '/Ankana',
  trailingSlash: 'always',
  output: 'static',
  integrations: [sitemap()],
  build: { assets: 'assets' },
});
