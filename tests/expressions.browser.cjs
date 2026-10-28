// Run against a synthetic loopback project with an owner discussion message.
// BOARD_TEST_URL selects the fixture; NODE_PATH supplies the optional Playwright runtime.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const base=process.env.BOARD_TEST_URL;
let browser;
before(async()=>{
 if(!base)return;
 const url=new URL(base);assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');
 const {chromium}=require('playwright');
 browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
});
after(async()=>{await browser?.close();});

for(const theme of ['default','pink'])test(`${theme}: own portrait picker persists a role-bound mood and character reactions follow the separator`,{skip:!base},async()=>{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 try{
  await page.addInitScript(theme=>{localStorage.setItem('boardTheme',theme);localStorage.setItem('dockOpen','1');},theme);
  await page.goto(base);const snapshot=await page.evaluate(()=>AvatarMoods.ready);
  const owner=Object.keys(snapshot.actors).find(id=>snapshot.actors[id]==='owner');
  const choices=snapshot.items.filter(row=>row.role==='owner');
  assert(choices.length>=20);assert.equal(snapshot.items.filter(row=>row.collection==='original-60').length,60);
  const self=page.locator(`#room-threads .room-avatar[data-mention-id="${owner}"]`).first();await self.waitFor();await self.click();
  const picker=page.locator('dialog.avatar-mood-picker');await picker.waitFor({state:'visible'});
  assert.equal(await picker.locator('.avatar-mood-option').count(),choices.length);
  const chosen=choices.find(row=>row.collection==='original-60');
  await picker.locator(`[data-expression="${chosen.key}"]`).click();await picker.waitFor({state:'hidden'});
  const saved=await page.evaluate(async()=>await (await fetch('/api/expressions')).json());
  assert.equal(saved.moods.owner.mood,chosen.key);
  assert.deepEqual(saved.moods.claude,snapshot.moods.claude);assert.deepEqual(saved.moods.gpt,snapshot.moods.gpt);
  await page.reload();await page.evaluate(()=>AvatarMoods.ready);
  assert.equal(await page.evaluate(()=>AvatarMoods.current(BoardIdentity.me.id).key),chosen.key);
  await page.locator('#room-threads .room-reaction-add').first().click();
  const grid=page.locator('.room-reaction-picker:not([hidden]) .room-reaction-grid');
  const within=await grid.evaluate(node=>{const picker=node.closest('.room-reaction-picker').getBoundingClientRect(),log=node.closest('.room-threads').getBoundingClientRect();return picker.top>=log.top&&picker.bottom<=log.bottom;});
  assert(within,'the first-message picker stays inside the visible discussion log');
  assert.equal(await grid.locator('.room-reaction-separator').count(),1);
  const count=await grid.locator('.room-reaction-separator').evaluate(line=>{let total=0;for(let next=line.nextElementSibling;next;next=next.nextElementSibling)if(next.tagName==='BUTTON')total++;return total;});
  assert.equal(count,snapshot.items.length);assert.equal(await grid.locator('input,h1,h2,h3').count(),0);
  assert.equal(await page.locator('.room-mood-sticker').count(),0);
  await page.keyboard.press('Escape');
  assert.deepEqual(errors,[]);
 }finally{await page.close();}
});
