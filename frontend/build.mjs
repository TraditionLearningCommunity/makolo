import { build } from 'esbuild';
import { copyFile, mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const dist = path.join(root, 'static', 'dist');
const source = path.join(root, 'frontend', 'src');
const generated = path.join(root, 'frontend', '.generated');
const ICON_ALIASES = { ListClock: 'Clock' };

await mkdir(dist, { recursive: true });
await mkdir(generated, { recursive: true });

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (['.git', 'node_modules', 'staticfiles'].includes(entry.name)) continue;
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await walk(fullPath));
    else files.push(fullPath);
  }
  return files;
}

function toPascalCase(iconName) {
  return iconName
    .split('-')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join('');
}

const iconNames = new Set();
for (const file of await walk(root)) {
  if (!file.endsWith('.html')) continue;
  const content = await readFile(file, 'utf8');
  for (const match of content.matchAll(/data-lucide=["']([a-z0-9-]+)["']/g)) {
    iconNames.add(toPascalCase(match[1]));
  }
}
const sortedIcons = [...iconNames].sort();
if (!sortedIcons.length) throw new Error('No Lucide icons found in templates.');
const importNames = [...new Set(sortedIcons.map(icon => ICON_ALIASES[icon] || icon))].sort();
const registryEntries = sortedIcons.map(icon => {
  const imported = ICON_ALIASES[icon] || icon;
  return imported === icon ? icon : `${icon}: ${imported}`;
});
const registry = `import { ${importNames.join(', ')} } from 'lucide';\nexport const makoloIcons = { ${registryEntries.join(', ')} };\n`;
await writeFile(path.join(generated, 'lucide-icons.js'), registry, 'utf8');
console.log(`Lucide icons bundled: ${sortedIcons.length}`);
if (Object.keys(ICON_ALIASES).length) console.log(`Lucide aliases: ${JSON.stringify(ICON_ALIASES)}`);

const common = {
  minify: true,
  sourcemap: false,
  legalComments: 'none',
  target: ['es2020'],
  platform: 'browser',
  logLevel: 'info',
};

await build({
  ...common,
  entryPoints: [path.join(source, 'app.js')],
  outfile: path.join(dist, 'makolo.js'),
  bundle: true,
  format: 'iife',
});

await build({
  ...common,
  entryPoints: [path.join(source, 'theme-init.js')],
  outfile: path.join(dist, 'theme-init.js'),
  bundle: true,
  format: 'iife',
});

await build({
  ...common,
  entryPoints: [path.join(source, 'scanner.js')],
  outfile: path.join(dist, 'scanner.js'),
  bundle: false,
  format: 'iife',
});

await copyFile(
  path.join(root, 'node_modules', 'qr-scanner', 'qr-scanner.umd.min.js'),
  path.join(dist, 'qr-scanner.umd.min.js'),
);
await copyFile(
  path.join(root, 'node_modules', 'qr-scanner', 'qr-scanner-worker.min.js'),
  path.join(dist, 'qr-scanner-worker.min.js'),
);

const files = (await readdir(dist)).sort();
for (const file of files) {
  const info = await stat(path.join(dist, file));
  if (info.isFile()) {
    console.log(`${file}: ${(info.size / 1024).toFixed(1)} KiB`);
  }
}
