"""FastAPI backend and self-contained engineering dashboard."""
from __future__ import annotations
from pathlib import Path
import io
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .forecasting.ingestion import read_table, preview, DataError
from .forecasting.evaluation import evaluate
from .forecasting.orientation import is_orientation_dataset, evaluate_orientation

ROOT=Path(__file__).resolve().parents[1]
app=FastAPI(title='AI Solar PV Forecasting System',version='0.1.0',
 description='Measured-PV chronological validation research prototype')
app.mount('/assets',StaticFiles(directory=str(ROOT/'frontend')),name='assets')

@app.get('/')
def dashboard():
    return FileResponse(ROOT/'frontend'/'index.html')

@app.get('/api/health')
def health():
    return {'status':'ok','version':'0.1.0','dataset':'not bundled','model':'not pre-trained'}

async def parse(upload:UploadFile,header_row:int):
    payload=await upload.read()
    try:
        return read_table(payload,upload.filename or 'unknown',header_row=header_row)
    except DataError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc

@app.post('/api/preview')
async def preview_file(file:UploadFile=File(...),header_row:int=Form(0)):
    frame=await parse(file,header_row)
    return preview(frame)

@app.post('/api/evaluate')
async def evaluate_file(file:UploadFile=File(...),timestamp_column:str=Form(...),power_column:str=Form(...),
                        timezone:str=Form('UTC'),header_row:int=Form(0),
                        capacity_kw:float|None=Form(None),ac_capacity_kw:float|None=Form(None),
                        poa_forecast_column:str|None=Form(None),temp_forecast_column:str|None=Form(None)):
    frame=await parse(file,header_row)
    try:
        if is_orientation_dataset(frame):
            return evaluate_orientation(frame,power_column)
        return evaluate(frame,timestamp_column,power_column,timezone=timezone,capacity_kw=capacity_kw,
                        ac_capacity_kw=ac_capacity_kw,poa_forecast_column=poa_forecast_column or None,
                        temp_forecast_column=temp_forecast_column or None)
    except DataError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
