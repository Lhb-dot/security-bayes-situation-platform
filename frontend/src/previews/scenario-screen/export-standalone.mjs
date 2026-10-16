import { build } from 'vite';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFile, writeFile } from 'node:fs/promises';

const here = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(here, '../../..');
const entryName = process.argv[2] || 'scenario-screen-preview.html';
if (!/^[a-z0-9-]+\.html$/i.test(entryName)) throw new Error('Expected an HTML filename in the frontend directory');
const defaultScene = process.argv[3] || '';
if (defaultScene && !['network', 'power', 'flight_deck', 'geological'].includes(defaultScene)) throw new Error('Unknown default preview scene');
const original = await readFile(resolve(frontend, entryName), 'utf8');
const title = original.match(/<title>([\s\S]*?)<\/title>/i)?.[1] || '独立设计预览';
const result = await build({
  root: frontend,
  configFile: resolve(frontend, 'vite.config.ts'),
  build: {
    write: false,
    emptyOutDir: false,
    cssCodeSplit: false,
    assetsInlineLimit: Infinity,
    rollupOptions: { input: resolve(frontend, entryName) },
  },
});
const outputs = (Array.isArray(result) ? result : [result]).flatMap(bundle => bundle.output);
const scripts = outputs.filter(file => file.type === 'chunk');
const styles = outputs.filter(file => file.type === 'asset' && file.fileName.endsWith('.css'));
if (scripts.length !== 1 || scripts[0].imports.length || scripts[0].dynamicImports.length) throw new Error('Standalone preview must contain exactly one self-contained script');
const css = styles.map(file => typeof file.source === 'string' ? file.source : Buffer.from(file.source).toString('utf8')).join('\n');
const javascript = scripts[0].code.replace(/<\/script/gi, '<\\/script');
const html = `<!doctype html>\n<html lang="zh-CN"${defaultScene ? ` data-preview-scene="${defaultScene}"` : ''}><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>${title} · 离线版</title><style>${css}</style></head><body><div id="app"></div><script type="module">${javascript}</script></body></html>\n`;
const destination = resolve(frontend, entryName.replace(/\.html$/i, `${defaultScene ? `-${defaultScene}` : ''}-standalone.html`));
await writeFile(destination, html, 'utf8');
console.log(`Standalone HTML: ${destination} (${Buffer.byteLength(html)} bytes)`);
