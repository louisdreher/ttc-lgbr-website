/* Browser and accessibility checks against a mocked API; no real accounts/mail. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const output = path.resolve('tmp/user-checks');
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    channel: process.env.BROWSER_CHANNEL || 'msedge',
  });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.route('https://**/*', (route) => route.abort());
    const member = {
      id: 10,
      first_name: 'Anna',
      last_name: 'Weber',
      email: 'anna@example.org',
      is_active: true,
      birth_date: null,
      joined_at: '2020-01-01',
      eligible_since: null,
      ttc_eligible_since: null,
      membership_end_date: null,
      phone: null,
      mobile: null,
      street: null,
      house_number: null,
      postal_code: null,
      city: null,
    };
    let users = [
      {
        id: 1,
        name: 'Max Muster',
        email: 'max@example.org',
        roles: ['ADMIN'],
        is_active: true,
        member_id: null,
        member: null,
        created_at: new Date().toISOString(),
      },
      {
        id: 2,
        name: 'Anna Weber',
        email: 'anna@example.org',
        roles: ['EDITOR'],
        is_active: true,
        member_id: 10,
        member,
        created_at: new Date().toISOString(),
      },
    ];
    let mailCount = 0;
    let saved = null;
    let password = null;
    await context.route('**/api/**', async (route) => {
      const request = route.request(),
        url = new URL(request.url()),
        p = url.pathname,
        method = request.method();
      const json = (value, status = 200) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
      const empty = () => route.fulfill({ status: 204 });
      if (p === '/api/auth/refresh') return json({ access_token: 'test', token_type: 'bearer' });
      if (p === '/api/auth/me') return json(users[0]);
      if (p === '/api/auth/set-password') {
        password = request.postDataJSON();
        return empty();
      }
      if (p === '/api/admin/users/members')
        return json([
          { id: 10, first_name: 'Anna', last_name: 'Weber', user_id: 2 },
          { id: 11, first_name: 'Eva', last_name: 'Klein', user_id: null },
        ]);
      if (p === '/api/admin/users/members/11')
        return json({ ...member, id: 11, first_name: 'Eva', last_name: 'Klein' });
      if (p === '/api/admin/users' && method === 'GET') {
        let filtered = users;
        const search = url.searchParams.get('search');
        if (search)
          filtered = users.filter((user) => user.name.toLowerCase().includes(search.toLowerCase()));
        return json({ items: filtered, total: filtered.length });
      }
      if (p === '/api/admin/users' && method === 'POST') {
        saved = request.postDataJSON();
        users.push({ ...saved, id: 3, created_at: new Date().toISOString() });
        return json({ id: 3 }, 201);
      }
      const role = p.match(/^\/api\/users\/(\d+)\/roles\/(.+)$/);
      if (role) {
        const user = users.find((user) => user.id === Number(role[1]));
        user.roles =
          method === 'PUT'
            ? [...new Set([...user.roles, role[2]])]
            : user.roles.filter((r) => r !== role[2]);
        return json({ message: 'OK' });
      }
      const item = p.match(/^\/api\/admin\/users\/(\d+)(.*)$/);
      if (item) {
        const id = Number(item[1]),
          suffix = item[2],
          user = users.find((u) => u.id === id);
        if (suffix === '/password-link') {
          mailCount++;
          return empty();
        }
        if (suffix === '/active') {
          user.is_active = request.postDataJSON().is_active;
          return empty();
        }
        if (method === 'DELETE') {
          users = users.filter((u) => u.id !== id);
          return empty();
        }
        if (method === 'PUT') {
          Object.assign(user, request.postDataJSON());
          return empty();
        }
        return json(user);
      }
      return json({ detail: 'Unexpected mock request ' + p }, 404);
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('dialog', (dialog) => dialog.accept());
    const base = process.env.USERS_TEST_URL || 'http://127.0.0.1:4202';
    async function axe(name) {
      await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
      const result = await page.evaluate(async () =>
        window.axe.run('main', {
          runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
        }),
      );
      assert.deepEqual(
        result.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
        [],
        name,
      );
      await page.screenshot({ path: path.join(output, name + '.png'), fullPage: true });
    }
    await page.goto(base + '/admin/users');
    await page.getByRole('link', { name: 'Anna Weber', exact: true }).waitFor();
    await axe('list-desktop');
    const anna = page
      .getByRole('row')
      .filter({ has: page.getByRole('link', { name: 'Anna Weber', exact: true }) });
    assert.equal(await anna.locator('input[type="checkbox"]').count(), 0);
    await anna.getByText('Redaktion', { exact: true }).waitFor();
    await anna.getByRole('link', { name: 'Anna Weber bearbeiten' }).click();
    await page.getByLabel('Mannschaftsberichte', { exact: true }).check();
    await page.getByRole('button', { name: 'Benutzer speichern', exact: true }).click();
    await page.getByText('Benutzer gespeichert.', { exact: true }).waitFor();
    await anna.getByText('Redaktion, Mannschaftsberichte', { exact: true }).waitFor();
    assert(users[1].roles.includes('TEAM_REPORTER'));
    await anna.getByRole('button', { name: 'Passwort für Anna Weber zurücksetzen' }).click();
    await page
      .getByText('Passwort-Link wurde an anna@example.org gesendet.', { exact: true })
      .waitFor();
    assert.equal(mailCount, 1);
    await anna.getByRole('button', { name: 'Deaktivieren', exact: true }).click();
    await anna.getByText('Deaktiviert', { exact: true }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await axe('list-mobile');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.getByRole('link', { name: 'Benutzer anlegen', exact: true }).click();
    await page.getByLabel('Anzeigename *', { exact: true }).fill('Eva Klein');
    await page.getByLabel('Anmelde-E-Mail *', { exact: true }).fill('eva@example.org');
    await page.getByLabel('Zuordnung', { exact: true }).selectOption('existing');
    await page.getByLabel('Mitglied *', { exact: true }).selectOption('11');
    await page.getByLabel('Vorname *', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('Vorname *', { exact: true }).inputValue(), 'Eva');
    await axe('form-mobile');
    await page.setViewportSize({ width: 1440, height: 1000 });
    await axe('form-desktop');
    await page.getByRole('button', { name: 'Benutzer speichern', exact: true }).click();
    await page.getByText('Benutzer angelegt. Einladungslink versendet.', { exact: true }).waitFor();
    assert.equal(saved.member_id, 11);
    assert.equal(saved.member.first_name, 'Eva');
    assert.equal(mailCount, 2);
    await page.getByLabel('Name oder E-Mail', { exact: true }).fill('Eva');
    await page.getByRole('button', { name: 'Filtern', exact: true }).click();
    await page.getByText('1 Benutzer gefunden', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Eva Klein löschen', exact: true }).click();
    await page.getByText('Keine Benutzer für diese Auswahl gefunden.', { exact: true }).waitFor();
    await page.goto(base + '/passwort-festlegen#token=' + 't'.repeat(43));
    await page.getByLabel('Neues Passwort', { exact: true }).waitFor();
    assert(!page.url().includes('#'));
    await axe('password-desktop');
    await page.getByLabel('Neues Passwort', { exact: true }).fill('my-new-secure-password');
    await page.getByLabel('Passwort wiederholen', { exact: true }).fill('my-new-secure-password');
    await page.getByRole('button', { name: 'Passwort speichern', exact: true }).click();
    await page.getByRole('link', { name: 'Zur Anmeldung', exact: true }).waitFor();
    assert.equal(password.token, 't'.repeat(43));
    assert.deepEqual(errors, []);
    console.log('Users browser flows and WCAG AA checks passed; screenshots:', output);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
