"""Experiment 003 HTTP endpoint. Source workbook stays in memory."""
from __future__ import annotations
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from .experiment2_api import _decode
from .forecasting.experiment3 import run_experiment3
from .forecasting.ingestion import MAX_BYTES, DataError

router = APIRouter(prefix='/api')

def _run(raw, name, power, xgb, lstm, count, hours):
    frame=_decode(raw,name)
    return run_experiment3(frame,target=power,source_bytes=raw,
        include_xgboost=xgb,include_lstm=lstm,fold_count=count,fold_hours=hours)

@router.post('/experiment3')
async def experiment3(file: UploadFile=File(...),
                      power_column: str=Form('Total PV Power'),
                      include_xgboost: bool=Form(True),include_lstm: bool=Form(True),
                      fold_count: int=Form(4),fold_days: int=Form(14)):
    try:
        if fold_days<1 or fold_days>42:
            raise DataError('Validation fold days must be 1–42.')
        raw=await file.read(MAX_BYTES+1)
        return await run_in_threadpool(_run,raw,file.filename or '',power_column,
                       include_xgboost,include_lstm,fold_count,fold_days*24)
    except DataError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
