import { promises as fs } from 'node:fs';
import path from 'node:path';
import { expect } from '@playwright/test';

const emailDir = process.env.DJANGO_EMAIL_FILE_PATH || '/tmp/makolo-e2e-emails';

export async function clearE2eEmails() {
  await fs.mkdir(emailDir, { recursive: true });
  for (const entry of await fs.readdir(emailDir)) {
    await fs.rm(path.join(emailDir, entry), { force: true, recursive: true });
  }
}

export async function passwordResetLinkFor(email) {
  let resetLink = null;
  await expect.poll(async () => {
    const entries = await fs.readdir(emailDir).catch(() => []);
    for (const entry of entries) {
      const content = await fs.readFile(path.join(emailDir, entry), 'utf8').catch(() => '');
      if (!content.includes(email)) continue;
      const match = content.match(/https?:\/\/[^\s]+\/account\/password\/reset\/[^\s]+/);
      if (match) {
        resetLink = match[0].trim();
        return true;
      }
    }
    return false;
  }).toBe(true);
  return resetLink;
}
