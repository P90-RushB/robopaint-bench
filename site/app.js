'use strict';
let collection;
let recommendation;
const authorRanks = new Map();
const modelVideos = new Map();
let selectedAttempt = 3;
const byId = id => document.getElementById(id);
const el = (tag, className, value) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
};
function safeAsset(path) {
  if (typeof path !== 'string' || !/^assets\/media\/[a-z0-9_./-]+$/i.test(path) || path.includes('..')) return '';
  return path;
}
function publicURL(value) {
  if (!value) return null;
  try { const u = new URL(value); return u.protocol === 'https:' ? u.href : null; } catch { return null; }
}
function backendLabel(model) {
  return model.backend_label || ({codex:'Codex SDK',openrouter:'OpenRouter',volcengine:'Volcengine Ark'}[model.backend]) || model.backend;
}
const roundLabel = number => `ICL Round ${number}`;
function roundExperience(number) {
  if(number===1)return 'Starts the session.';
  return number===2 ? 'Carries experience from Round 1.' : 'Carries experience from Rounds 1–2.';
}
function orderedModels(models, order) {
  return [...models].sort((a,b) => {
    const rankDifference = order === 'author' ? (authorRanks.get(a.id) ?? Infinity) - (authorRanks.get(b.id) ?? Infinity) : 0;
    return rankDifference || a.label.localeCompare(b.label);
  });
}
function imageFor(model, attempt, large = false) {
  const img = el('img');
  img.src = safeAsset(attempt.canvas.path);
  img.alt = `${model.label}, Golden Gate Bridge painting, ${roundLabel(attempt.attempt)} of one continuous session`;
  img.loading = large ? 'eager' : 'lazy';
  img.width = attempt.canvas.width || 1024;
  img.height = attempt.canvas.height || 725;
  img.addEventListener('error', () => {
    const missing = el('div', 'media-missing');
    missing.append(el('p', '', `${model.label} · ${roundLabel(attempt.attempt)}. Follow the media assembly guide to enable images.`));
    img.replaceWith(missing);
  }, { once: true });
  return img;
}
function renderGallery() {
  const q = byId('model-search').value.trim().toLowerCase();
  const order = byId('sort-order').value;
  const models = orderedModels(collection.models.filter(m => `${m.label} ${m.model_id} ${m.backend} ${backendLabel(m)}`.toLowerCase().includes(q)), order);
  const gallery = byId('gallery'); gallery.replaceChildren();
  for (const m of models) {
    const a = m.attempts.find(item => item.attempt === selectedAttempt);
    const figure = el('figure', 'painting-card');
    const button = el('button', 'painting-open');
    button.setAttribute('aria-label', `Inspect ${m.label}, all three ICL rounds of one continuous session`);
    button.append(imageFor(m,a),el('span','inspect-tag','INSPECT ALL 3 ROUNDS ↗'));
    button.addEventListener('click', () => openModel(m));
    const caption = el('figcaption'); const label = el('div');
    const heading = el('h3');
    if(order==='author' && authorRanks.has(m.id))heading.append(el('span','rank-number',`#${authorRanks.get(m.id)}`),' ');
    heading.append(m.label);
    label.append(heading,el('p','',`${backendLabel(m)} · ${m.effort_label || m.effort}`));
    caption.append(label,el('span','steps',`${a.steps} actions`));
    figure.append(button,caption);gallery.append(figure);
  }
  if (!models.length) gallery.append(el('p','empty','No models match this search.'));
  byId('gallery-status').textContent = `${models.length} of ${collection.models.length} models · ${roundLabel(selectedAttempt)} · ${order==='author'?"author's personal ranking":'alphabetical order'}`;
}
function validatedModelVideos(data, models) {
  if(data?.schema!=='robopaint.model-videos.v1'||data.case_id!=='golden_gate'||data.playback_speed!==6||!Array.isArray(data.captions)||!data.captions.includes('zh')||!data.captions.includes('en'))throw new Error('Invalid model video metadata');
  const entries=data.models;
  if(!entries||typeof entries!=='object'||Array.isArray(entries)||Object.keys(entries).length!==models.length)throw new Error('Incomplete model video collection');
  const videos=new Map();
  for(const model of models){
    const video=entries[model.id];
    if(!video||typeof video.bvid!=='string'||!/^BV[0-9A-Za-z]{10}$/.test(video.bvid))throw new Error('Invalid Bilibili video ID');
    const canonical=`https://www.bilibili.com/video/${video.bvid}`;
    if(video.url!==canonical&&video.url!==`${canonical}/`)throw new Error('Invalid Bilibili video URL');
    if(!Number.isFinite(video.duration_seconds)||video.duration_seconds<=0)throw new Error('Invalid video duration');
    videos.set(model.id,{...video,url:canonical});
  }
  return videos;
}
function videoDuration(seconds) {
  const total=Math.round(seconds);
  const minutes=Math.floor(total/60);
  return `${minutes}:${String(total%60).padStart(2,'0')}`;
}
function selectModelVideo(modelId) {
  const model=collection.models.find(m=>m.id===modelId);
  const video=modelVideos.get(modelId);
  if(!model||!video)return;
  document.querySelectorAll('[data-video-model]').forEach(button=>{
    const selected=button.dataset.videoModel===modelId;
    button.setAttribute('aria-pressed',String(selected));
    button.classList.toggle('active',selected);
  });
  const player=byId('model-video-player');
  const source=`https://player.bilibili.com/player.html?bvid=${video.bvid}&page=1&autoplay=0`;
  player.title=`${model.label} robot painting recording on Bilibili, 6× playback`;
  if(player.getAttribute('src')!==source)player.src=source;
  player.hidden=false;
  byId('model-video-poster').hidden=true;
  byId('model-video-status').textContent=`${model.label} · ${videoDuration(video.duration_seconds)} video · 6× playback`;
  const external=byId('model-video-external');
  external.href=video.url;
  external.setAttribute('aria-label',`Open ${model.label}'s recording on Bilibili in a new tab`);
  external.hidden=false;
}
async function initModelVideos() {
  try{
    const inline=byId('model-video-data');
    let data;
    if(inline)data=JSON.parse(inline.textContent);
    else{const response=await fetch('data/model-videos.json');if(!response.ok)throw new Error(`HTTP ${response.status}`);data=await response.json();}
    for(const [id,video] of validatedModelVideos(data,collection.models))modelVideos.set(id,video);
    const controls=byId('model-video-controls');
    for(const model of orderedModels(collection.models,'author')){
      const button=el('button','model-video-choice',model.label);
      button.type='button';
      button.dataset.videoModel=model.id;
      button.setAttribute('aria-pressed','false');
      button.setAttribute('aria-controls','model-video-player');
      button.addEventListener('click',()=>selectModelVideo(model.id));
      controls.append(button);
    }
    selectModelVideo(modelVideos.has('astra')?'astra':orderedModels(collection.models,'author')[0].id);
  }catch{
    byId('model-video-status').textContent='The model recordings could not be loaded. Refresh this page to try again.';
  }
}
function openModel(m) {
  const content = byId('dialog-content');content.replaceChildren();
  content.append(el('h2','dialog-title',m.label),el('p','dialog-intro',`${m.model_id} · ${backendLabel(m)} · ${m.effort_label || m.effort}`));
  content.append(el('p','dialog-icl','In-context learning across one continuous session: each round starts on fresh paper while prior experience carries forward. Model weights stay fixed.'));
  const frames=el('div','dialog-attempts');
  for(const a of m.attempts){
    const f=el('figure');const link=el('a','image-link');
    link.href=safeAsset(a.canvas.path);link.target='_blank';link.rel='noopener';link.append(imageFor(m,a,true));
    const caption=el('figcaption');caption.append(el('strong','',`${roundLabel(a.attempt)} · ${a.steps} actions`),el('span','round-history',roundExperience(a.attempt)));
    f.append(link,caption);frames.append(f);
  }
  content.append(frames);
  const notes=el('div','dialog-notes');notes.append(el('h3','','Run evidence & conditions'));
  const caveats=Array.isArray(m.caveats)?m.caveats:[];
  if(caveats.length) for(const note of caveats) notes.append(el('p','',typeof note==='string'?note:JSON.stringify(note)));
  else notes.append(el('p','','Three completed sequential ICL rounds within one agent session. Prior experience carries forward; paper resets.'));
  if(m.replay_verification) notes.append(el('p','',`Replay verification: ${typeof m.replay_verification==='string'?m.replay_verification:JSON.stringify(m.replay_verification)}`));
  const recordURL=publicURL(m.record?.url);
  if(recordURL){const a=el('a','text-link','Published replay record ↗');a.href=recordURL;a.target='_blank';a.rel='noopener';notes.append(a);}
  else notes.append(el('p','muted','Replay evidence is retained by the maintainers; a public record download is not yet linked for this model.'));
  const hash=el('p','small');hash.append('ICL Round 3 canvas SHA-256: ',el('code','',m.attempts.find(a=>a.attempt===3).canvas.sha256));notes.append(hash);
  const recording=modelVideos.get(m.id);
  if(recording){const link=el('a','video-card','Watch this model’s recording on Bilibili ↗');link.href=recording.url;link.target='_blank';link.rel='noopener';notes.append(link);}
  for(const a of m.attempts){const url=publicURL(a.video_url);if(url){const link=el('a','video-card',`Watch ${roundLabel(a.attempt)} ↗`);link.href=url;link.target='_blank';link.rel='noopener';notes.append(link);}}
  content.append(notes);byId('painting-dialog').showModal();
}
function renderComparison(){const holder=byId('comparison');holder.replaceChildren();const attempt=Number(byId('compare-attempt').value);for(const id of ['compare-left','compare-right']){const m=collection.models.find(m=>m.id===byId(id).value);if(!m)continue;const a=m.attempts.find(a=>a.attempt===attempt);const f=el('figure');const caption=el('figcaption');caption.append(el('strong','',m.label),el('span','',`${roundLabel(attempt)} · ${a.steps} actions`));f.append(imageFor(m,a,true),caption);holder.append(f);}}
function renderSettings(){
  const body=byId('settings-table');
  for(const m of orderedModels(collection.models,recommendation?.status==='provided'?'author':'alphabetical')){
    const row=el('tr');const name=el('td');
    name.append(el('strong','',m.label),el('br'),el('small','',backendLabel(m)));
    const caveats=Array.isArray(m.caveats)?m.caveats:[];
    row.append(el('td','',authorRanks.has(m.id)?`#${authorRanks.get(m.id)}`:'—'),name,el('td','',m.effort_label||m.effort),el('td','',m.attempt_steps.join(' / ')),el('td','',caveats.join(' ')||'Three sequential ICL rounds; one agent session.'));
    body.append(row);
  }
}
async function init(){
  try {
    const inlineResults=byId('benchmark-data');
    if(inlineResults)collection=JSON.parse(inlineResults.textContent);
    else{const response=await fetch('data/golden_gate.json');if(!response.ok)throw new Error(`HTTP ${response.status}`);collection=await response.json();}
    if(!Array.isArray(collection.models)||!collection.models.length)throw new Error('Empty collection');
    collection.models.sort((a,b)=>a.label.localeCompare(b.label));
    const inlineRecommendation=byId('recommendation-data');
    if(inlineRecommendation)recommendation=JSON.parse(inlineRecommendation.textContent);
    else{const rankingResponse=await fetch('data/editorial-ranking.json');if(!rankingResponse.ok)throw new Error('Missing recommendation metadata');recommendation=await rankingResponse.json();}
    if(recommendation.status==='provided'){
      const ids=recommendation.tiers.flatMap(t=>t.model_ids);if(new Set(ids).size!==collection.models.length||ids.length!==collection.models.length||collection.models.some(m=>!ids.includes(m.id)))throw new Error('Invalid recommendation coverage');
      let rank=1;for(const tier of recommendation.tiers){for(const id of tier.model_ids)authorRanks.set(id,rank);rank+=tier.model_ids.length;}
      const choice=byId('sort-order').querySelector('[value="author"]');choice.disabled=false;choice.textContent="Author's personal ranking";byId('sort-order').value='author';
      const note=byId('ranking-note');note.replaceChildren(el('strong','',"The benchmark author's personal ranking. "));note.append(`Provided ${recommendation.date}. This qualitative ordering reflects the author's judgment; all three ICL rounds remain available for your own comparison. `);const link=el('a','','How results are presented ↗');link.href='docs/scoring.html';note.append(link);
    }else{
      byId('sort-order').value='alphabetical';
      byId('sort-order').querySelector('[value="author"]').disabled=true;
    }
    byId('sort-order').addEventListener('change',renderGallery);
    byId('model-count').textContent=collection.models.length;
    byId('canvas-count').textContent=collection.models.reduce((n,m)=>n+m.attempts.length,0);
    for(const id of ['compare-left','compare-right']){for(const m of orderedModels(collection.models,recommendation?.status==='provided'?'author':'alphabetical')){const option=el('option','',m.label);option.value=m.id;byId(id).append(option);}}
    byId('compare-left').value=collection.models.some(m=>m.id==='astra')?'astra':collection.models[0].id;
    byId('compare-right').value=collection.models.some(m=>m.id==='sol')?'sol':collection.models[1]?.id||collection.models[0].id;
    for(const id of ['compare-left','compare-right','compare-attempt'])byId(id).addEventListener('change',renderComparison);
    document.querySelectorAll('[data-attempt]').forEach(button=>button.addEventListener('click',()=>{selectedAttempt=Number(button.dataset.attempt);document.querySelectorAll('[data-attempt]').forEach(b=>{const on=Number(b.dataset.attempt)===selectedAttempt;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});renderGallery();}));
    byId('model-search').addEventListener('input',renderGallery);renderGallery();renderComparison();renderSettings();
    void initModelVideos();
  }catch(error){byId('gallery-status').textContent='Result metadata could not be loaded.';const notice=el('p','error','Serve the assembled site over HTTP after running scripts/build_site.py. See docs/hosting.md for the local preview commands.');byId('gallery').append(notice);}
}
byId('painting-dialog').querySelector('.dialog-close').addEventListener('click',()=>byId('painting-dialog').close());
byId('painting-dialog').addEventListener('click',event=>{if(event.target===byId('painting-dialog')){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
byId('copy-command').addEventListener('click',async()=>{const button=byId('copy-command');try{await navigator.clipboard.writeText('python scripts/prepare_run.py --case golden_gate --model sol');button.textContent='Copied';}catch{button.textContent='Select code';}setTimeout(()=>button.textContent='Copy',1800);});
document.querySelectorAll('.hero img,.robot-figure img').forEach(img=>img.addEventListener('error',()=>{const note=el('div','media-missing');note.append(el('p','','Local preview assets are assembled separately from the source repository.'));img.replaceWith(note);},{once:true}));
init();
