import AxeBuilder from '@axe-core/playwright';
import { expect } from '@playwright/test';

export async function expectNoSeriousAxeViolations(page) {
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter(violation =>
    ['serious', 'critical'].includes(violation.impact),
  );
  const summary = blocking.map(violation => ({
    url: page.url(),
    id: violation.id,
    impact: violation.impact,
    help: violation.help,
    nodes: violation.nodes.map(node => ({
      target: node.target,
      html: node.html,
      failureSummary: node.failureSummary,
    })),
  }));
  expect(summary, JSON.stringify(summary, null, 2)).toEqual([]);
}
