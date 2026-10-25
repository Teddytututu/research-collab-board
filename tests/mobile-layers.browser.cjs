// Run with node --test; use the installed Playwright runtime via NODE_PATH.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
let playwrightPath,chromium,skipReason;
try{playwrightPath=require.resolve('playwright');}
catch(error){
  if(error.code!=='MODULE_NOT_FOUND'||error.message.split('\n')[0]!=="Cannot find module 'playwright'")throw error;
  skipReason='Optional browser tests: install Playwright to run (npm install --no-save playwright).';
}
if(playwrightPath)({chromium}=require(playwrightPath));
const assets=fs.existsSync(path.join(__dirname,'../board/discussion.css'))?path.join(__dirname,'../board'):path.join(__dirname,'..');
let browser;
before(async()=>{
  if(skipReason)return;
  try{browser=await chromium.launch({headless:true});}
  catch(error){
    if(!/^browserType\.launch: Executable doesn't exist at [^\r\n]+/.test(error.message))throw error;
    skipReason='Optional browser tests: install the Chromium browser (npx playwright install chromium).';
  }
});
after(async()=>{await browser?.close();});

for(const theme of ['default','pink'])for(const width of [320,390,768,1024,1440]){
  test(`${theme} ${width}px: latest control paints above message metadata and below modal`,async t=>{
    if(skipReason){t.skip(skipReason);return;}
    const page=await browser.newPage({viewport:{width,height:844},hasTouch:true});
    try{
      await page.setContent(`<!doctype html><html class="theme-${theme}"><body>
        <section id="msgs"><div class="room-log-wrap">
          <div id="room-threads" class="room-threads"><article class="room-message by-gpt">
            <div class="room-message-content"><div class="room-meta"><span class="room-author">GPT</span><time>00:45</time></div>
            <div class="room-bubble">手机上的消息</div></div></article></div>
          <button id="room-latest" class="room-latest">↓ 回到最新消息 · 999 条未读</button>
        </div></section><dialog class="room-delete-dialog"><h2>撤回消息</h2><button>取消</button></dialog>
      </body></html>`);
      await page.addStyleTag({content:'body{margin:0}#msgs{width:min(400px,100%)}.room-log-wrap{height:400px}.room-threads{box-sizing:border-box;height:400px!important;min-height:0!important}.room-message-content{width:100%}'});
      for(const name of ['discussion.css','room-features.css'])await page.addStyleTag({content:fs.readFileSync(path.join(assets,name),'utf8')});
      // Align real theme metadata under the floating control, as in the report.
      const result=await page.evaluate(()=>{
        const button=document.querySelector('#room-latest'),meta=document.querySelector('.room-meta');
        const b=button.getBoundingClientRect(),m=meta.getBoundingClientRect();
        meta.style.transform=`translate(${b.left+8-m.left}px,${b.top+8-m.top}px)`;
        const point={x:b.left+12,y:b.top+12};
        return {hit:document.elementFromPoint(point.x,point.y)?.closest('button')?.id,
          left:b.left,right:b.right,height:b.height,overflow:document.documentElement.scrollWidth>innerWidth};
      });
      assert.equal(result.hit,'room-latest','metadata must stay inside the message scroll layer');
      assert.ok(result.left>=0 && result.right<=width,'control fits the viewport');
      assert.ok(result.height>=44,'touch target is at least 44px');
      assert.equal(result.overflow,false);
      await page.evaluate(()=>{document.querySelector('#room-latest').onclick=e=>{e.currentTarget.hidden=true;};});
      await page.locator('#room-latest').tap();
      assert.equal(await page.locator('#room-latest').isVisible(),false);
      await page.evaluate(()=>{document.querySelector('#room-latest').hidden=false;document.querySelector('dialog').showModal();});
      assert.equal(await page.locator('dialog button').evaluate(el=>el===document.activeElement),true);
      assert.equal(await page.evaluate(()=>{const d=document.querySelector('dialog'),b=d.getBoundingClientRect();return document.elementFromPoint(b.left+b.width/2,b.top+b.height/2)?.closest('dialog')===d;}),true);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('dialog').evaluate(el=>el.open),false);
    }finally{await page.close();}
  });
}
