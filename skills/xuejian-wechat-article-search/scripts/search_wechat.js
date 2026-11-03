#!/usr/bin/env node

const fs = require('node:fs');
const https = require('node:https');
const zlib = require('node:zlib');
const cheerio = require('cheerio');

const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36',
];

const BASE_HEADERS = {
  Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Encoding': 'gzip, deflate, br',
  'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.7',
  Host: 'weixin.sogou.com',
  Referer: 'https://weixin.sogou.com/',
};

function randomUserAgent() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function decodeBody(buffer, encoding = '') {
  const value = String(encoding).toLowerCase();
  try {
    if (value.includes('br')) return zlib.brotliDecompressSync(buffer);
    if (value.includes('gzip')) return zlib.gunzipSync(buffer);
    if (value.includes('deflate')) return zlib.inflateSync(buffer);
  } catch {
    return buffer;
  }
  return buffer;
}

function request(url, { headers = {}, timeoutMs = 15000 } = {}) {
  return new Promise((resolve, reject) => {
    const target = new URL(url);
    const req = https.request(
      {
        hostname: target.hostname,
        path: `${target.pathname}${target.search}`,
        headers,
      },
      (res) => {
        const chunks = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () => {
          const body = decodeBody(Buffer.concat(chunks), res.headers['content-encoding']);
          resolve({
            statusCode: res.statusCode || 0,
            headers: res.headers,
            text: body.toString('utf8'),
          });
        });
      },
    );
    req.on('error', reject);
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error('request timeout'));
    });
    req.end();
  });
}

async function requestWithRetry(url, options = {}, retries = 1) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await request(url, options);
    } catch (error) {
      lastError = error;
      if (attempt < retries) await sleep(300 + attempt * 500);
    }
  }
  throw lastError;
}

function cookieHeaderFrom(headers) {
  const values = headers['set-cookie'];
  if (!Array.isArray(values)) return '';
  return values.map((item) => item.split(';')[0]).filter(Boolean).join('; ');
}

async function getSogouCookie() {
  try {
    const response = await requestWithRetry('https://v.sogou.com/v?ie=utf8&query=&p=40030600', {
      headers: {
        Accept: BASE_HEADERS.Accept,
        'Accept-Encoding': BASE_HEADERS['Accept-Encoding'],
        'Accept-Language': BASE_HEADERS['Accept-Language'],
        'User-Agent': randomUserAgent(),
      },
      timeoutMs: 10000,
    });
    return cookieHeaderFrom(response.headers);
  } catch {
    return '';
  }
}

function absoluteSogouUrl(value) {
  if (!value) return '';
  if (value.startsWith('//')) return `https:${value}`;
  if (value.startsWith('/')) return `https://weixin.sogou.com${value}`;
  return value;
}

function textOf($, element, selector) {
  return $(element).find(selector).first().text().replace(/\s+/g, ' ').trim();
}

