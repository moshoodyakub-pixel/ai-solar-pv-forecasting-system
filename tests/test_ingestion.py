import io
import pandas as pd
import pytest
from backend.forecasting.ingestion import read_table, DataError, preview


def test_numeric_column_names_are_supported():
    raw=b'1,2,3\n10,20,30\n40,50,60\n'
    df=read_table(raw,'sample.csv')
    assert list(df.columns)==['1','2','3']
    assert preview(df)['total_rows']==2


def test_headerless_csv_can_be_opened():
    df=read_table(b'1,2\n3,4','data.csv',header_row=-1)
    assert list(df.columns)==['0','1']
    assert df.shape==(2,2)


def test_reject_unsupported_extension():
    with pytest.raises(DataError,match='CSV or XLSX'):
        read_table(b'any','data.xls')
