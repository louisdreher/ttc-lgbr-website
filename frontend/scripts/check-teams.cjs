const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
(async () => {
 const browser = await chromium.launch({channel:'msedge', headless:true});
 try {
 const page = await browser.newPage();
 const errors = [];
 let players = [{player_id:1,first_name:'Anna',last_name:'Test',position:1,status:null,media_id:null}];
 page.on('pageerror', error => errors.push(error.message));
 await page.route('https://**/*', r => r.abort());
 await page.route('**/api/**', async r => {
 const url = new URL(r.request().url());
 const p = url.pathname;
 const json = body => r.fulfill({json:body});
 if(p === '/api/auth/refresh') return json({access_token:'test',token_type:'bearer'});
 if(p === '/api/auth/me') return json({id:1,name:'Admin',email:'admin@example.test',roles:['ADMIN'],is_active:true});
 if(p === '/api/admin/media/images' && r.request().method() === 'POST') return json({id:42,mime_type:'image/webp',file_size:100,width:692,height:865});
 if(p === '/api/admin/media/images/42') return r.fulfill({contentType:'image/png',body:await fs.readFile('public/images/player-placeholder.png')});
 if(p === '/api/competition/teams/1/lineup/1/image' && r.request().method() === 'PUT') {
   assert.deepEqual(r.request().postDataJSON(), {media_id:42});
   players[0].media_id = 42;
   return r.fulfill({status:204});
 }
 if(p === '/api/competition/seasons') return json([{id:2,start_year:2026,end_year:2027,half:'rr'}, {id:1,start_year:2009,end_year:2010,half:'vr'}]);
 if(p === '/api/competition/teams') return json(url.searchParams.get('season_id') === '1' ? [
 {id:1,name:'Herren III',team_number:3,category:'H'}, {id:2,name:'Herren IV',team_number:4,category:'H'}
 ] : []);
 if(p === '/api/competition/teams/1/lineup') return json({team_id:1,team_name:'Herren III',season_id:1,category:'H',players});
 if(p === '/api/competition/teams/1/candidates') return json(players.some(player => player.player_id === 2) ? [] : [{player_id:2,first_name:'Ben',last_name:'Test',team_number:3,rank:'2'}]);
 if(p === '/api/competition/teams/1/lineup/2' && r.request().method() === 'PUT') {
   players.push({player_id:2,first_name:'Ben',last_name:'Test',position:2,status:null,media_id:null});
   return r.fulfill({status:204});
 }
 if(p === '/api/competition/teams/1/lineup/2' && r.request().method() === 'DELETE') {
   players = players.filter(player => player.player_id !== 2);
   return r.fulfill({status:204});
 }
 return json([]);
 });
 await fs.mkdir('tmp/team-checks', {recursive:true});
 async function check(name) {
 await page.addScriptTag({path:require.resolve('axe-core/axe.min.js')});
 for (const width of [1280,390]) {
 await page.setViewportSize({width,height:900});
 const result=await page.evaluate(() => window.axe.run(document.querySelector('dialog[open]') || 'main',{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
 assert.deepEqual(result.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[], name);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth),true);
 await page.screenshot({path:`tmp/team-checks/${name}-${width}.png`,fullPage:true,animations:'disabled'});
 }
 }
 await page.goto('http://127.0.0.1:4217/admin/teams');
 await page.getByLabel('Saison und Halbserie').selectOption('1');
 await page.getByRole('link',{name:'Herren III bearbeiten'}).waitFor();
 assert.equal(new URL(page.url()).searchParams.get('season'),'1');
 assert.equal(await page.locator('.team-row').count(),2);
 await check('list');
 await page.getByRole('link',{name:'Herren III bearbeiten'}).click();
 await page.getByText('Anna Test',{exact:false}).waitFor();
 assert.equal(new URL(page.url()).pathname,'/admin/teams/1');
 const placeholder = page.getByAltText('Kein Spielerfoto vorhanden');
 await placeholder.evaluate(img => img.decode());
 assert.equal(await placeholder.evaluate(img => img.naturalWidth), 692);
 await check('detail');
 await page.getByRole('button',{name:'Anna Test: Bild hochladen',exact:true}).click();
 await page.getByRole('dialog',{name:'Bild hochladen',exact:true}).waitFor();
 await page.locator('input[type=file]').setInputFiles('public/images/player-placeholder.png');
 await check('image-upload');
 await page.getByRole('button',{name:'Bild hochladen',exact:true}).click();
 await page.getByRole('dialog').waitFor({state:'detached'});
 await page.getByRole('button',{name:'Anna Test: Bild wechseln',exact:true}).waitFor();
 await check('image-updated');
 await page.getByRole('button',{name:'Spieler hinzufügen',exact:true}).click();
 await page.getByRole('dialog',{name:'Spieler auswählen'}).waitFor();
 await page.getByRole('button',{name:'Ben Test hinzufügen'}).waitFor();
 assert.equal(await page.getByRole('dialog').locator('select').count(),0);
 assert.equal(await page.getByLabel('Name oder Meldeposition suchen').evaluate(input => document.activeElement === input),true);
 await page.getByLabel('Name oder Meldeposition suchen').fill('Nobody');
 await page.getByText('Keine Spieler für diese Suche gefunden.').waitFor();
 await page.getByLabel('Name oder Meldeposition suchen').fill('Ben');
 await check('player-picker');
 await page.keyboard.press('Escape');
 await page.getByRole('dialog').waitFor({state:'detached'});
 assert.equal(await page.getByRole('button',{name:'Spieler hinzufügen',exact:true}).evaluate(button => document.activeElement === button),true);
 await page.getByRole('button',{name:'Spieler hinzufügen',exact:true}).click();
 await page.getByRole('button',{name:'Ben Test hinzufügen'}).click();
 await page.getByRole('dialog').waitFor({state:'detached'});
 await page.getByRole('button',{name:'Ben Test aus Mannschaft entfernen'}).waitFor();
 await page.getByRole('button',{name:'Ben Test aus Mannschaft entfernen'}).click();
 await check('remove-confirmation');
 await page.getByRole('button',{name:'Entfernen bestätigen'}).click();
 await page.getByRole('button',{name:'Ben Test aus Mannschaft entfernen'}).waitFor({state:'detached'});
 await page.getByRole('link',{name:'Zurück zur Übersicht',exact:false}).click();
 await page.getByRole('link',{name:'Herren III bearbeiten'}).waitFor();
 assert.equal(await page.getByLabel('Saison und Halbserie').inputValue(),'1');
 await page.reload();
 await page.getByRole('link',{name:'Herren III bearbeiten'}).waitFor();
 assert.equal(await page.getByLabel('Saison und Halbserie').inputValue(),'1');
 assert.deepEqual(errors,[]);
 console.log('List/detail navigation, persisted season, desktop/mobile and WCAG AA checks passed.');
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
