"""Measured-PV Experiment 002 API; no research data is stored by the server."""
from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from .forecasting.experiment2 import run_experiment
from .forecasting.ingestion import DataError, MAX_BYTES

router = APIRouter(prefix='/api')


def _decode(data: bytes, filename: str) -> pd.DataFrame:
    if len(data)>MAX_BYTES:
        raise DataError('Uploaded research file exceeds 25 MB limit.')
    if not data or not filename.lower().endswith('.xlsx'):
        raise DataError('Experiment 002 currently accepts the original orientation-diverse PV_Data.xlsx workbook only.')
    try:
        with pd.ExcelFile(BytesIO(data),engine='openpyxl') as book:
            if not {'DATA','DATA DESCRIPTION'}.issubset(book.sheet_names):
                raise DataError('Workbook must contain DATA and DATA DESCRIPTION sheets.')
            labels = pd.read_excel(book,sheet_name='DATA DESCRIPTION',header=None,nrows=2).iloc[1].tolist()
            if len(labels)!=21 or labels[0]!='Day' or labels[-1]!='Total PV Power':
                raise DataError('Variable dictionary in DATA DESCRIPTION was not recognised.')
            frame=pd.read_excel(book,sheet_name='DATA',header=None)
            if frame.shape[1]!=21:
                raise DataError('DATA sheet must contain exactly 21 fields.')
            frame.columns=labels
            return frame
    except DataError:
        raise
    except (ValueError,KeyError,IndexError,OSError,ImportError,BadZipFile) as exc:
        raise DataError(f'Unable to import original Excel workbook: {exc}') from exc


def _run(raw: bytes, filename: str, target: str, xgb: bool, lstm: bool) -> dict:
    frame=_decode(raw,filename)
    return run_experiment(frame, target=target, source_bytes=raw,
                          include_xgboost=xgb, include_lstm=lstm)


@router.post('/experiment2')
async def experiment2(file: UploadFile = File(...),
                      power_column: str = Form('Total PV Power'),
                      include_xgboost: bool = Form(True),
                      include_lstm: bool = Form(True)):
    try:
        # An upload is read into memory only; never persisted or committed.
        raw=await file.read(MAX_BYTES+1)
        return await run_in_threadpool(_run,raw,file.filename or '',power_column,
                                       include_xgboost,include_lstm)
    except DataError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
