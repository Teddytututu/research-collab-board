// Optional live-browser acceptance against a fictional project on a loopback listener.
// BOARD_TEST_URL supplies the isolated test server; NODE_PATH supplies Playwright.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
let chromium,browser;
const base=process.env.BOARD_TEST_URL;
const enabled=!!base;
if(enabled){
  const url=new URL(base);
  assert.equal(url.protocol,'http:');assert.equal(url.hostname,'127.0.0.1');
  ({chromium}=require('playwright'));
}
before(async()=>{if(enabled)browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});});
after(async()=>{await browser?.close();});
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4l8AAAAASUVORK5CYII=','base64');
const upload={name:'example.png',mimeType:'image/png',buffer:png};

async function pageAt(width=1440,theme='default'){
  const page=await browser.newPage({viewport:{width,height:940}});
  await page.addInitScript(theme=>{localStorage.setItem('dockOpen','1');localStorage.setItem('boardTheme',theme);},theme);
  await page.goto(base);await page.locator('.private-entry button').first().waitFor();
  return page;
}
const privateInput=page=>page.locator('#private-text');
const peerButton=(page,peer)=>page.locator('#private-chat .private-peers button').filter({hasText:peer});

test('separate peer drafts, public draft, Enter and Shift+Enter, IME and failed retry',{skip:!enabled},async()=>{
  const page=await pageAt();const errors=[];page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.locator('#room-text').fill('Public draft fixture');
    await page.getByRole('button',{name:'私聊 GPT',exact:true}).click();
    await privateInput(page).fill('GPT draft fixture');
    await peerButton(page,'Claude').click();await assert.equal(await privateInput(page).inputValue(),'');
    await privateInput(page).fill('Claude draft fixture');
    await peerButton(page,'GPT').click();assert.equal(await privateInput(page).inputValue(),'GPT draft fixture');
    await privateInput(page).press('Shift+Enter');assert.equal(await privateInput(page).inputValue(),'GPT draft fixture\n');
    await privateInput(page).dispatchEvent('keydown',{key:'Enter',isComposing:true,keyCode:229});
    assert.equal(await privateInput(page).inputValue(),'GPT draft fixture\n');
    const text='GPT message '+Date.now();await privateInput(page).fill(text);
    await page.route('**/api/private?peer=GPT',async route=>{
      if(route.request().method()==='POST')await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Example retry error'})});
      else await route.continue();
    });
    await privateInput(page).press('Enter');await page.getByRole('status').filter({hasText:'Example retry error'}).waitFor();
    assert.equal(await privateInput(page).inputValue(),text);
    await page.unroute('**/api/private?peer=GPT');await privateInput(page).press('Enter');
    await page.locator('#private-chat .room-body').filter({hasText:text}).waitFor();assert.equal(await privateInput(page).inputValue(),'');
    await peerButton(page,'Claude').click();assert.equal(await privateInput(page).inputValue(),'Claude draft fixture');
    assert.equal(await page.locator('#private-chat .room-body').filter({hasText:text}).count(),0);
    await page.getByRole('button',{name:'返回讨论室',exact:true}).click();
    assert.equal(await page.locator('#room-text').inputValue(),'Public draft fixture');
    assert.equal(await page.locator('#room-threads .room-body').filter({hasText:text}).count(),0);
    assert.deepEqual(errors,[]);
  }finally{await page.close();}
});

