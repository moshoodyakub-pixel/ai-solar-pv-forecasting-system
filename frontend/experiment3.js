/* EXP-003: expanding-origin development validation and full-prediction export. */
'use strict';
(() => {
  const byId=id=>document.getElementById(id);
  const run=byId('exp3Run'), results=byId('exp3Results'), alert=byId('exp3Error');
  if(!run || !results)return;
  let report=null;
  const format=v=>v===undefined||v===null?'—':Number(v).toFixed(2);
  byId('datasetFile').addEventListener('change',()=>{
    report=null;run.disabled=true;results.classList.add('hidden');alert.classList.add('hidden');
  });
  byId('inspectBtn').addEventListener('click',()=>{
    run.disabled=!byId('datasetFile').files[0];
  });
  function showError(message){alert.textContent=message;alert.classList.remove('hidden');}
  function download(name,content,type){
    const url=URL.createObjectURL(new Blob([content],{type}));
    const a=document.createElement('a');
    a.href=url;a.download=name;document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),2000);
  }
  function makeTable(headings,rows){
    const table=document.createElement('table'),header=document.createElement('thead');
    const tr=document.createElement('tr');
    for(const name of headings){const th=document.createElement('th');th.textContent=name;tr.append(th)}
    header.append(tr);table.append(header);
    const body=document.createElement('tbody');
    for(const values of rows){
      const r=document.createElement('tr');
      for(const value of values){const cell=document.createElement('td');cell.textContent=String(value??'—');r.append(cell)}
      body.append(r);
    }
    table.append(body);return table;
  }
  function render(data){
    report=data;
    results.classList.remove('hidden');
    const q=data.data_quality;
    byId('exp3Winner').textContent='Lowest pooled development-validation MAE: '+
      data.development_recommendation.replaceAll('_',' ')+' · Earlier development data only';
    byId('exp3Summary').textContent=q.fold_count+' expanding folds ('+
      q.fold_hours/24+' days each), '+q.validation_predictions+
      ' fully exported validation predictions. Existing held-out rows start at '+
      q.reserved_15pct_start_source_row_1based+' and were not evaluated.';
    const names=data.ranked_models;
    byId('exp3ModelScores').replaceChildren(makeTable(
      ['Model','Pooled MAE','Generating MAE','High-ramp MAE','Fold MAE SD','Fit seconds'],
      names.map(name=>{
        const score=data.model_scores[name];
        return [name.replaceAll('_',' '),format(score.pooled_validation.mae),
          format(score.generating_hours_ex_post.mae),format(score.high_ramp_ex_post.mae),
          format(score.fold_mae_std),format(score.total_fit_seconds)];
      })));
    byId('exp3FoldScores').replaceChildren(makeTable(
      ['Fold','Training hours','Day range',...names.map(m=>m.replaceAll('_',' '))],
      data.folds.map(f=>[f.fold,f.train_rows,f.validation_first_day+'–'+f.validation_last_day,
        ...names.map(m=>format(f.metrics[m].all_hours.mae))])));
    byId('exp3Periods').replaceChildren(makeTable(
      ['Recorded hour bucket',...names.map(m=>m.replaceAll('_',' '))],
      ['morning_07_10','midday_11_15','evening_16_20','other_hours'].map(period=>
        [period,...names.map(m=>format(data.time_of_day_metrics[m][period].mae))])));
    byId('exp3Warnings').replaceChildren(...data.warnings.map(message=>{
      const p=document.createElement('p');p.textContent='· '+message;return p;
    }));
    results.scrollIntoView({behavior:'smooth',block:'start'});
  }
  run.addEventListener('click',async()=>{
    const file=byId('datasetFile').files[0];
    if(!file||!file.name.toLowerCase().endsWith('.xlsx')){
      showError('Choose and inspect the original PV_Data.xlsx file first.');return;
    }
    if(typeof previewData!=='undefined' && previewData?.dataset_type!=='zenodo_orientation'){
      showError('Inspect the original two-sheet orientation workbook before running EXP-003.');return;
    }
    alert.classList.add('hidden');
    run.disabled=true;const original=run.textContent;run.textContent='Evaluating expanding windows…';
    try{
      const form=new FormData();
      form.append('file',file);
      form.append('power_column',byId('powerCol').value||'Total PV Power');
      form.append('include_xgboost',String(byId('exp3Xgb').checked));
      form.append('include_lstm',String(byId('exp3Lstm').checked));
      form.append('fold_count',byId('exp3Folds').value);
      form.append('fold_days',byId('exp3Days').value);
      const response=await fetch('/api/experiment3',{method:'POST',body:form});
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
      render(data);
    }catch(error){showError(error.message)}
    finally{run.disabled=false;run.textContent=original}
  });
  byId('exp3Json').addEventListener('click',()=>{
    if(report)download('EXP-003_rolling_validation.json',JSON.stringify(report,null,2),'application/json');
  });
  byId('exp3Csv').addEventListener('click',()=>{
    if(!report)return;
    const names=Object.keys(report.model_scores);
    const fields=['fold','source_row_1based','day','hour','period','actual',
      'generating_hour_ex_post','observed_abs_ramp_source_unit_ex_post','high_ramp_ex_post',...names];
    const lines=[fields.join(',')];
    for(const r of report.predictions){
      lines.push([r.fold,r.source_row_1based,r.day,r.hour,r.period,r.actual,
        r.generating_hour_ex_post,r.observed_abs_ramp_source_unit_ex_post,r.high_ramp_ex_post,
        ...names.map(m=>r.forecasts[m])].join(','));
    }
    download('EXP-003_all_validation_predictions.csv',lines.join('\n')+'\n','text/csv');
  });
})();
