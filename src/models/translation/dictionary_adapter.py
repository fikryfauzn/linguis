from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class DictionaryAdapter(ABC):
    @abstractmethod
    def lookup(self, term: str) -> Optional[Dict[str, Any]]:
        """
        Returns structured data:
        {
            "word": "praise",
            "phonetic": "/preiz/",
            "definitions": [
                {"pos": "noun", "text": "The expression of approval..."},
                {"pos": "verb", "text": "To express warm approval..."}
            ]
        }
        """
        pass

    @abstractmethod
    def close(self):
        pass