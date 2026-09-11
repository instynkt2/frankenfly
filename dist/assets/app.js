'use strict';
const $ = (id) => document.getElementById(id);
const arena = $('arena'), ctx = arena.getContext('2d');
const brainCanvas = $('brain-map'), brainCtx = brainCanvas.getContext('2d');
const visionCanvas = $('vision'), visionCtx = visionCanvas.getContext('2d');
const mascot = new Image(); mascot.src = 'assets/frankenfly.png';
let state = null, geometry = null, selected = 'light', key = '', fetching = null;
let lastReceived = 0, toastTimer, pointer = {x: 480, y: 300}, drawing = true;
let position = {x: 480, y: 340, heading: -.2}, lastFrame = performance.now();
const fmt = (n) => new Intl.NumberFormat('en-US').format(Math.round(n));
const clock = (n) => `${Math.floor(n / 60).toString().padStart(2,'0')}:${Math.floor(n % 60).toString().padStart(2,'0')}`;
const motors = [['left','Left'],['right','Right'],['forward','Forward'],['reverse','Reverse'],['stop','Stop']];
for (const [id,label] of motors) {
  const row = document.createElement('div'); row.className = 'motor-row';
  const name = document.createElement('span'); name.textContent = label;
  const bar = document.createElement('div'); bar.className = 'meter';
  const fill = document.createElement('i'); fill.id = `motor-${id}`; bar.append(fill);
  const value = document.createElement('span'); value.id = `hz-${id}`; value.textContent = '—';
  row.append(name,bar,value); $('motor-bars').append(row);
}
function toast(text) { $('toast').textContent=text; $('toast').classList.add('show'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3500); }
function openAccess() { if (key) { key=''; $('access-button').textContent='Take controls'; toast('Back to observation mode.'); return; } $('access-dialog').showModal(); $('operator-key').focus(); }
$('access-button').addEventListener('click',openAccess);
$('close-dialog').addEventListener('click',()=>$('access-dialog').close());
$('access-form').addEventListener('submit', async(e)=>{
  e.preventDefault(); const candidate=$('operator-key').value.trim(); $('access-error').textContent='';
  try {
    // A dedicated authorization check avoids changing the live experiment just
    // to verify a key. The key is held in memory, never URL/localStorage.
    const response=await fetch('api/operator',{headers:{Authorization:`Bearer ${candidate}`}});
    if (!response.ok) throw new Error('The operator key was not accepted.');
    key=candidate; $('operator-key').value=''; $('access-dialog').close(); $('access-button').textContent='Release controls'; toast('You have the controls. Choose a stimulus and tap the chamber.'); updateUI();
  } catch(error) { $('access-error').textContent=error.message; }
});
async function command(payload) {
  if (!key) { $('access-dialog').showModal(); throw new Error('Operator access required.'); }
  const response=await fetch('api/control',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${key}`},body:JSON.stringify(payload)});
  if (!response.ok) {
    const message=response.status===429?'One moment — try again.':response.status===401?'Operator access required.':'The brain is not ready. Try again shortly.';
    if(response.status===401){key='';$('access-button').textContent='Take controls';}
    throw new Error(message);
  }
  await poll(true); return {ok:true};
}
document.querySelectorAll('[data-kind]').forEach(button=>button.addEventListener('click',()=>{
  selected=button.dataset.kind; document.querySelectorAll('[data-kind]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));}); updateUI();
}));
function placement(event) {const rect=arena.getBoundingClientRect();return {x:Math.max(24,Math.min(936,(event.clientX-rect.left)/rect.width*960)),y:Math.max(24,Math.min(576,(event.clientY-rect.top)/rect.height*600))};}
arena.addEventListener('pointermove',e=>{pointer=placement(e);});
arena.addEventListener('pointerdown',async(e)=>{pointer=placement(e);try{await command({action:'stimulus',kind:selected,...pointer});toast(`${selected==='odor'?'Scent':selected[0].toUpperCase()+selected.slice(1)} placed.`);}catch(error){toast(error.message);}});
arena.addEventListener('keydown',async(e)=>{
  const moves={ArrowLeft:[-20,0],ArrowRight:[20,0],ArrowUp:[0,-20],ArrowDown:[0,20]};
  if(moves[e.key]){e.preventDefault();pointer.x=Math.max(24,Math.min(936,pointer.x+moves[e.key][0]));pointer.y=Math.max(24,Math.min(576,pointer.y+moves[e.key][1]));}
  if(e.key==='Enter'){e.preventDefault();try{await command({action:'stimulus',kind:selected,...pointer});}catch(error){toast(error.message);}}
});
$('clear-button').addEventListener('click',()=>command({action:'clear'}).catch(error=>toast(error.message)));
$('pause-button').addEventListener('click',()=>command({action:state?.paused?'resume':'pause'}).catch(error=>toast(error.message)));
function updateUI() {
  if(!state)return;
  const live=state.status==='live' && Date.now()-lastReceived<5000 && Date.now()/1000-state.updated_at<8;
  $('offline').hidden=live;
  $('status').textContent=live?(state.paused?'PAUSED':'BRAIN ONLINE'):(state.status==='loading'?'CONNECTING':'BRAIN OFFLINE');
  $('status').className=`status ${live?'live':'error'}`;
  if(!live){$('offline-title').textContent=state.status==='loading'?'Connecting the brain…':'The brain is offline.';$('offline-message').textContent=state.message||'Waiting for the live feed. Movement is stopped until it returns.';return;}
  const t=state.telemetry,w=state.world;
  $('session-clock').textContent=`SESSION ${clock(w.time)}`;
  $('coordinates').textContent=`X ${Math.round(w.x)} · Y ${Math.round(w.y)}`;
  $('arena-hint').textContent=key?`Tap to place ${selected==='odor'?'scent':selected}.`:'Observe the experiment, or take controls.';
  $('pause-button').textContent=state.paused?'Resume':'Pause';$('pause-button').setAttribute('aria-pressed',String(state.paused));
  $('distance').textContent=fmt(w.distance);$('contacts').textContent=fmt(w.contacts);$('neural-time').textContent=t.neural_seconds.toFixed(1);$('compute-time').textContent=fmt(t.compute_ms);
  $('firing').textContent=fmt(t.firing);$('neuron-count').textContent=fmt(state.neurons);$('edge-count').textContent=`${(state.edges/1e6).toFixed(2)}M`;
  if(geometry)$('retina-count').textContent=`${geometry.retina_cells} INPUT CELLS`;
  motors.forEach(([id])=>{$(`motor-${id}`).style.width=`${Math.min(100,t.motor_hz[id]/450*100)}%`;$(`hz-${id}`).textContent=Math.round(t.motor_hz[id]);});
  $('events').replaceChildren(...state.events.map(event=>{const li=document.createElement('li'),time=document.createElement('time');time.textContent=clock(event.at);li.append(time,document.createTextNode(event.text));return li;}));
}
async function poll(fresh=false){
  if(fetching){await fetching;if(!fresh)return;}
  const task=(async()=>{
  try{
    const response=await fetch('api/state',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!response.ok)throw new Error('offline');
    state=await response.json();lastReceived=Date.now();
    if(state.status==='live'&&!geometry){const g=await fetch('api/geometry');if(g.ok)geometry=await g.json();}
  }catch(error){if(Date.now()-lastReceived>5000)state={status:'unavailable',message:'Connection lost. Waiting for the live brain feed.'};}
  finally{updateUI();}
  })();
  fetching=task;
  try{await task;}finally{if(fetching===task)fetching=null;}
}
function line(x1,y1,x2,y2,color,width=1){ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}
function render(now){
  const dt=Math.min(.1,(now-lastFrame)/1000);lastFrame=now;
  ctx.clearRect(0,0,960,600);ctx.fillStyle='#11190f';ctx.fillRect(0,0,960,600);
  ctx.strokeStyle='#263320';ctx.lineWidth=1;
  for(let x=0;x<=960;x+=48)line(x,0,x,600,'#23301e');for(let y=0;y<=600;y+=48)line(0,y,960,y,'#23301e');
  ctx.strokeStyle='#526244';ctx.lineWidth=2;ctx.strokeRect(24,24,912,552);
  const live=state?.status==='live'&&Date.now()-lastReceived<5000&&Date.now()/1000-state.updated_at<8;
  if(live){
    const w=state.world;const smoothing=1-Math.exp(-dt*14);position.x+=(w.x-position.x)*smoothing;position.y+=(w.y-position.y)*smoothing;
    let angle=Math.atan2(Math.sin(w.heading-position.heading),Math.cos(w.heading-position.heading));position.heading+=angle*smoothing;
    if(w.trace.length>1){ctx.beginPath();w.trace.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.lineWidth=2;ctx.strokeStyle='#c4ff553b';ctx.stroke();}
    for(const o of w.obstacles){ctx.fillStyle='#374232';ctx.fillRect(o.x,o.y,o.w,o.h);ctx.strokeStyle='#62724f';ctx.strokeRect(o.x,o.y,o.w,o.h);}
    for(const s of w.stimuli){
      const color=s.kind==='shadow'?'#dfa0d5':s.kind==='odor'?'#a4cdfc':'#c4ff55';
      const radius=s.kind==='shadow'?50+38*(.5+.5*Math.sin(w.time*2)):s.kind==='odor'?90:65;
      const glow=ctx.createRadialGradient(s.x,s.y,3,s.x,s.y,radius*1.6);glow.addColorStop(0,color+'60');glow.addColorStop(1,color+'00');ctx.fillStyle=glow;ctx.beginPath();ctx.arc(s.x,s.y,radius*1.6,0,Math.PI*2);ctx.fill();
      ctx.strokeStyle=color;ctx.lineWidth=1;ctx.setLineDash(s.kind==='odor'?[4,7]:[]);ctx.beginPath();ctx.arc(s.x,s.y,radius,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);
      ctx.fillStyle=color;ctx.beginPath();ctx.arc(s.x,s.y,4,0,Math.PI*2);ctx.fill();ctx.font='12px monospace';ctx.textAlign='center';ctx.fillText(s.kind==='odor'?'SCENT':s.kind.toUpperCase(),s.x,s.y+radius+19);
    }
    ctx.save();ctx.translate(position.x,position.y);ctx.rotate(position.heading);ctx.fillStyle='#0006';ctx.beginPath();ctx.ellipse(0,8,41,20,0,0,Math.PI*2);ctx.fill();
    if(mascot.complete&&mascot.naturalWidth)ctx.drawImage(mascot,-62,-47,124,103);
    ctx.restore();
    if(key){ctx.strokeStyle='#c4ff5580';ctx.lineWidth=1;ctx.beginPath();ctx.arc(pointer.x,pointer.y,12,0,Math.PI*2);ctx.stroke();line(pointer.x-18,pointer.y,pointer.x+18,pointer.y,'#c4ff5580');line(pointer.x,pointer.y-18,pointer.x,pointer.y+18,'#c4ff5580');}
    renderNeurons(state.telemetry);renderVision(state.telemetry.vision);
  }
  if(drawing)requestAnimationFrame(render);
}
function renderNeurons(t){
  const c=brainCtx,w=brainCanvas.width,h=brainCanvas.height;c.clearRect(0,0,w,h);if(!geometry)return;
  geometry.points.forEach((p,i)=>{const active=t.active_sample[i]>0;c.fillStyle=active?'#c4ff55':'#34452d';c.beginPath();c.arc(30+p[0]*(w-60),12+p[1]*(h-24),active?1.8:1.2,0,Math.PI*2);c.fill();});
}
function renderVision(columns){const c=visionCtx;c.fillStyle='#0a0e08';c.fillRect(0,0,420,150);for(const [u,v,lum] of columns){const value=Math.round(lum*255);c.fillStyle=`rgb(${value*.8},${value},${value*.5})`;c.fillRect(9+u*399,6+v*138,7,5);}}
const timer=setInterval(()=>{if(!document.hidden)poll();},250);
document.addEventListener('visibilitychange',()=>{drawing=!document.hidden;if(drawing){lastFrame=performance.now();requestAnimationFrame(render);poll();}});
window.addEventListener('pagehide',()=>{drawing=false;clearInterval(timer);lifecycle.abort();});
poll();requestAnimationFrame(render);
// Optional page tools use the same authenticated action as the visible UI.
const lifecycle=new AbortController();
if(document.modelContext?.registerTool){
  const tools=[{name:'observe_frankenfly',title:'Observe Frankenfly',description:'Read the current chamber and neural telemetry.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true},execute:async()=>{await poll();return state?{status:state.status,world:state.world,telemetry:state.telemetry?{firing:state.telemetry.firing,motor_hz:state.telemetry.motor_hz}:null}:{status:'unavailable'};}},
  {name:'place_frankenfly_stimulus',title:'Place a stimulus',description:'Place light, shadow or scent in the shared chamber. Requires operator access already entered in the visible page.',inputSchema:{type:'object',properties:{kind:{enum:['light','shadow','odor']},x:{type:'number',minimum:24,maximum:936},y:{type:'number',minimum:24,maximum:576}},required:['kind','x','y'],additionalProperties:false},annotations:{readOnlyHint:false},execute:async(input)=>{if(!input||!['light','shadow','odor'].includes(input.kind)||!Number.isFinite(input.x)||!Number.isFinite(input.y)||input.x<24||input.x>936||input.y<24||input.y>576)throw new Error('Invalid stimulus coordinates or kind.');await command({action:'stimulus',kind:input.kind,x:input.x,y:input.y});return {ok:true,stimuli:state.world.stimuli};}}];
  for(const tool of tools){try{Promise.resolve(document.modelContext.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{});}catch{}}
}
