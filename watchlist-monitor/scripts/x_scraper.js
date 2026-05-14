/**
 * X Scraper v2 — subprocess helper for watchlist-runner
 * Called via: node x_scraper.js <account1> <account2> ...
 * Output: JSON array of {account, text, link, time} per tweet
 * Requires: cookies.json in PROFILE_DIR (exported from logged-in Playwright)
 */

const { chromium } = require('playwright');
const fs = require('fs');

const PROFILE_DIR = process.env.HOME + '/.hermes/browser-profiles/x';
const COOKIES_FILE = PROFILE_DIR + '/cookies.json';
const MAX_PER_ACCOUNT = 5;
const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1680, height: 1050 },
];

async function scrapeAccount(page, account) {
  const url = `https://x.com/${account.replace('@', '')}`;
  await page.goto(url, { waitUntil: 'load', timeout: 20000 });

  // Scroll until tweets appear (X lazy-loads timeline)
  for (let i = 0; i < 8; i++) {
    await page.waitForTimeout(1500);
    const count = await page.evaluate(
      () => document.querySelectorAll('article[data-testid="tweet"]').length
    );
    if (count >= MAX_PER_ACCOUNT) break;
    await page.evaluate(() => window.scrollBy(0, 2000));
  }

  const tweets = await page.evaluate((max) => {
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    const results = [];
    for (const a of articles) {
      if (results.length >= max) break;
      const text = a.querySelector('[data-testid="tweetText"]')?.innerText || '';
      const link = a.querySelector('a[href*="/status/"]')?.href || '';
      const time = a.querySelector('time')?.getAttribute('datetime') || '';
      if (text) results.push({ text, link, time });
    }
    return results;
  }, MAX_PER_ACCOUNT);

  return tweets.map(t => ({ account, ...t }));
}

async function main() {
  const accounts = process.argv.slice(2);
  if (!accounts.length) {
    console.log('[]');
    return;
  }

  const vp = VIEWPORTS[Math.floor(Math.random() * VIEWPORTS.length)];
  const context = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: true,
    viewport: vp,
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  });

  // Load auth cookies
  if (fs.existsSync(COOKIES_FILE)) {
    try {
      await context.addCookies(JSON.parse(fs.readFileSync(COOKIES_FILE, 'utf8')));
    } catch {}
  }

  const page = await context.newPage();

  // Anti-detection init
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'en-US'] });
    if (!window.chrome) window.chrome = { runtime: {} };
  });

  const allTweets = [];
  for (let i = 0; i < accounts.length; i++) {
    try {
      const tweets = await scrapeAccount(page, accounts[i]);
      allTweets.push(...tweets);
    } catch {}
    if (i < accounts.length - 1) {
      await page.waitForTimeout(2000 + Math.random() * 4000);
    }
  }

  await context.close();
  console.log(JSON.stringify(allTweets));
}

main().catch(() => console.log('[]'));
