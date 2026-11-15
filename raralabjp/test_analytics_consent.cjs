const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/assets/js/analytics-consent.js','utf8');
function scenario(saved,hostname='awaifacets.com') {
 const store=new Map(saved?[['awai.analytics-consent.v1',saved]]:[]), scripts=[], handlers={}, nodes={}, writes=[];
 function el(tag){return {tag,children:[],dataset:{},hidden:false,handlers:{},appendChild(x){this.children.push(x);if(x.id)nodes[x.id]=x;if(tag==='head'&&x.tag==='script')scripts.push(x);},setAttribute(){},addEventListener(n,f){this.handlers[n]=f;},focus(){this.focused=true;},querySelectorAll(){if(!this.buttons)this.buttons=['denied','granted'].map(c=>{let b=el('button');b.dataset.choice=c;return b;});return this.buttons;},querySelector(){return this.querySelectorAll()[0];}};}
 const document={readyState:'complete',title:'Montana sapphire',referrer:'https://x.com/user?q=private#secret',head:el('head'),body:el('body'),createElement:el,querySelector(){return null;},addEventListener(n,f){handlers[n]=f;}};
 Object.defineProperty(document,'cookie',{get(){return '_ga=old; _ga_JF02RW2R0M=old; essential=keep';},set(v){writes.push(v);}});
 const location={hostname,href:'https://'+hostname+'/gallery/stone/?email=private@example.com#secret',reload(){this.reloaded=true;}};
 const c={document,location,URL,Date,JSON,localStorage:{getItem(k){return store.get(k)},setItem(k,v){store.set(k,v)}},addEventListener(n,f){handlers[n]=f;}};c.window=c;
 vm.runInNewContext(source,c);
 return {c,scripts,handlers,nodes,writes,choose(choice){nodes['awai-analytics-choice'].querySelectorAll().find(b=>b.dataset.choice===choice).handlers.click();}};
}
let s=scenario();assert.equal(s.scripts.length,0);assert.equal(s.nodes['awai-analytics-choice'].hidden,false);assert(!s.writes.some(x=>x.startsWith('essential=')));s.choose('denied');assert.equal(s.scripts.length,0);assert.equal(s.c['ga-disable-G-JF02RW2R0M'],true);
s=scenario();s.choose('granted');assert.equal(s.scripts.length,1);let events=s.c.dataLayer.map(x=>Array.from(x));assert.equal(events[0][2].ad_storage,'denied');assert.equal(events[0][2].ad_user_data,'denied');assert.equal(events[0][2].ad_personalization,'denied');assert.equal(events[2][2].page_location,'https://awaifacets.com/gallery/stone/');assert.equal(events[2][2].page_referrer,'https://x.com/');assert.equal(events[2][2].send_page_view,true);assert.equal(events.filter(e=>e[0]==='event'&&e[1]==='page_view').length,0);
s.handlers.click({target:{closest(){return {href:'https://shop.awaifacets.com/product/stone?email=private#secret'}}}});assert.equal(s.c.dataLayer.at(-1)[1],'shop_click');assert.equal(s.c.dataLayer.at(-1)[2].link_url,'https://shop.awaifacets.com/product/stone');let count=s.c.dataLayer.length;s.handlers.click({target:{closest(){return {href:'mailto:private@example.com'}}}});assert.equal(s.c.dataLayer.length,count);
s.nodes['awai-analytics-settings'].handlers.click();assert.equal(s.nodes['awai-analytics-choice'].hidden,false);s.choose('denied');assert.equal(s.c.location.reloaded,true);assert.equal(s.c['ga-disable-G-JF02RW2R0M'],true);s.handlers.click({target:{closest(){return {href:'https://shop.awaifacets.com/product/stone'}}}});assert.equal(s.c.dataLayer.length,count);
for(const input of ['invalid',JSON.stringify({choice:'granted',at:0}),JSON.stringify({choice:'other',at:Date.now()})]){s=scenario(input);assert.equal(s.scripts.length,0);assert.equal(s.nodes['awai-analytics-choice'].hidden,false);}
s=scenario(JSON.stringify({choice:'denied',at:Date.now()}));assert.equal(s.scripts.length,0);assert.equal(s.nodes['awai-analytics-choice'].hidden,true);
s=scenario(JSON.stringify({choice:'granted',at:Date.now()}));assert.equal(s.scripts.length,1);
s=scenario(null,'localhost');s.choose('granted');assert.equal(s.scripts.length,0);
console.log('PASS: no load before consent/reject, grant once, revoke reload+disable, sanitized URLs, shop-only clicks, expiry/malformed state, localhost excluded.');
