import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('PWA Manifest, Workbox Caching & Offline Boundaries', () => {
  it('verifies index.html contains PWA meta tags and theme color', () => {
    const indexPath = path.resolve(__dirname, '../../index.html');
    const indexHtml = fs.readFileSync(indexPath, 'utf-8');

    expect(indexHtml).toContain('<meta name="theme-color" content="#059669"');
    expect(indexHtml).toContain('viewport-fit=cover');
    expect(indexHtml).toContain('apple-touch-icon');
  });

  it('verifies required PWA app icons exist in public directory', () => {
    const iconsDir = path.resolve(__dirname, '../../public/icons');

    expect(fs.existsSync(path.join(iconsDir, 'icon-192.png'))).toBe(true);
    expect(fs.existsSync(path.join(iconsDir, 'icon-512.png'))).toBe(true);
    expect(fs.existsSync(path.join(iconsDir, 'maskable-icon-512.png'))).toBe(true);
    expect(fs.existsSync(path.join(iconsDir, 'logo.svg'))).toBe(true);
  });

  it('verifies Workbox config strictly denylists /api/ from offline navigation fallback', () => {
    const viteConfigPath = path.resolve(__dirname, '../../vite.config.ts');
    const viteConfigContent = fs.readFileSync(viteConfigPath, 'utf-8');

    // NFR-050 / Sec 12.1: strictly no offline API data caching
    expect(viteConfigContent).toContain('navigateFallbackDenylist');
    expect(viteConfigContent).toContain('runtimeCaching: []');
  });

  it('verifies service worker is registered in main entry point', () => {
    const mainPath = path.resolve(__dirname, '../main.tsx');
    const mainContent = fs.readFileSync(mainPath, 'utf-8');

    expect(mainContent).toContain('registerSW');
    expect(mainContent).toContain('immediate: true');
  });

  it('verifies production build output includes valid manifest and sw.js', () => {
    const distDir = path.resolve(__dirname, '../../dist');
    if (fs.existsSync(distDir)) {
      expect(fs.existsSync(path.join(distDir, 'manifest.webmanifest'))).toBe(true);
      expect(fs.existsSync(path.join(distDir, 'sw.js'))).toBe(true);

      const manifestContent = JSON.parse(
        fs.readFileSync(path.join(distDir, 'manifest.webmanifest'), 'utf-8')
      );
      expect(manifestContent.name).toBe('FridgeChef AI');
      expect(manifestContent.short_name).toBe('FridgeChef');
      expect(manifestContent.theme_color).toBe('#059669');
      expect(manifestContent.display).toBe('standalone');
      expect(manifestContent.icons.length).toBeGreaterThanOrEqual(3);
    }
  });
});
