import time
from typing import Optional, Dict, Any
from .dictionary_adapter import DictionaryAdapter

class FakeDictionary(DictionaryAdapter):
    """
    T1.2: Fallback Dictionary.
    Now strictly returns 'None' to allow the UI to show 'Lookup Failed' correctly,
    instead of showing fake data that confuses the user.
    """

    def lookup(self, term: str) -> Optional[Dict[str, Any]]:
        # Return None so the UI shows the "Lookup Failed" state
        # instead of showing "Praise" for every missing word.
        return None

    def close(self):
        pass