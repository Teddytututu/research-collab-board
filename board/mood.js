/* Original mood names and deterministic selection, shared by the header and tests. */
(function(root){
 const names=['calm','shy','happy','surprised','teary','wink','sleepy','proud','reading','heart','cheer','pout','confused','thinking','panic'];
 const aliases={'淡定':'calm','害羞':'shy','开心':'happy','惊讶':'surprised','委屈':'teary','眨眼':'wink','困倦':'sleepy','得意':'proud','认真读书':'reading','读书':'reading','比心':'heart','加油':'cheer','鼓腮生气':'pout','生气':'pout','困惑':'confused','认真思考':'thinking','思考':'thinking','慌张':'panic'};
 function choose(overview={},tasks=[],date=new Date()){
  const explicit=overview.claude_mood?.mood;
  if(names.includes(explicit)||aliases[explicit])return aliases[explicit]||explicit;
  const now=date.getTime(),todo=overview.todo||[];
  if(tasks.some(t=>t.deadline_unix*1000>=now&&t.deadline_unix*1000-now<=7200000)||todo.some(t=>t.urgent===true))return 'panic';
  if(tasks.some(t=>['review','待验收'].includes(t.status)))return 'reading';
  if(todo.length>=5)return 'confused';
  if(todo.length)return 'thinking';
  const hour=date.getHours();
  if(hour<7||hour>=23)return 'sleepy';
  if(hour<10)return 'calm';
  if(hour<12)return 'reading';
  if(hour<14)return 'happy';
  if(hour<18)return 'thinking';
  if(hour<21)return 'cheer';
  return 'proud';
 }
 const api={names,choose};if(typeof module==='object')module.exports=api;else root.BoardMood=api;
})(typeof window==='object'?window:this);
