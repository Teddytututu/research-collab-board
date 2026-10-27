const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');

function harness(saved={}){
 const storage=new Map(Object.entries(saved)),ids=new Map(),requests=[];
 class Element{
  constructor(tag,cls='',text=''){
   this.tagName=tag;this.className=cls;this.textContent=text;this.children=[];this.style={};this.handlers={};this.open=false;this.hidden=false;this.isConnected=false;
   this.classList={add:n=>{if(!this.className.split(' ').includes(n))this.className+=' '+n;},toggle:()=>{}};
  }
  connect(value){this.isConnected=value;this.children.forEach(c=>c.connect(value));}
  append(...nodes){for(const n of nodes){this.children.push(n);n.connect(this.isConnected);if(n.id)ids.set(n.id,n);}}
  replaceChildren(){this.children.forEach(c=>c.connect(false));this.children=[];}
  after(n){n.connect(true);ids.set(n.id,n);}
  addEventListener(name,handler){this.handlers[name]=handler;}
  setAttribute(){}
 }
 const box=new Element('div'),filter=new Element('input');box.connect(true);filter.value='';
 ids.set('file-body',box);ids.set('file-filter',filter);
 const context={document:{getElementById:id=>ids.get(id)||null},$:selector=>ids.get(selector.slice(1)),
  el:(tag,cls,text)=>new Element(tag,cls||'',text||''),localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},
  window:{open:()=>{}},navigator:{clipboard:{writeText:()=>Promise.resolve()}},
  fetch:async(url,args)=>{requests.push(JSON.parse(args.body));return {ok:true};},setTimeout:()=>{}};
 const html=fs.readFileSync(path.join(__dirname,'../board/index.html'),'utf8'),start=html.indexOf('function renderFiles(');
 vm.runInNewContext(html.slice(start,html.indexOf('let lastRev',start))+'\nthis.render=renderFiles;',context);
 const find=(node,cls)=>node.children.flatMap(c=>[...(c.className.split(' ').includes(cls)?[c]:[]),...find(c,cls)]);
 return {context,box,filter,storage,requests,find,groups:()=>find(box,'factive-group')};
}
const links=[
 {title:'Demo report',cat:'研究',path:'demo/report.md'},
 {title:'DEMO1001 first',cat:'学习',path:'demo/first.md'},
 {title:'TASK1002 other',cat:'学习',path:'demo/other.md'},
 {title:'DEMO1001 second',cat:'学习',path:'demo/second.md'},
 {title:'General reading',cat:'学习',path:'demo/general.md'},
 {title:'General file',path:'demo/file.txt'},
 {title:'Archived study',cat:'学习',path:'demo/old.md',archived:true}
];
test('active groups reuse category order and preserve course-local link ordering',()=>{
 const h=harness();h.context.render(links);const groups=h.groups();
 assert.deepEqual(groups.map(g=>g.children[0].textContent),['研究 · 1','学习 · 4','其他 · 1']);
 assert.deepEqual(groups.map(g=>g.open),[true,false,false]);
 assert.deepEqual(h.find(groups[1],'fcourse-label').map(n=>n.textContent),['DEMO1001','TASK1002','综合']);
 assert.deepEqual(h.find(groups[1],'fname').map(n=>n.textContent),['DEMO1001 first','DEMO1001 second','TASK1002 other','General reading']);
});
test('title filter restores fa folding, keeps fg state and retains original open index',async()=>{
 const h=harness({'fa:研究':'0','fa:学习':'0','fg:学习':'1'});h.context.render(links);
 h.filter.value='DEMO1001';h.filter.oninput();
 assert.deepEqual(h.groups().filter(g=>!g.hidden).map(g=>g.children[0].textContent),['学习 · 4']);
 const study=h.groups()[1];assert.equal(study.open,true);
 assert.equal(h.find(study,'fcard').filter(n=>!n.hidden).length,2);
 await h.find(study,'fcard').filter(n=>!n.hidden)[1].onclick();assert.deepEqual(h.requests,[{i:3}]);
 h.filter.value='';h.filter.oninput();assert.equal(study.open,false);assert.equal(h.storage.get('fg:学习'),'1');
 study.open=true;study.handlers.toggle();assert.equal(h.storage.get('fa:学习'),'1');
});
