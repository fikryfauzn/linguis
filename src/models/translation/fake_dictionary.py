import time
from typing import Optional, Dict, Any
from .dictionary_adapter import DictionaryAdapter

class FakeDictionary(DictionaryAdapter):
    """
    T1.2: Dummy Dictionary with Structured Data.
    """

    def lookup(self, term: str) -> Optional[Dict[str, Any]]:
        # Simulate I/O latency
        time.sleep(0.3)
        
        clean_term = term.strip().lower()
        
        # Simulating a "Miss" for very short words
        if len(clean_term) < 2:
            return None

        # Return STRUCTURED DATA (The fix)
        return {
            "word": term,
            "phonetic": "/preiz/", # Dummy phonetic
            "definitions": [
                {
                    "pos": "noun", 
                    "text": "The expression of approval or admiration for someone or something."
                },
                {
                    "pos": "verb", 
                    "text": "To express warm approval or admiration of; to commend the worth of."
                },
                {
                    "pos": "verb", 
                    "text": "To glorify, especially by attribution of perfection; to worship or honor."
                },
                {
                    "pos": "noun", 
                    "text": "(Archaic) Value or merit."
                }
            ]
        }

    def close(self):
        pass