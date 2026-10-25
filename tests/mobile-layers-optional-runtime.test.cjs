const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {spawnSync}=require('node:child_process');

function runFixture(moduleSource){
  const work=path.resolve(__dirname,'../work');
  fs.mkdirSync(work,{recursive:true});
  const fixture=fs.mkdtempSync(path.join(work,'browser-runtime-'));
  const preload=path.join(fixture,'preload.cjs'),runtime=path.join(fixture,'runtime.cjs');
  if(moduleSource!==null)fs.writeFileSync(runtime,moduleSource);
  fs.writeFileSync(preload,`
    const Module=require('node:module'),original=Module._resolveFilename;
    Module._resolveFilename=function(request,...args){
      if(request==='playwright'){
        ${moduleSource===null?`const error=new Error("Cannot find module 'playwright'\\nRequire stack:");error.code='MODULE_NOT_FOUND';throw error;`:`return ${JSON.stringify(runtime)};`}
      }
      return original.call(this,request,...args);
    };
  `);
  try{
    const env={...process.env};delete env.NODE_PATH;delete env.NODE_TEST_CONTEXT;
    const result=spawnSync(process.execPath,['--require',preload,'--test','--test-reporter=tap',path.join(__dirname,'mobile-layers.browser.cjs')],
      {encoding:'utf8',env,timeout:30000});
    assert.ifError(result.error);
    return {status:result.status,output:result.stdout+result.stderr};
  }finally{
    assert.equal(path.dirname(fixture),work);
    fs.rmSync(fixture,{recursive:true,force:true});
  }
}

function assertSkipped(result,reason){
  assert.equal(result.status,0,result.output);
  assert.match(result.output,/# skipped 10/);
  assert.match(result.output,/# fail 0/);
  assert.match(result.output,reason);
}

function assertFailed(result,reason){
  assert.equal(result.status,1,result.output);
  assert.match(result.output,/# skipped 0/);
  assert.match(result.output,reason);
}

test('browser cases explain a missing optional Playwright module',()=>{
  assertSkipped(runFixture(null),/install Playwright/);
});

test('browser cases explain a missing Chromium executable',()=>{
  assertSkipped(runFixture(`exports.chromium={launch:async()=>{throw new Error("browserType.launch: Executable doesn't exist at missing-chromium");}};`),/playwright install chromium/);
});

test('a missing transitive Playwright dependency fails',()=>{
  assertFailed(runFixture(`require('./missing-internal-dependency.cjs');`),/missing-internal-dependency/);
});

test('a broken installed Playwright module fails',()=>{
  assertFailed(runFixture(`throw new Error('broken Playwright initialization');`),/broken Playwright initialization/);
});

test('browser launch permission errors fail',()=>{
  assertFailed(runFixture(`exports.chromium={launch:async()=>{throw new Error('browserType.launch: spawn EACCES');}};`),/spawn EACCES/);
});

test('unrelated executable errors fail',()=>{
  assertFailed(runFixture(`exports.chromium={launch:async()=>{throw new Error("Executable doesn't exist at application-input");}};`),/application-input/);
});

test('real browser test assertions still fail',()=>{
  const result=runFixture(`exports.chromium={launch:async()=>({close:async()=>{},newPage:async()=>({
    setContent:async()=>{},addStyleTag:async()=>{},close:async()=>{},evaluate:async()=>({hit:'wrong-layer'})
  })})};`);
  assertFailed(result,/metadata must stay inside the message scroll layer/);
  assert.match(result.output,/# fail 10/);
});
