"""Research data ingestion: never silently invent missing timestamps or power values."""
from __future__ import annotations
from io import BytesIO
import pandas as pd

MAX_BYTES = 25 * 1024 * 1024

class DataError(ValueError):
    """User-correctable data/schema issue."""


def read_table(data: bytes, filename: str, header_row: int = 0) -> pd.DataFrame:
    if not data:
        raise DataError('File is empty.')
    if len(data) > MAX_BYTES:
        raise DataError('File exceeds the 25 MB research upload limit.')
    if header_row < -1 or header_row > 100:
        raise DataError('Header row must be -1 (no header) or between 0 and 100.')
    header = None if header_row == -1 else header_row
    name = filename.lower()
    try:
        if name.endswith('.csv'):
            frame = pd.read_csv(BytesIO(data), header=header)
        elif name.endswith('.xlsx'):
            frame = pd.read_excel(BytesIO(data), header=header, engine='openpyxl')
        else:
            raise DataError('Upload a CSV or XLSX file (not XLS or XLSM).')
    except (ValueError, OSError, ImportError, pd.errors.ParserError) as exc:
        raise DataError(f'Unable to read file: {exc}') from exc
    if frame.empty:
        raise DataError('The selected sheet contains no data rows.')
    # Numeric and blank headings are normal for some research workbooks.
    cols = [str(c).strip() if str(c).strip() else f'column_{i+1}' for i,c in enumerate(frame.columns)]
    counts: dict[str,int] = {}
    unique=[]
    for col in cols:
        n=counts.get(col,0)+1;counts[col]=n
        unique.append(col if n == 1 else f'{col}__{n}')
    frame.columns=unique
    return frame


def preview(frame: pd.DataFrame):
    sample = frame.head(8).copy()
    # Convert non-JSON-safe Excel timestamps and NaN without losing source values.
    rows = sample.astype(object).where(pd.notna(sample), None).to_dict(orient='records')
    for row in rows:
        for col,v in row.items():
            if isinstance(v, pd.Timestamp):
                row[col]=v.isoformat()
            elif v is not None and not isinstance(v,(str,int,float,bool)):
                row[col]=str(v)
    cols=list(frame.columns)
    def matching(words):
        return next((c for c in cols if any(w in c.lower() for w in words)),None)
    return {'columns':cols,'total_rows':len(frame),'preview':rows,
            'suggested_timestamp':matching(['timestamp','datetime','date','time']),
            'suggested_power':matching(['power_kw','pv_power','ac_power','generation','actual_power']),
            'note':'All values are from the uploaded file; this screen contains no model predictions.'}