function formatChinaDateTime(date) {
  const shifted = new Date(date.getTime() + 8 * 60 * 60 * 1000);
  const yyyy = shifted.getUTCFullYear();
  const mm = String(shifted.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(shifted.getUTCDate()).padStart(2, '0');
  const hh = String(shifted.getUTCHours()).padStart(2, '0');
  const mi = String(shifted.getUTCMinutes()).padStart(2, '0');
  const ss = String(shifted.getUTCSeconds()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
}

function formatChinaDateText(date) {
  const shifted = new Date(date.getTime() + 8 * 60 * 60 * 1000);
  const yyyy = shifted.getUTCFullYear();
  const mm = String(shifted.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(shifted.getUTCDate()).padStart(2, '0');
  return `${yyyy}年${mm}月${dd}日`;
}

function parseRelativeTime(timeText) {
  const raw = (timeText || '').trim();
  if (!raw) return { datetime: '', dateText: '' };

  const now = new Date();
  const target = new Date(now);
  const rules = [
    [/(\d+)\s*天前/, (n) => target.setDate(target.getDate() - n)],
    [/(\d+)\s*小时前/, (n) => target.setHours(target.getHours() - n)],
    [/(\d+)\s*分钟前/, (n) => target.setMinutes(target.getMinutes() - n)],
  ];
  for (const [pattern, apply] of rules) {
    const match = raw.match(pattern);
    if (match) {
      apply(Number(match[1]));
      return {
        datetime: target.toISOString().slice(0, 19).replace('T', ' '),
        dateText: `${target.getFullYear()}年${String(target.getMonth() + 1).padStart(2, '0')}月${String(target.getDate()).padStart(2, '0')}日`,
      };
    }
  }

  const dateMatch = raw.match(/(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})/);
  if (dateMatch) {
    const date = new Date(Number(dateMatch[1]), Number(dateMatch[2]) - 1, Number(dateMatch[3]));
    return {
      datetime: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} 00:00:00`,
      dateText: `${date.getFullYear()}年${String(date.getMonth() + 1).padStart(2, '0')}月${String(date.getDate()).padStart(2, '0')}日`,
    };
  }

  return { datetime: '', dateText: raw };
}

function dateFieldsFrom($, element) {
  const scriptText = $(element).find('.s-p .s2 script').first().text();
  const timestamp = scriptText.match(/(\d{10})/);
  if (timestamp) {
    const date = new Date(Number(timestamp[1]) * 1000);
    return {
      datetime: formatChinaDateTime(date),
      date_text: formatChinaDateText(date),
      date_description: '',
    };
  }

  const timeText = $(element).find('.s-p .s2').first().clone().children('script').remove().end().text().trim();
  const parsed = parseRelativeTime(timeText);
  return {
    datetime: parsed.datetime,
    date_text: parsed.dateText,
    date_description: timeText || parsed.dateText,
  };
}

function parseArticle($, element) {
  const link = $(element).find('h3 a').first();
  const title = link.text().replace(/\s+/g, ' ').trim();
  if (!title) return null;

  const dateFields = dateFieldsFrom($, element);
  return {
    title,
    url: absoluteSogouUrl(link.attr('href') || ''),
    summary: textOf($, element, 'p.txt-info'),
    datetime: dateFields.datetime,
    date_text: dateFields.date_text,
    date_description: dateFields.date_description || dateFields.date_text,
    source: textOf($, element, '.s-p .all-time-y2') || textOf($, element, '.s-p a.account'),
  };
}

function parseArticlesFromSearchHtml(html, maxResults) {
  const $ = cheerio.load(html || '');
  const articles = [];
  $('ul.news-list li').each((_, element) => {
    if (articles.length >= maxResults) return false;
    const article = parseArticle($, element);
    if (article) articles.push(article);
    return undefined;
  });
  return articles;
}

function extractRedirectUrlFromHtml(html) {
  const text = html || '';
  const meta = text.match(/<meta[^>]+http-equiv=["']refresh["'][^>]+content=["'][^"']*url=([^"']+)["']/i);
  if (meta) return meta[1];

  const direct =
    text.match(/(?:window\.)?location(?:\.href)?\s*=\s*["']([^"']+)["']/i) ||
    text.match(/location\.replace\(\s*["']([^"']+)["']\s*\)/i);
  if (direct) return direct[1];

  const parts = [];
  for (const match of text.matchAll(/url\s*\+=\s*["']([^"']+)["']/g)) {
    parts.push(match[1]);
  }
  const assembled = parts.join('');
  return assembled.includes('mp.weixin.qq.com') ? assembled : null;
}

async function resolveOneUrl(url, cookieHeader) {
  if (!url.includes('weixin.sogou.com')) return { url, resolved: true };
  try {
    const response = await requestWithRetry(url, {
      headers: {
        Accept: BASE_HEADERS.Accept,
        'Accept-Encoding': BASE_HEADERS['Accept-Encoding'],
        'Accept-Language': BASE_HEADERS['Accept-Language'],
        Cookie: cookieHeader,
        'User-Agent': randomUserAgent(),
      },
      timeoutMs: 8000,
    }, 1);
    const location = response.headers.location || extractRedirectUrlFromHtml(response.text);
    if (location && location.includes('mp.weixin.qq.com')) {
      return { url: location, resolved: true };
    }
  } catch {
    // Keep the Sogou link when redirect resolution is blocked.
  }
  return { url, resolved: false };
}

async function resolveRealUrls(articles) {
  const cookieHeader = await getSogouCookie();
  const output = [];
  for (const article of articles) {
    const resolved = await resolveOneUrl(article.url, cookieHeader);
    output.push({
      ...article,
      url: resolved.url,
      url_resolved: resolved.resolved,
    });
    await sleep(500 + Math.random() * 800);
  }
  return output;
}

function parseCliArgs(args) {
  const parsed = {
    query: '',
    num: 10,
    output: '',
    resolveRealUrl: false,
  };
  for (let i = 0; i < args.length; i += 1) {
    const item = args[i];
    if (item === '-n' || item === '--num') {
      parsed.num = Number.parseInt(args[i + 1], 10) || parsed.num;
      i += 1;
    } else if (item === '-o' || item === '--output') {
      parsed.output = args[i + 1] || '';
      i += 1;
    } else if (item === '-r' || item === '--resolve-url') {
      parsed.resolveRealUrl = true;
    } else if (!item.startsWith('-') && !parsed.query) {
      parsed.query = item;
    }
  }
  parsed.num = Math.max(1, Math.min(parsed.num, 50));
  return parsed;
}

async function searchWechatArticles(query, maxResults = 10, resolveRealUrl = false) {
  const limit = Math.max(1, Math.min(Number(maxResults) || 10, 50));
  const cookieHeader = await getSogouCookie();
  const articles = [];
  const pages = Math.ceil(limit / 10);

  for (let page = 1; page <= pages && articles.length < limit; page += 1) {
    const searchUrl = `https://weixin.sogou.com/weixin?type=2&ie=utf8&s_from=input&_sug_=n&page=${page}&query=${encodeURIComponent(query)}`;
    const response = await requestWithRetry(searchUrl, {
      headers: {
        ...BASE_HEADERS,
        Cookie: cookieHeader,
        'User-Agent': randomUserAgent(),
      },
      timeoutMs: 30000,
    }, 1);
    const parsed = parseArticlesFromSearchHtml(response.text, limit - articles.length);
    if (!parsed.length) break;
    articles.push(...parsed);
    if (page < pages) await sleep(500 + Math.random() * 800);
  }

  const result = articles.slice(0, limit);
  return resolveRealUrl ? resolveRealUrls(result) : result;
}

function usage() {
  return [
    '微信公众号文章搜索',
    '',
    'Usage:',
    '  node scripts/search_wechat.js "关键词" [-n 10] [-o result.json] [-r]',
    '',
    'Options:',
    '  -n, --num           result count, 1-50',
    '  -o, --output        write JSON to a file',
    '  -r, --resolve-url   try to resolve Sogou redirect URLs to mp.weixin.qq.com',
  ].join('\n');
}

async function main() {
  const args = parseCliArgs(process.argv.slice(2));
  if (!args.query) {
    console.log(usage());
    return;
  }

  const articles = await searchWechatArticles(args.query, args.num, args.resolveRealUrl);
  const payload = {
    query: args.query,
    total: articles.length,
    articles,
  };
  const json = JSON.stringify(payload, null, 2);
  if (args.output) fs.writeFileSync(args.output, json, 'utf8');
  console.log(json);
}

module.exports = {
  searchWechatArticles,
  parseArticlesFromSearchHtml,
  extractRedirectUrlFromHtml,
  parseCliArgs,
  parseRelativeTime,
  formatChinaDateTime,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(`搜索失败: ${error.message}`);
    process.exit(1);
  });
}