test('select, paste, drop, peer image drafts, thumbnail removal, viewer and focus',{skip:!enabled},async()=>{
  const page=await pageAt();
  try{
    await page.getByRole('button',{name:'私聊 GPT',exact:true}).click();
    await page.locator('#private-chat input[type=file]').setInputFiles(upload);
    assert.equal(await page.locator('#private-attach .thumb').count(),1);
    await peerButton(page,'Claude').click();assert.equal(await page.locator('#private-attach .thumb').count(),0);
    await peerButton(page,'GPT').click();assert.equal(await page.locator('#private-attach .thumb').count(),1);
    await page.getByRole('button',{name:'移除这份附件',exact:true}).click();
    assert.equal(await page.locator('#private-attach .thumb').count(),0);
    await privateInput(page).evaluate((input,bytes)=>{
      const clipboard=new DataTransfer();clipboard.items.add(new File([new Uint8Array(bytes)],'pasted.png',{type:'image/png'}));
      input.dispatchEvent(new ClipboardEvent('paste',{clipboardData:clipboard,bubbles:true,cancelable:true}));
    },[...png]);
    assert.equal(await page.locator('#private-attach .thumb').count(),1);
    await page.locator('#private-chat form').evaluate((form,bytes)=>{
      const data=new DataTransfer();data.items.add(new File([new Uint8Array(bytes)],'dropped.png',{type:'image/png'}));
      form.dispatchEvent(new DragEvent('drop',{dataTransfer:data,bubbles:true,cancelable:true}));
    },[...png]);
    assert.equal(await page.locator('#private-attach .thumb').count(),2);
    const sent=page.waitForResponse(r=>r.url().includes('/api/private?peer=GPT')&&r.request().method()==='POST');
    await page.locator('#private-chat button[type=submit]').click();
    const receipt=await sent;assert.equal(receipt.status(),201);const messageId=(await receipt.json()).post.id;
    const image=page.locator(`#private-chat [data-private-message-id="${messageId}"] .room-images button`).last();
    await image.waitFor();await image.click();
    const dialog=page.locator('dialog.private-image-dialog');await dialog.waitFor();
    assert.equal(await dialog.locator('button').first().evaluate(el=>el===document.activeElement),true);
    const src=await dialog.locator('img').getAttribute('src');assert.match(src,/\/api\/private\/image\?peer=GPT&name=/);
    const response=await page.request.get(base+src);assert.equal(response.status(),200);
    assert.equal((await page.request.get(base+src.replace('peer=GPT','peer=Claude'))).status(),404);
    // Live polling can replace the opener while the modal is open.
    await image.evaluate(el=>{el.dataset.originalOpener='true';});
    const refreshed=page.waitForResponse(r=>r.url().includes('/api/private?peer=GPT')&&r.request().method()==='GET');
    await page.evaluate(()=>document.querySelector('#private-chat .social-refresh').click());await refreshed;
    await page.waitForFunction(()=>!document.querySelector('[data-original-opener]'));
    await page.keyboard.press('Escape');assert.equal(await dialog.isVisible(),false);
    assert.equal(await image.evaluate(el=>el===document.activeElement),true);
    assert.equal(await page.locator('#private-chat').isVisible(),true);
    await peerButton(page,'Claude').click();assert.equal(await page.locator('#private-chat .room-images button').count(),0);
  }finally{await page.close();}
});

for(const theme of ['default','pink'])for(const width of [320,768,1024,1440]){
  test(`${theme} ${width}px: bubbles, input row and responsive fit`,{skip:!enabled},async()=>{
    const page=await pageAt(width,theme);
    try{
      await page.getByRole('button',{name:'私聊 GPT',exact:true}).click();
      await page.locator('#private-chat .private-message').first().waitFor();
      const result=await page.evaluate(()=>{
        const box=document.querySelector('#private-chat'),bubble=box.querySelector('.room-bubble');
        const style=getComputedStyle(bubble),form=box.querySelector('form');
        const input=box.querySelector('.room-input-wrap').getBoundingClientRect(),pick=box.querySelector('.room-pick').getBoundingClientRect(),send=box.querySelector('.room-submit').getBoundingClientRect();
        return {overflow:document.documentElement.scrollWidth>innerWidth,formOverflow:form.scrollWidth>form.clientWidth,
          radius:style.borderRadius,background:style.backgroundColor,border:style.borderTopColor,inputBottom:input.bottom,pickTop:pick.top,sendTop:send.top,
          left:form.getBoundingClientRect().left,right:form.getBoundingClientRect().right};
      });
      assert.equal(result.overflow,false);assert.equal(result.formOverflow,false);
      assert.equal(result.radius,'14px');assert.equal(result.background,'rgb(255, 255, 255)');
      assert.ok(result.pickTop>=result.inputBottom);assert.ok(result.sendTop>=result.inputBottom);
      assert.ok(result.left>=0&&result.right<=width);
      if(process.env.BOARD_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.BOARD_SCREENSHOT_DIR,`private-${theme}-${width}.png`)});
    }finally{await page.close();}
  });
}
