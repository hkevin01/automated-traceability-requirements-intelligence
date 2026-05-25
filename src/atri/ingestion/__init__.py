# ID: ATRI-ING-001
# Purpose: Ingestion package - exports all public adapter classes and IngestionResult.
from atri.ingestion.base import IngestionResult
from atri.ingestion.doors import DOORSAdapter
from atri.ingestion.jama import JamaAdapter
from atri.ingestion.sysml import SysMLAdapter
from atri.ingestion.visure import VisureAdapter
from atri.ingestion.word_pdf import WordPDFAdapter

__all__ = [
    "IngestionResult",
    "DOORSAdapter",
    "JamaAdapter",
    "SysMLAdapter",
    "VisureAdapter",
    "WordPDFAdapter",
]
