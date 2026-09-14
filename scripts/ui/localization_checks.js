/* Offline execution of shipped presentation functions. No browser or service is started. */
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'console.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);
// Node includes Acorn. Used only to extract real declarations, never as a runtime dependency.
const parser={exports:{},module:{}};
vm.runInNewContext(process.binding('natives')['internal/deps/acorn/acorn/dist/acorn'],parser);
const body=parser.exports.parse(script,{ecmaVersion:2022}).body[0].expression.callee.body.body;
const elements={};
class Element {
  constructor(id){this.id=id;this.value='';this.listeners={};this.isConnected=true;this.options=[];this.classList={toggle(){},remove(){}};this.files=[];}
  set innerHTML(v){this.html=v;for(const m of v.matchAll(/\bid="([^"]+)"/g))elements[m[1]]=new Element(m[1]);}
  get innerHTML(){return this.html||'';}
  addEventListener(k,f){(this.listeners[k]||=[]).push(f);}
  setAttribute(k,v){this[k]=v;}
  getAttribute(k){return this[k];}
  hasAttribute(k){return k in this;}
  querySelectorAll(){return [];}
  appendChild(){} focus(){} click(){} remove(){}
}
for(const id of ['app','masthead-state','token-link','ui-language','view-switch-human','view-switch-developer'])elements[id]=new Element(id);
let treeNodes=[];
const document={documentElement:{lang:'en'},title:'',getElementById:id=>elements[id]||null,
  querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>new Element(''),
  createTreeWalker:()=>{let i=0;return {nextNode:()=>treeNodes[i++]||null};}};
const storage=new Map();
const context={document,sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
  setTimeout:()=>0,clearTimeout(){},location:{hash:'#/submit'},window:{},Event:class{},console,
  TOKEN_KEY:'fixture_token_key',VIEW_KEY:'fixture_view',app:elements.app,mastheadState:elements['masthead-state'],
  tokenLink:elements['token-link'],viewSwitchHuman:elements['view-switch-human'],viewSwitchDeveloper:elements['view-switch-developer'],
  _ruleLinkSeq:0,pollTimer:null,forceTokenScreen:false,FormData:class{constructor(){this.rows=[];}append(k,v){this.rows.push([k,v]);}}};
vm.createContext(context);
for(const file of ['localization_catalog.js','localization.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,file),'utf8'),context);
context.ui=context.ShimmerLocale.text;context.displayValue=context.ShimmerLocale.value;
for(const n of body){
  if(n.type==='FunctionDeclaration'||(n.type==='VariableDeclaration'&&n.declarations.some(d=>['PHASES','GOVERNANCE_SENTENCES','GOVERNANCE_SENTENCES_HUMAN','HARNESS_PART_LABELS_HUMAN','MONTH_NAMES'].includes(d.id.name))))
    vm.runInContext(script.slice(n.start,n.end),context);
}
context.apiJson=async()=>({ok:true,body:{backend_profile:'local',sensitive_layer_active:false}});
context.api=()=>{throw Error('Network not permitted');};
let checks=0;
function check(name,fn){fn();checks++;}
const plain=s=>s.replace(/<pre>[\s\S]*?<\/pre>/g,'').replace(/<[^>]*>/g,'');
const forbidden=['Completed','Unavailable','Warning','Recommendation','Evidence','Review findings','Tracked changes','Output language','No results','Process finished','Source text with tracked changes','Agent activity','Multi-round positioning','Findings','Documents','Download','Log','Submit a run','Question','Privacy','Proposed correction','As it stands','Why:'];
function noEnglish(value){const p=plain(value);for(const word of forbidden)assert(!p.includes(word),word+' leaked: '+p.slice(0,160));}
async function main(){
  check('English identity and fallback',()=>{assert.equal(context.ui('Completed'),'Completed');assert.equal(context.ui('extension_token'),'extension_token');});
  context.ShimmerLocale.select('tr');
  check('Turkish status',()=>{assert.equal(context.stateToken('stopped','succeeded').label,'Tamamlandı');assert.equal(context.stateToken('queued').label,'Sırada');});
  check('Canonical enum does not change',()=>{assert.equal(context.stateToken('running').tone,'periwinkle');assert.equal(context.displayValue('concession'),'Taviz');assert.equal(context.displayValue('REF-0001'),'REF-0001');});
  check('Every phase and governance state',()=>{
    noEnglish(context.phaseLadderHtml('5'));noEnglish(context.phaseLadderHumanHtml('5','review'));
    for(const state of ['queued','running','awaiting_approval','cancelled','stopped'])for(const outcome of ['succeeded','governance_stop','crashed','timed_out']){
      const run={state,outcome,documents:[{}],stop_reason:{code:'blocked'},task:'review'};
      noEnglish(context.nextActionSentence(run));noEnglish(context.nextActionSentenceHuman(run));
    }
  });
  check('Submit chrome',()=>{context.renderSubmit();noEnglish(elements.app.innerHTML);assert(elements.app.innerHTML.includes('Çıktı dili'));assert(elements.app.innerHTML.includes('value="review"'));assert(elements.app.innerHTML.includes('id="s-files" multiple hidden'));});
  await Promise.resolve();await Promise.resolve();
  check('Validation refusal',()=>{elements['s-task'].value='';elements['s-sensitive'].value='';elements['submit-form'].listeners.submit[0]({preventDefault(){}});assert(elements['submit-result'].innerHTML.includes('Hem görev hem gizlilik'));});
  check('Parameterized API errors preserve exact values',()=>{const d=context.detailText({detail:'file "<bad>.pdf" is 123 bytes, over the SHIMMER_MAX_UPLOAD_MB (2 MB) per-file cap'});assert(d.includes('dosyası 123 bayt'));assert(d.includes('"<bad>.pdf"'));assert(!context.escapeHtml(d).includes('<bad>'));});
  check('Approval and empty state',()=>{noEnglish(context.renderApprovalBlock({pending_approval:{}}));const h=new Element('log');context.renderLogPanel({has_log:false},h);noEnglish(h.innerHTML);assert(h.innerHTML.includes('günlük yok'));});
  check('Amendment source protection and escaping',()=>{const a={original_text_is_passage:true,original_text:'Completed Evidence <script>',proposed_text:'Önerilen',comment:'Gerekçe',convention_ref:'CONV-001'};const before=JSON.stringify(a);let h=context.amendmentHumanHtml(a);assert(h.includes('Completed Evidence &lt;script&gt;'));noEnglish(h.replace('Completed Evidence &lt;script&gt;',''));assert.equal(JSON.stringify(a),before);});
  check('Case and strategic labels, canonical JSON',()=>{const d={recorded:true,fixture:true,activation:{state:'accepted'},view:{case_id:'CASE-1',evidence:[]},run_id:'RUN-1',strategic_support:{state:'recommendation',layers:[{type:'RECOMMENDATION',state:'accepted',display_label:'Recommendation',display_state:'Accepted',action:'Öneri',movement:'concession'}]}};const original=JSON.stringify(d);const h=context.multiRoundHtml(d);noEnglish(h);assert(h.includes('Öneri'));assert(h.includes('concession'));assert.equal(JSON.stringify(d),original);});
  check('Failure and activity summaries',()=>{noEnglish(context.activationSummaryHtml(null,true));noEnglish(context.activationSummaryHtml({recorded:true,completion:{state:'completed'},decisions:[],agent_states:[],activation_mode:'dense'},false));});
  check('Downloads',()=>{noEnglish(context.renderDocuments({documents:[{status:'done',doc_id:'DOC-1',deliverables_url:'/runs/RUN-1/documents/DOC-1/deliverables'}]}));noEnglish(context.renderArchiveSection({state:'stopped',outcome:'succeeded'}));});
  check('Findings, refusal and relation labels',()=>{
    noEnglish(context.findingSentenceHtml({relation:'above_band',record_verdict:'irregular',value_a:3.5,value_b:2,rule_id:'CONV-1',unit_id:'U-1'}));
    noEnglish(context.amendmentRefusalsHtml([{unit_id:'U-1',rule_id:'CONV-1',reason:'missing_field',relation:'missing_field'}],true));
  });
  check('Language switch preserves source input',()=>{
    context.ShimmerLocale.select('en');const node={nodeValue:'Output language',isConnected:true,parentElement:{tagName:'LABEL'}};treeNodes=[node];
    const form=new Element('fixture');context.ShimmerLocale.bindForm(form);const input=elements['s-question'];input.value='Source: Warning';
    context.ShimmerLocale.select('tr');assert.equal(node.nodeValue,'Çıktı dili');assert.equal(input.value,'Source: Warning');
    context.ShimmerLocale.select('en');assert.equal(node.nodeValue,'Output language');assert.equal(input.value,'Source: Warning');treeNodes=[];
  });
  check('Reopened run selects saved language',()=>{
    for(const name of ['loadActivation','loadFindings','loadPairs','loadMultiRound'])context[name]=()=>{};
    context.renderDetailBody({run_id:'RUN-1',output_language:'tr',state:'stopped',outcome:'succeeded',documents:[],has_log:false},[]);
    assert.equal(context.ShimmerLocale.language(),'tr');noEnglish(elements.app.innerHTML);
    context.renderDetailBody({run_id:'RUN-1',state:'stopped',outcome:'succeeded',documents:[],has_log:false},[]);assert.equal(context.ShimmerLocale.language(),'en');assert(elements.app.innerHTML.includes('Process finished'));
  });
  check('Neutralize detection and restore',()=>{context.ShimmerLocale.select('tr');const old=context.ui;context.ui=x=>x;assert.throws(()=>noEnglish(context.multiRoundHtml(null)));context.ui=old;noEnglish(context.multiRoundHtml(null));});
  console.log('PASS: '+checks+' offline localization UI checks');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
