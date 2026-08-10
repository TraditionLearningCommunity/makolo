import { build } from 'esbuild';
import { copyFile, mkdir, readdir, rm, stat } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const dist = path.join(root, 'static', 'dist');
const source = path.join(root, 'frontend', 'src');

await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

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
  console.log(`${file}: ${(info.size / 1024).toFixed(1)} KiB`);
}
