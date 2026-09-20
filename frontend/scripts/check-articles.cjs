/* Repeatable browser checks with a mocked API; no application data is changed. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const base = process.env.ARTICLE_TEST_URL || 'http://127.0.0.1:4201';
const output = path.resolve('tmp/article-checks');
const now = new Date().toISOString();
const initial = (id, changes = {}) => ({
  id,
  author_id: 7,
  author_name: 'Anna Weber',
  title: 'Ein Vereinsfest für alle',
  slug: 'vereinsfest',
  teaser: '',
  content:
    'Gemeinsam haben wir einen schönen Tag in der Halle verbracht.\n\nVielen Dank an alle Helferinnen und Helfer!',
  article_type: 'EVENT_REPORT',
  visibility: 'PUBLIC',
  status: 'IN_REVIEW',
  event_id: null,
  published_at: null,
  updated_at: now,
  tags: ['verein', 'jugend'],
  cover_image_id: null,
  system_authored: false,
  generated: false,
  ...changes,
});

(async () => {
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    channel: process.env.BROWSER_CHANNEL || 'msedge',
  });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    // External fonts/images are irrelevant to this deterministic local UI check.
    await context.route('https://**/*', (route) => route.abort());
    let role = 'TEAM_REPORTER';
    let articles = [
      initial(1),
      initial(2, {
        author_id: 99,
        author_name: 'System',
        title: 'Herren II gegen TTC Gast',
        slug: 'herren-2-2026-09-17',
        article_type: 'MATCH_REPORT',
        event_id: 9,
        status: 'DRAFT',
        system_authored: true,
        generated: true,
      }),
      initial(3, {
        title: 'Neuigkeiten aus dem Verein',
        slug: 'neuigkeiten',
        status: 'PUBLISHED',
        published_at: now,
      }),
    ];
    const editor = () => role === 'EDITOR' || role === 'ADMIN';
    function dto(article) {
      let actions = [];
      if (article.status === 'ARCHIVED')
        actions = editor() ? ['visibility', 'restore', 'delete'] : [];
      else if (editor() || article.status !== 'PUBLISHED') {
        actions = ['save'];
        if (article.status !== 'PUBLISHED') actions.push('submit');
        if (editor()) {
          actions.push('visibility', 'archive', 'delete');
          if (article.status !== 'PUBLISHED') actions.push('publish');
        }
      }
      return { ...article, allowed_actions: actions };
    }
    await context.route('**/api/**', async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const p = url.pathname;
      const method = request.method();
      const json = (data, status = 200) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
      if (p === '/api/auth/refresh')
        return json({ access_token: 'browser-test', token_type: 'bearer' });
      if (p === '/api/auth/me')
        return json({
          id: 7,
          name: 'Anna Weber',
          email: 'test@example.invalid',
          is_active: true,
          roles: role === 'MEMBER' ? [] : [role],
        });
      if (p === '/api/event-categories') return json([{ id: 1, name: 'Verein', slug: 'verein' }]);
      if (
        p === '/api/admin/articles/opportunities' &&
        url.searchParams.get('group') === 'other_events'
      )
        return json({ team_matches: [], other_events: [], total: 0, offset: 0, limit: 20 });
      if (p === '/api/admin/articles/opportunities')
        return json({
          team_matches: [
            {
              event_id: 9,
              title: 'Herren II gegen TTC Gast',
              starts_at: now,
              team_match_id: 90,
              article_id: 2,
            },
          ],
          other_events: [],
          total: 1,
          offset: 0,
          limit: 20,
        });
      if (p === '/api/admin/articles/prepare/9')
        return json({
          ...articles.find((a) => a.id === 2),
          id: undefined,
          article_id: 2,
          editable_fields: ['title', 'teaser', 'content', 'visibility', 'tags', 'cover_image_id'],
        });
      if (
        method === 'GET' &&
        ['/api/admin/articles', '/api/articles', '/api/intern/articles'].includes(p)
      ) {
        const scope = url.searchParams.get('scope');
        let selected = articles;
        if (scope === 'mine') selected = selected.filter((a) => a.author_id === 7);
        if (p !== '/api/admin/articles')
          selected = selected.filter(
            (a) =>
              a.status === 'PUBLISHED' &&
              a.visibility !== 'HIDDEN' &&
              (p.includes('/intern/') || a.visibility === 'PUBLIC'),
          );
        const statuses = url.searchParams.getAll('status');
        const since = url.searchParams.get('updated_since');
        if (since) selected = selected.filter((a) => Date.parse(a.updated_at) >= Date.parse(since));
        if (statuses.length) selected = selected.filter((a) => statuses.includes(a.status));
        const type = url.searchParams.get('article_type');
        if (type) selected = selected.filter((a) => a.article_type === type);
        const offset = Number(url.searchParams.get('offset') || 0);
        const limit = Number(url.searchParams.get('limit') || 20);
        return json({
          items: selected.slice(offset, offset + limit).map(dto),
          total: selected.length,
          offset,
          limit,
        });
      }
      if (method === 'GET' && /^\/api\/(intern\/)?articles\//.test(p)) {
        const article = articles.find((a) => a.slug === decodeURIComponent(p.split('/').at(-1)));
        return article ? json(dto(article)) : json({ detail: 'Nicht gefunden' }, 404);
      }
      const match = p.match(/^\/api\/admin\/articles\/(\d+)(?:\/(\w+))?$/);
      if (match) {
        const article = articles.find((a) => a.id === Number(match[1]));
        if (!article) return json({ detail: 'Nicht gefunden' }, 404);
        const action = match[2];
        if (method === 'DELETE') {
          articles = articles.filter((a) => a !== article);
          return route.fulfill({ status: 204 });
        }
        if (method === 'GET') return json(dto(article));
        if (action === 'visibility') article.visibility = request.postDataJSON().visibility;
        else if (action === 'archive') article.status = 'ARCHIVED';
        else if (action === 'restore') {
          article.status = 'DRAFT';
          article.published_at = null;
        } else if (action === 'publish') {
          article.status = 'PUBLISHED';
          article.published_at = now;
        } else {
          Object.assign(article, request.postDataJSON());
          article.author_id = 7;
          article.author_name = 'Anna Weber';
          article.system_authored = false;
          if (action === 'submit') article.status = 'IN_REVIEW';
        }
        return json(dto(article));
      }
      return json({ detail: 'Unexpected test request: ' + method + ' ' + p }, 500);
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('dialog', (dialog) => dialog.accept());
    let checks = 0;
    async function visit(url, selector, name) {
      await page.goto(base + url, { waitUntil: 'domcontentloaded' });
      await page.locator(selector + ' h1').waitFor();
      await page
        .locator(selector + ' [role="status"]')
        .filter({ hasText: /wird geladen|werden geladen/ })
        .waitFor({ state: 'hidden' });
      await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
      const violations = await page.evaluate(
        async (selector) =>
          (
            await axe.run(document.querySelector(selector), {
              runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
            })
          ).violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
        selector,
      );
      assert.deepEqual(violations, [], 'Axe: ' + name + ' ' + JSON.stringify(violations));
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
        false,
        'Horizontal overflow: ' + name,
      );
      await page.screenshot({ path: path.join(output, name + '.png'), fullPage: true });
      checks++;
    }
    await visit('/admin/articles/new', 'app-article-create', 'new-desktop');
    assert.equal(await page.getByRole('link', { name: 'Redaktion', exact: true }).count(), 0);
    await visit('/admin/articles/event/9', 'app-article-editor', 'editor-desktop');
    assert.equal(await page.getByLabel('Linkname', { exact: true }).isDisabled(), true);
    const slug = await page.getByLabel('Linkname', { exact: true }).inputValue();
    await page.getByLabel('Titel', { exact: true }).fill('Ein neuer Titel für das Spiel');
    assert.equal(await page.getByLabel('Linkname', { exact: true }).inputValue(), slug);
    await page.getByRole('button', { name: 'Einreichen', exact: true }).click();
    await page.waitForURL('**/admin/articles/2/edit');
    assert.equal(articles.find((a) => a.id === 2).status, 'IN_REVIEW');
    assert.equal(articles.find((a) => a.id === 2).teaser, '');
    await visit('/admin/articles/drafts', 'app-article-list', 'mine-desktop');
    await visit('/admin/articles/3/edit', 'app-article-editor', 'readonly-desktop');
    assert.equal(await page.locator('app-article-editor form').count(), 0);
    role = 'EDITOR';
    await visit('/admin/articles/list', 'app-article-list', 'editorial-desktop');
    assert.equal(await page.getByRole('link', { name: 'Neuer Beitrag', exact: true }).count(), 1); // Sidebar only.
    assert.equal(await page.locator('#article-period').count(), 0);
    await page.getByRole('button', { name: 'Alle', exact: true }).click();
    await page.getByLabel(/Sichtbarkeit: Ein Vereinsfest für alle/).click();
    await page.getByRole('button', { name: 'Nur Mitglieder', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Sichtbarkeit geändert.' }).waitFor();
    assert.equal(articles.find((a) => a.id === 1).visibility, 'MEMBERS_ONLY');
    await page
      .getByRole('button', { name: 'Ein Vereinsfest für alle archivieren', exact: true })
      .click();
    await page
      .getByRole('button', { name: 'Ein Vereinsfest für alle wiederherstellen', exact: true })
      .waitFor();
    await page
      .getByRole('button', { name: 'Ein Vereinsfest für alle wiederherstellen', exact: true })
      .click();
    await page.getByRole('status').filter({ hasText: 'als Entwurf wiederhergestellt' }).waitFor();
    assert.equal(articles.find((a) => a.id === 1).status, 'DRAFT');
    await page.getByLabel('Weitere Aktionen: Ein Vereinsfest für alle', { exact: true }).click();
    await page
      .getByRole('button', { name: 'Ein Vereinsfest für alle löschen', exact: true })
      .click();
    await page.getByRole('status').filter({ hasText: 'Beitrag gelöscht.' }).waitFor();
    assert.equal(
      articles.some((a) => a.id === 1),
      false,
    );
    await visit('/news', 'app-article-feed', 'news-desktop');
    await visit('/news/neuigkeiten', 'app-article-detail', 'detail-desktop');
    role = 'MEMBER';
    await visit('/intern/articles', 'app-article-feed', 'member-desktop');
    await page.setViewportSize({ width: 390, height: 844 });
    role = 'EDITOR';
    await visit('/admin/articles/list', 'app-article-list', 'editorial-mobile');
    const visibilityTrigger = page.locator('.article-controls > .action-menu summary').first();
    await visibilityTrigger.focus();
    await page.keyboard.press('Enter');
    await page.getByRole('group', { name: 'Sichtbarkeit wählen' }).waitFor();
    await page.keyboard.press('Tab');
    assert.equal(
      await page
        .getByRole('button', { name: 'Öffentlich', exact: true })
        .evaluate((el) => el === document.activeElement),
      true,
    );
    const menuViolations = await page.evaluate(async () =>
      (
        await axe.run(document.querySelector('app-article-list'), {
          runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
        })
      ).violations.map((v) => v.id),
    );
    assert.deepEqual(menuViolations, []);
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    await page.screenshot({
      path: path.join(output, 'visibility-menu-mobile.png'),
      fullPage: true,
    });
    await page.keyboard.press('Escape');
    assert.equal(await visibilityTrigger.evaluate((el) => el === document.activeElement), true);
    assert.equal(await page.locator('.article-controls > details[open]').count(), 0);
    await visit('/admin/articles/write', 'app-article-editor', 'editor-mobile');
    const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
    let imageCaption = null;
    await context.route('**/api/admin/media/images**', async route => {
      if (route.request().url().endsWith('/caption')) {
        if (route.request().method() === 'PATCH') imageCaption = route.request().postDataJSON().caption;
        await route.fulfill({ json: { caption: imageCaption } });
        return;
      }
      if (route.request().method() === 'POST') {
        await route.fulfill({ json: { id: 42, width: 1, height: 1, mime_type: 'image/webp', file_size: png.length } });
      } else {
        assert.ok(route.request().headers()['authorization']);
        await route.fulfill({ contentType: 'image/png', body: png });
      }
    });
    const uploadTrigger = page.getByRole('button', { name: 'Bild hochladen', exact: true });
    await uploadTrigger.click();
    const dialog = page.getByRole('dialog');
    await dialog.waitFor();
    assert.equal(await dialog.getByRole('button', { name: 'Datei auswählen' }).evaluate(el => el === document.activeElement), true);
    await dialog.locator('input[type=file]').setInputFiles({ name: 'team.png', mimeType: 'image/png', buffer: png });
    await dialog.getByRole('button', { name: 'team.png entfernen' }).click();
    await dialog.locator('img').waitFor({ state: 'detached' });
    assert.equal(await dialog.locator('img').count(), 0);
    await dialog.evaluate((el, bytes) => {
      const transfer = new DataTransfer();
      transfer.items.add(new File([new Uint8Array(bytes)], 'drop.png', { type: 'image/png' }));
      el.querySelector('.drop-zone').dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }));
    }, [...png]);
    await dialog.getByRole('button', { name: 'drop.png entfernen' }).waitFor();
    assert.equal(await dialog.getByLabel('Bildunterschrift (optional)').count(), 0);
    const uploadViolations = await page.evaluate(async () => (await axe.run(document.querySelector('dialog'), {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
    })).violations.map(v => v.id));
    assert.deepEqual(uploadViolations, []);
    await page.screenshot({ path: path.join(output, 'media-upload-mobile.png'), fullPage: true });
    await dialog.getByRole('button', { name: 'Bild hochladen', exact: true }).click();
    await page.locator('app-media-preview img').waitFor();
    await page.getByRole('dialog').waitFor({ state: 'detached' });
    assert.equal(await page.getByRole('dialog').count(), 0);
    await page.locator('app-media-caption textarea:not(:disabled)').waitFor();
    assert.equal(await page.locator('app-media-caption textarea').inputValue(), '');
    await page.locator('app-media-caption textarea').fill('Kreismeisterschaften 2026');
    await page.getByRole('button', { name: 'Bildunterschrift speichern', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Bildunterschrift gespeichert.' }).waitFor();
    assert.equal(imageCaption, 'Kreismeisterschaften 2026');
    await page.getByRole('button', { name: 'Bild ersetzen' }).click();
    await page.locator('dialog[open]').waitFor();
    await page.keyboard.press('Escape');
    await page.getByRole('dialog').waitFor({ state: 'detached' });
    assert.equal(await page.getByRole('button', { name: 'Bild ersetzen' }).evaluate(el => el === document.activeElement), true);
    await page.getByLabel('Zusätzlich einen Event anlegen').check();
    await page.getByLabel('Kategorie', { exact: true }).selectOption({ label: 'Verein' });
    await page.screenshot({ path: path.join(output, 'optional-event-mobile.png'), fullPage: true });
    await visit('/news', 'app-article-feed', 'news-mobile');
    assert.deepEqual(errors, [], 'Browser runtime errors');
    console.log(
      checks +
        ' responsive views passed Axe AA; reporting, permissions and editorial actions passed.',
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
