'use strict';
let collection;
let recommendation;
let activeCase;
let caseCatalog;
let switchVersion = 0;
let playbackSpeed = 6;
const authorRanks = new Map();
const modelVideos = new Map();
let selectedAttempt = 3;
const inlineIds = {
  golden_gate: {results:'benchmark-data', recommendation:'recommendation-data', videos:'model-video-data'},
  pelican: {results:'pelican-benchmark-data', recommendation:'pelican-recommendation-data', videos:'pelican-model-video-data'}
};
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
  img.alt = `${model.label}, ${activeCase.label} painting, ${roundLabel(attempt.attempt)} of one continuous session`;
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
  const expectedSpeed=activeCase.id==='pelican'?4:6;
  if(data?.schema!=='robopaint.model-videos.v1'||data.case_id!==activeCase.id||data.playback_speed!==expectedSpeed||!Array.isArray(data.captions)||!data.captions.includes('zh')||!data.captions.includes('en'))throw new Error('Invalid model video metadata');
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
  player.title=`${model.label} ${activeCase.label} robot painting recording on Bilibili, ${playbackSpeed}× playback`;
  if(player.getAttribute('src')!==source)player.src=source;
  player.hidden=false;
  byId('model-video-poster').hidden=true;
  byId('model-video-status').textContent=`${model.label} · ${videoDuration(video.duration_seconds)} video · ${playbackSpeed}× playback`;
  const external=byId('model-video-external');
  external.href=video.url;
  external.setAttribute('aria-label',`Open ${model.label}'s recording on Bilibili in a new tab`);
  external.hidden=false;
}
function initModelVideos(data) {
  const controls=byId('model-video-controls');
  controls.replaceChildren();
  modelVideos.clear();
  const player=byId('model-video-player');
  player.removeAttribute('src');
  player.hidden=true;
  byId('model-video-poster').hidden=false;
  byId('model-video-external').hidden=true;
  try{
    for(const [id,video] of validatedModelVideos(data,collection.models))modelVideos.set(id,video);
    for(const model of orderedModels(collection.models,recommendation?.status==='provided'?'author':'alphabetical')){
      const button=el('button','model-video-choice',model.label);
      button.type='button';
      button.dataset.videoModel=model.id;
      button.setAttribute('aria-pressed','false');
      button.setAttribute('aria-controls','model-video-player');
      button.addEventListener('click',()=>selectModelVideo(model.id));
      controls.append(button);
    }
    selectModelVideo(modelVideos.has('astra')?'astra':collection.models[0].id);
  }catch{
    byId('model-video-poster').hidden=activeCase.id==='pelican';
    byId('model-video-status').textContent='The recordings for this task could not be loaded. See the replay guide to inspect its public records.';
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
  const trajectoryURL=publicURL(m.trajectory?.url);
  if(trajectoryURL){const a=el('a','text-link trajectory-link','Published trajectory (recorded window) ↗');a.href=trajectoryURL;a.target='_blank';a.rel='noopener';notes.append(a);if(m.trajectory.full_history===false)notes.append(el('p','small muted','This trajectory covers the recorded window described in the run notes; it is not a complete interaction history.'));}
  const hash=el('p','small');hash.append('ICL Round 3 canvas SHA-256: ',el('code','',m.attempts.find(a=>a.attempt===3).canvas.sha256));notes.append(hash);
  const recording=modelVideos.get(m.id);
  const sessionURL=recording?.url||publicURL(m.video_url);
  const seenVideos=new Set();
  if(sessionURL){const link=el('a','video-card','Watch all three rounds on Bilibili ↗');link.href=sessionURL;link.target='_blank';link.rel='noopener';notes.append(link);seenVideos.add(sessionURL.replace(/\/$/,''));}
  for(const a of m.attempts){const url=publicURL(a.video_url);if(url&&!seenVideos.has(url.replace(/\/$/,''))){const link=el('a','video-card',`Watch ${roundLabel(a.attempt)} ↗`);link.href=url;link.target='_blank';link.rel='noopener';notes.append(link);seenVideos.add(url.replace(/\/$/,''));}}
  content.append(notes);byId('painting-dialog').showModal();
}
function renderComparison(){const holder=byId('comparison');holder.replaceChildren();const attempt=Number(byId('compare-attempt').value);for(const id of ['compare-left','compare-right']){const m=collection.models.find(m=>m.id===byId(id).value);if(!m)continue;const a=m.attempts.find(a=>a.attempt===attempt);const f=el('figure');const caption=el('figcaption');caption.append(el('strong','',m.label),el('span','',`${roundLabel(attempt)} · ${a.steps} actions`));f.append(imageFor(m,a,true),caption);holder.append(f);}}
function renderSettings(){
  const body=byId('settings-table');
  body.replaceChildren();
  for(const m of orderedModels(collection.models,recommendation?.status==='provided'?'author':'alphabetical')){
    const row=el('tr');const name=el('td');
    name.append(el('strong','',m.label),el('br'),el('small','',backendLabel(m)));
    const caveats=Array.isArray(m.caveats)?m.caveats:[];
    row.append(el('td','',authorRanks.has(m.id)?`#${authorRanks.get(m.id)}`:'—'),name,el('td','',m.effort_label||m.effort),el('td','',m.attempt_steps.join(' / ')),el('td','',caveats.join(' ')||'Three sequential ICL rounds; one agent session.'));
    body.append(row);
  }
}
async function readData(inlineId,filename){
  const inline=byId(inlineId);
  if(inline)return JSON.parse(inline.textContent);
  if(typeof filename!=='string'||!/^[a-z0-9_-]+\.json$/i.test(filename))throw new Error('Invalid metadata filename');
  const response=await fetch(`data/${filename}`);
  if(!response.ok)throw new Error(`HTTP ${response.status}`);
  return response.json();
}
function renderRanking(){
  authorRanks.clear();
  const choice=byId('sort-order').querySelector('[value="author"]');
  const note=byId('ranking-note');
  if(recommendation.status==='provided'){
    const ids=recommendation.tiers.flatMap(t=>t.model_ids);
    if(new Set(ids).size!==collection.models.length||ids.length!==collection.models.length||collection.models.some(m=>!ids.includes(m.id)))throw new Error('Invalid recommendation coverage');
    let rank=1;
    for(const tier of recommendation.tiers){for(const id of tier.model_ids)authorRanks.set(id,rank);rank+=tier.model_ids.length;}
    choice.disabled=false;choice.textContent="Author's personal ranking";byId('sort-order').value='author';
    note.replaceChildren(el('strong','',"The benchmark author's personal ranking. "));
    note.append(`Provided ${recommendation.date}. This qualitative ordering applies to ${activeCase.label} and reflects the author's judgment; all three ICL rounds remain available for your own comparison. `);
    byId('settings-order-note').textContent="Rows follow this task's personal ranking. ";
  }else{
    byId('sort-order').value='alphabetical';
    choice.disabled=true;choice.textContent='Personal ranking not provided';
    note.replaceChildren(el('strong','',`${activeCase.label} is unranked. `));
    note.append('Models appear alphabetically. No artistic-quality score or personal ranking has been supplied for this task. Rankings from other tasks do not apply. ');
    byId('settings-order-note').textContent='Rows are alphabetical. No ranking has been supplied for this task. ';
  }
  const link=el('a','','How results are presented ↗');link.href='docs/scoring.html';note.append(link);
}
function updateTaskContent(){
  const textOnly=collection.target.mode==='text';
  const golden=activeCase.id==='golden_gate';
  const label=golden?'THE GOLDEN GATE STUDY':'THE PELICAN STUDY';
  playbackSpeed=golden?6:4;
  document.documentElement.dataset.case=activeCase.id;
  document.title=`${activeCase.label} — RoboPaintBench`;
  document.querySelectorAll('[data-case]').forEach(link=>{
    const selected=link.dataset.case===activeCase.id;
    link.classList.toggle('active',selected);
    if(selected)link.setAttribute('aria-current','true');else link.removeAttribute('aria-current');
  });
  byId('hero-case-label').textContent=label;
  byId('hero-case-number').textContent=golden?'01 / 02':'02 / 02';
  byId('results-case-label').textContent=`${golden?'01':'02'} — ${label}`;
  const title=byId('results-title');title.replaceChildren(textOnly?'Same prompt.':'Same reference.',el('br'),el('em','','Different strokes.'));
  byId('reference-study').hidden=textOnly;
  byId('prompt-study').hidden=!textOnly;
  byId('hero-prompt').textContent=collection.target.instruction;
  document.querySelector('.hero-scene').hidden=textOnly;
  const showcase=collection.models.find(m=>m.id==='astra')||collection.models[0];
  const canvas=showcase.attempts.find(a=>a.attempt===3);
  const painting=imageFor(showcase,canvas,true);painting.id='hero-painting';
  const paintingLink=byId('hero-painting-link');paintingLink.replaceChildren(painting);paintingLink.href=safeAsset(canvas.canvas.path);
  paintingLink.setAttribute('aria-label',`Open ${showcase.label}'s ${activeCase.label} Round 3 painting at full size`);
  byId('hero-painting-caption').textContent=`${showcase.label} · ICL Round 3`;
  byId('observation-description').textContent=`Two workspace views, flange pose, and public action feedback. ${textOnly?'The drawing target is text only; no reference image is attached.':'The reference is attached at the start of each round.'}`;
  byId('recordings-summary').textContent=`One player · ${collection.models.length} models · ${playbackSpeed}× playback`;
  byId('recordings-caption').textContent=`Each video follows three sequential ICL rounds in one continuous session, at ${playbackSpeed}× simulation-time speed with Chinese and English captions. Model thinking waits are absent from recordings. Model input uses two fixed 960 × 720 workspace cameras; the brush-follow camera is only for human viewing. If the embedded player does not load, open the selected recording on Bilibili.`;
  byId('run-command').textContent=`python scripts/prepare_run.py \\\n  --case ${activeCase.id} --model sol`;
  const replay=byId('case-colab-link');
  const colab=publicURL(activeCase.colab_url);
  replay.href=colab||'docs/replay.html';
  replay.textContent=colab?`Open ${activeCase.label} Colab ↗`:'Replay this task locally ↗';
  byId('colab-steps').hidden=!colab;
  byId('colab-description').textContent=colab?'Choose a model record and replay its painting process with GPU rendering. Follow the camera views, actions and results in the viewer. No model API key is needed.':'Use this task’s public record with the official AgentArk replay flow. No model API call is needed.';
  byId('result-metadata-link').href=`data/${activeCase.results}`;
  byId('footer-collection').textContent=`v0.1 · ${activeCase.label} collection`;
}
async function activateCase(id){
  const descriptor=caseCatalog.cases.find(item=>item.id===id);
  if(!descriptor)return;
  const version=++switchVersion;
  byId('case-status').textContent=`Loading ${descriptor.label}…`;
  byId('results').setAttribute('aria-busy','true');
  // Stop the old task's embedded video as soon as navigation begins.
  byId('model-video-player').removeAttribute('src');
  if(byId('painting-dialog').open)byId('painting-dialog').close();
  try{
    const ids=inlineIds[id]||{};
    const [results,ranking,videos]=await Promise.all([
      readData(ids.results,descriptor.results),
      readData(ids.recommendation,descriptor.recommendation),
      readData(ids.videos,descriptor.videos).catch(()=>null)
    ]);
    if(version!==switchVersion)return;
    if(results.case_id!==id||ranking.case_id!==id||!Array.isArray(results.models)||!results.models.length)throw new Error('Invalid task collection');
    if(id==='pelican'&&(results.target?.mode!=='text'||results.target.reference!==null))throw new Error('Pelican must have a text-only target');
    activeCase=descriptor;collection=results;recommendation=ranking;
    collection.models.sort((a,b)=>a.label.localeCompare(b.label));
    renderRanking();updateTaskContent();
    byId('model-count').textContent=collection.models.length;
    byId('canvas-count').textContent=collection.models.reduce((n,m)=>n+m.attempts.length,0);
    byId('model-search').value='';
    for(const control of ['compare-left','compare-right']){
      byId(control).replaceChildren();
      for(const model of orderedModels(collection.models,recommendation.status==='provided'?'author':'alphabetical')){
        const option=el('option','',model.label);option.value=model.id;byId(control).append(option);
      }
    }
    byId('compare-left').value=collection.models.some(m=>m.id==='astra')?'astra':collection.models[0].id;
    byId('compare-right').value=collection.models.some(m=>m.id==='sol')?'sol':collection.models[1]?.id||collection.models[0].id;
    renderGallery();renderComparison();renderSettings();initModelVideos(videos);
    byId('case-status').textContent=`${activeCase.label} · ${textTargetLabel()} · ${collection.models.length} models, three rounds each`;
  }catch{
    if(version!==switchVersion)return;
    byId('case-status').textContent=`${descriptor.label} could not be loaded. ${activeCase?'The previously loaded task remains selected.':''}`;
    const previousVideo=document.querySelector('[data-video-model].active')?.dataset.videoModel;
    if(previousVideo&&activeCase?.id!==id)selectModelVideo(previousVideo);
    if(!collection){byId('gallery-status').textContent='Result metadata could not be loaded.';byId('gallery').replaceChildren(el('p','error','Serve the assembled site over HTTP after running scripts/build_site.py. See docs/hosting.md for local preview commands.'));}
  }finally{if(version===switchVersion)byId('results').removeAttribute('aria-busy');}
}
function textTargetLabel(){return collection.target.mode==='text'?'text-only target':'reference-image target';}
function caseFromHash(){return caseCatalog.cases.find(item=>`#${item.hash}`===location.hash);}
async function init(){
  byId('sort-order').addEventListener('change',()=>{if(collection)renderGallery();});
  for(const id of ['compare-left','compare-right','compare-attempt'])byId(id).addEventListener('change',()=>{if(collection)renderComparison();});
  document.querySelectorAll('[data-attempt]').forEach(button=>button.addEventListener('click',()=>{
    selectedAttempt=Number(button.dataset.attempt);
    document.querySelectorAll('[data-attempt]').forEach(b=>{const on=Number(b.dataset.attempt)===selectedAttempt;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});
    if(collection)renderGallery();
  }));
  byId('model-search').addEventListener('input',()=>{if(collection)renderGallery();});
  document.querySelectorAll('.track-list [data-case]').forEach(link=>link.addEventListener('click',()=>byId('results').scrollIntoView({block:'start'})));
  try{
    caseCatalog=await readData('benchmark-cases-data','cases.json');
    if(!Array.isArray(caseCatalog.cases)||!caseCatalog.cases.length||!caseCatalog.cases.some(item=>item.id===caseCatalog.default_case_id))throw new Error('Invalid task catalog');
    window.addEventListener('hashchange',()=>{const selected=caseFromHash();if(selected)void activateCase(selected.id);});
    await activateCase(caseFromHash()?.id||caseCatalog.default_case_id);
  }catch{byId('case-status').textContent='The task catalog could not be loaded. Build the site before previewing it.';}
}
byId('painting-dialog').querySelector('.dialog-close').addEventListener('click',()=>byId('painting-dialog').close());
byId('painting-dialog').addEventListener('click',event=>{if(event.target===byId('painting-dialog')){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
byId('copy-command').addEventListener('click',async()=>{const button=byId('copy-command');try{await navigator.clipboard.writeText(`python scripts/prepare_run.py --case ${activeCase?.id||'golden_gate'} --model sol`);button.textContent='Copied';}catch{button.textContent='Select code';}setTimeout(()=>button.textContent='Copy',1800);});
document.querySelectorAll('#hero-scene-image,#reference-study img').forEach(img=>img.addEventListener('error',()=>{const note=el('div','media-missing');note.append(el('p','','Local preview assets are assembled separately from the source repository.'));img.hidden=true;img.after(note);},{once:true}));
byId('model-video-poster').addEventListener('error',()=>{byId('model-video-poster').hidden=true;},{once:true});
init();
