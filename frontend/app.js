'use strict';
const $=id=>document.getElementById(id);
let currentFile=null, report=null, previewData=null;
const emptyText='';
function error(message){$('errorBox').textContent=message;$('errorBox').classList.remove('hidden');}
function clearError(){$('errorBox').classList.add('hidden');$('errorBox').textContent='';}
function num(id){const s=$(id).value.trim();return s===''?null:Number(s);}
function safeText(cell){return cell===null||cell===undefined?'—':String(cell);}
async function callApi(path,form){let r=await fetch(path,{method:'POST',body:form});let value;
  try{value=await r.json();}catch{throw Error(`HTTP ${r.status}: server did not return JSON`)}
  if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));
  return value;
}
function formWithFile(){const f=new FormData();f.append('file',currentFile);f.append('header_row',$('headerRow').value);return f;}
$('datasetFile').addEventListener('change',event=>{
  currentFile=event.target.files[0]||null;previewData=null;report=null;
  $('fileMeta').textContent=currentFile?`${currentFile.name} · ${(currentFile.size/1024).toFixed(0)} KB`:'No file selected';
  $('inspectBtn').disabled=!currentFile;$('evaluateBtn').disabled=true;
  $('previewBox').classList.add('hidden');$('resultSection').classList.add('hidden');clearError();
});
function fillSelect(id,items,selected,empty){let select=$(id);select.innerHTML='';if(empty){const option=document.createElement('option');option.value='';option.textContent=empty;select.append(option)}
 for(const item of items){const opt=document.createElement('option');opt.value=item;opt.textContent=item;select.append(opt)}
 if(selected && items.includes(selected))select.value=selected;select.disabled=false;
}
$('inspectBtn').onclick=async()=>{
  clearError();const btn=$('inspectBtn');btn.disabled=true;btn.textContent='Inspecting…';
  try{const data=await callApi('/api/preview',formWithFile());previewData=data;
  const orientation=data.dataset_type==='zenodo_orientation';
  if(orientation){
    fillSelect('timestampCol',['__day_hour__'],'__day_hour__');
    $('timestampCol').options[0].textContent='Day + Hour (relative, no year)';
    $('timestampCol').disabled=true;
    $('timestampLabel').textContent='Relative hourly time index';
    $('powerLabel').textContent='Measured PV output (source units)';
    $('datasetHelp').textContent='Recognized Zenodo rooftop PV dataset: 7,080 headerless rows with Day/Hour and five panel outputs. Calendar year, plant rating and whether power is W or Wh are not documented. Results will remain in original source units.';
    $('capacity').disabled=true; $('acCapacity').disabled=true;
  }else{
    fillSelect('timestampCol',data.columns,data.suggested_timestamp);
    $('timestampLabel').textContent='Measurement timestamp';
    $('powerLabel').textContent='Measured AC power (kW)';
    $('datasetHelp').textContent='Upload actual measured PV power in kW with authentic hourly timestamps. We never fabricate missing measurements.';
    $('capacity').disabled=false; $('acCapacity').disabled=false;
  }
  fillSelect('powerCol',data.columns,data.suggested_power);
  fillSelect('poaCol',orientation?[]:data.columns,null,'None — disable physical baseline');
  fillSelect('tempCol',orientation?[]:data.columns,null,'None — disable physical baseline');
  if(orientation){$('poaCol').disabled=true;$('tempCol').disabled=true;}
  $('rowCount').textContent=`${data.total_rows.toLocaleString()} rows / ${data.columns.length} columns`;
  const table=document.createElement('table'),head=document.createElement('thead'),row=document.createElement('tr');
  for(const col of data.columns){const cell=document.createElement('th');cell.textContent=col;row.append(cell)}head.append(row);table.append(head);
  const body=document.createElement('tbody');for(const item of data.preview){const tr=document.createElement('tr');for(const col of data.columns){const td=document.createElement('td');td.textContent=safeText(item[col]);tr.append(td)}body.append(tr)}table.append(body);
  $('previewTable').replaceChildren(table);$('previewBox').classList.remove('hidden');$('evaluateBtn').disabled=false;$('runExperiment2').disabled=data.dataset_type!=='zenodo_orientation';
  }catch(err){error(err.message)}finally{btn.disabled=false;btn.textContent='Inspect file →'}
};
$('evaluateBtn').onclick=async()=>{
  clearError();const btn=$('evaluateBtn');btn.disabled=true;btn.textContent='Training and evaluating…';
  try{const form=formWithFile();form.append('timestamp_column',$('timestampCol').value);
    form.append('power_column',$('powerCol').value);form.append('timezone',$('timezone').value.trim());
    if(num('capacity')!==null)form.append('capacity_kw',num('capacity'));
    if(num('acCapacity')!==null)form.append('ac_capacity_kw',num('acCapacity'));
    if($('poaCol').value)form.append('poa_forecast_column',$('poaCol').value);
    if($('tempCol').value)form.append('temp_forecast_column',$('tempCol').value);
    report=await callApi('/api/evaluate',form);renderReport(report);
  }catch(err){error(err.message)}finally{btn.disabled=false;btn.innerHTML='Run chronological evaluation <span>↗</span>'}
};
function renderReport(r){$('resultSection').classList.remove('hidden');
 $('selectedModel').textContent=`Validation-selected model: ${r.selected_model.replaceAll('_',' ')} · ${r.forecast_horizon}`;
 $('testWindow').textContent=r.dataset_type==='zenodo_orientation'?`TEST BEGINS D${r.data_quality.first_test_day} H${r.data_quality.first_test_hour}`:`TEST BEGINS ${r.data_quality.test_start_utc}`;
 const orientation=r.dataset_type==='zenodo_orientation';
 $('chartDescription').textContent=orientation?'Actual and predicted values in original dataset units (source describes W or Wh ambiguously). Generating-hour metrics use observed irradiance only to filter test-period evaluation.':'The chart is generated only after evaluation. No demonstration values are substituted.';
 const table=document.createElement('table');const head=document.createElement('thead');const tr=document.createElement('tr');
 for(const label of orientation?['Model','Test MAE (source unit)','Test RMSE (source unit)','Generating-hours MAE','Test R²']:['Model','Test MAE kW','Test RMSE kW','Test nRMSE %','Test R²']){const el=document.createElement('th');el.textContent=label;tr.append(el)}head.append(tr);table.append(head);
 const body=document.createElement('tbody');for(const key of r.ranking_validation){const m=r.scores[key].test;const tr=document.createElement('tr');
  const values=orientation?[key.replaceAll('_',' '),m.mae,m.rmse,r.scores[key].test_generating_hours.mae??'—',m.r2??'—']:[key.replaceAll('_',' '),m.mae_kw,m.rmse_kw,m.nrmse_pct_of_capacity??'—',m.r2??'—'];
  for(const val of values){const td=document.createElement('td');td.textContent=String(val);tr.append(td)}body.append(tr)}table.append(body);$('metricTable').replaceChildren(table);
 $('warnings').replaceChildren(...r.warnings.map(s=>{const p=document.createElement('p');p.textContent=`· ${s}`;return p}));
 const chartRows=orientation?r.sample_predictions.map(row=>({timestamp_utc:row.label,actual_kw:row.actual,[r.selected_model+'_kw']:row.forecasts[r.selected_model]})):r.sample_predictions;
 drawChart(chartRows,'actual_kw',`${r.selected_model}_kw`,orientation);$('resultSection').scrollIntoView({behavior:'smooth',block:'start'});
}
function drawChart(rows,a,b,relative=false){const svg=$('forecastChart');svg.replaceChildren();const NS='http://www.w3.org/2000/svg';
 const W=960,H=295,left=52,right=16,top=17,bottom=37;
 const all=rows.flatMap(x=>[x[a],x[b]]);const ymax=Math.max(1,Math.max(...all)*1.08);const X=i=>left+(W-left-right)*(i/(rows.length-1||1));const Y=y=>top+(H-top-bottom)*(1-y/ymax);
 function element(type,attrs,text){const e=document.createElementNS(NS,type);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;svg.append(e);return e}
 for(let j=0;j<=4;j++){const val=ymax*j/4,yy=Y(val);element('line',{x1:left,y1:yy,x2:W-right,y2:yy,stroke:'#e6eae4','stroke-width':1});element('text',{x:8,y:yy+4,'font-size':12,fill:'#758681','font-family':'IBM Plex Mono'},val.toFixed(0))}
 for(const [key,color] of [[a,'#21777d'],[b,'#c7813d']]){const pts=rows.map((v,i)=>`${X(i).toFixed(2)},${Y(v[key]).toFixed(2)}`).join(' ');element('polyline',{points:pts,fill:'none',stroke:color,'stroke-width':2.5,'stroke-linejoin':'round','stroke-linecap':'round'})}
 for(const i of [0,Math.floor((rows.length-1)/2),rows.length-1]){const timestamp=rows[i]?.timestamp_utc||'';element('text',{x:X(i),y:H-10,'text-anchor':i===0?'start':i===rows.length-1?'end':'middle','font-size':11,fill:'#758681','font-family':'IBM Plex Mono'},relative?timestamp:timestamp.slice(5,16).replace('T',' '))}
 element('text',{x:8,y:12,'font-size':11,fill:'#758681','font-family':'IBM Plex Mono'},relative?'Source unit':'kW')
}
$('exportBtn').onclick=()=>{if(!report)return;const json=JSON.stringify(report,null,2);const blob=new Blob([json],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='pv_chronological_evaluation.json';a.click();URL.revokeObjectURL(url)};
$('openMap').onclick=()=>{const lat=num('latitude'),lon=num('longitude');if(lat===null||lon===null||lat < -90||lat>90||lon < -180||lon>180){error('Enter a valid latitude (-90 to 90) and longitude (-180 to 180).');return}clearError();window.open(`https://www.openstreetmap.org/?mlat=${encodeURIComponent(lat)}&mlon=${encodeURIComponent(lon)}#map=12/${lat}/${lon}`,'_blank','noopener,noreferrer')};
fetch('/api/health').then(x=>x.json()).then(x=>{$('apiStatus').textContent=x.status==='ok'?'Forecast engine ready':'Engine unavailable';}).catch(()=>{$('apiStatus').textContent='Engine unavailable'});


// EXP-002: advanced model comparison and complete audit exports

let exp2Report=null;
function exp2Esc(s){return String(s===null||s===undefined?'—':s);}
function exp2Download(content, name, type){
  const objectURL=URL.createObjectURL(new Blob([content],{type}));
  const a=document.createElement('a');a.href=objectURL;a.download=name;
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(objectURL),1500);
}
function exp2Metrics(report){
  const names=report.ranking_validation;
  const cols=['Model','Validation MAE','Test MAE','Test RMSE','Test R²','Generating-hour MAE'];
  const table=document.createElement('table');const thead=document.createElement('thead');
  let row=document.createElement('tr');
  for(const text of cols){const th=document.createElement('th');th.textContent=text;row.append(th)}
  thead.append(row);table.append(thead);
  const body=document.createElement('tbody');
  for(const name of names){
    const val=report.scores[name].validation,test=report.scores[name].test;
    const daylight=report.scores[name].test_generating_hours;
    const values=[name.replaceAll('_',' '),val.mae,test.mae,test.rmse,test.r2,daylight.mae];
    row=document.createElement('tr');
    for(const value of values){const cell=document.createElement('td');cell.textContent=exp2Esc(value);row.append(cell)}
    body.append(row);
  }
  table.append(body);$('exp2Metrics').replaceChildren(table);
}
function exp2Draw(rows,model){
  const svg=$('exp2Chart'),ns='http://www.w3.org/2000/svg';
  svg.replaceChildren();
  if(rows.length<2)return;
  const w=960,h=280,l=48,r=14,t=20,b=34;
  const hi=Math.max(1,...rows.flatMap(row=>[row.actual,row.forecasts[model]]))*1.07;
  const X=i=>l+(w-l-r)*i/(rows.length-1),Y=v=>t+(h-t-b)*(1-v/hi);
  function el(kind,attrs,content){const node=document.createElementNS(ns,kind);
    for(const [key,value] of Object.entries(attrs))node.setAttribute(key,String(value));
    if(content!==undefined)node.textContent=String(content);svg.append(node);}
  for(let z=0;z<=4;z++){let val=hi*z/4,yy=Y(val);
    el('line',{x1:l,y1:yy,x2:w-r,y2:yy,stroke:'#e6eae4','stroke-width':1});
    el('text',{x:7,y:yy+4,fill:'#758681','font-size':11},val.toFixed(0));}
  for(const [get,color] of [[v=>v.actual,'#21777d'],[v=>v.forecasts[model],'#c7813d']]){
    const points=rows.map((row,i)=>X(i).toFixed(2)+','+Y(get(row)).toFixed(2)).join(' ');
    el('polyline',{points,fill:'none',stroke:color,'stroke-width':2.5,'stroke-linejoin':'round'});}
  for(const idx of [0,Math.floor((rows.length-1)/2),rows.length-1]){
    const value=rows[idx];el('text',{x:X(idx),y:h-10,
      'text-anchor':idx===0?'start':idx===rows.length-1?'end':'middle',
      'font-size':11,fill:'#758681'},'D'+value.day+' H'+String(value.hour).padStart(2,'0'));}
  el('text',{x:6,y:10,fill:'#758681','font-size':11},'Source unit');
}
function exp2Render(r){
  exp2Report=r;
  $('experiment2Results').classList.remove('hidden');
  $('exp2Selection').textContent='Validation-selected: '+r.selected_model.replaceAll('_',' ')
    +' · '+r.data_quality.test_rows+' unseen test hours';
  $('exp2Summary').textContent='Experiment '+r.experiment_id+' · '
    +r.data_quality.train_rows+' training, '+r.data_quality.validation_rows
    +' validation, '+r.data_quality.test_rows+' test samples. '
    +'Metrics are in original source units (W/Wh unresolved), not kW.';
  exp2Metrics(r);
  exp2Draw(r.predictions.slice(-240),r.selected_model);
  $('exp2Cautions').replaceChildren(...r.warnings.map(message=>{
    const line=document.createElement('p');line.textContent='· '+message;return line;}));
  $('experiment2Results').scrollIntoView({behavior:'smooth',block:'start'});
}
$('runExperiment2').addEventListener('click',async()=>{
  clearError();
  if(!currentFile||previewData?.dataset_type!=='zenodo_orientation'){
    error('Inspect the original PV_Data.xlsx orientation workbook first.');return;
  }
  const button=$('runExperiment2');
  button.disabled=true;button.textContent='Training models and exporting all test predictions…';
  try{
    const form=new FormData();form.append('file',currentFile);
    form.append('power_column',$('powerCol').value);
    form.append('include_xgboost',$('exp2Xgb').checked?'true':'false');
    form.append('include_lstm',$('exp2Lstm').checked?'true':'false');
    const response=await callApi('/api/experiment2',form);
    exp2Render(response);
  }catch(err){error(err.message)}finally{
    button.disabled=false;button.innerHTML='Run Experiment 002 <span>↗</span>';
  }
});
$('exp2JSON').addEventListener('click',()=>{
  if(!exp2Report)return;
  exp2Download(JSON.stringify(exp2Report,null,2),'EXP-002_full_evaluation.json','application/json');
});
$('exp2CSV').addEventListener('click',()=>{
  if(!exp2Report)return;
  const models=Object.keys(exp2Report.scores);
  const header=['relative_hour_index','day','hour','actual_source_unit','generating_hour_ex_post',...models];
  const lines=[header.join(',')];
  for(const p of exp2Report.predictions){
    lines.push([p.relative_hour_index,p.day,p.hour,p.actual,p.generating_hour_ex_post,
       ...models.map(m=>p.forecasts[m])].join(','));
  }
  exp2Download(lines.join('\n')+'\n','EXP-002_all_test_predictions.csv','text/csv');
});

$('datasetFile').addEventListener('change',()=>{ $('runExperiment2').disabled=true; $('experiment2Results').classList.add('hidden'); exp2Report=null; });
