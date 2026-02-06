import asyncio
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QObject, pyqtSignal

from ..models.translation.dictionary_adapter import DictionaryAdapter
from ..models.translation.stardict_adapter import StarDictAdapter
from ..models.translation.fake_dictionary import FakeDictionary
from ..utils.logging import get_logger

class TranslationViewModel(QObject):
    lookup_started = pyqtSignal(str)
    lookup_success = pyqtSignal(dict)
    lookup_failed = pyqtSignal(str) 

    def __init__(self):
        super().__init__()
        self._logger = get_logger("TranslationVM")
        
        # YOUR DICTIONARY PATH
        # Note: We omit the extension (.ifo, .dict.dz) as pystardict adds it automatically
        STARDICT_PATH = "/usr/share/stardict/dic/oald/Oxford_Advanced_Learner_s_Dictionary"
        
        try:
            self._adapter = StarDictAdapter(STARDICT_PATH)
            self._logger.info(f"Loaded StarDict: {STARDICT_PATH}")
        except Exception as e:
            self._logger.warning(f"StarDict load failed ({e}). Using FakeDictionary fallback.")
            self._adapter = FakeDictionary()
            
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._current_task: asyncio.Task = None

    async def lookup(self, term: str):
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        
        if not term or len(term.strip()) == 0:
            return

        self.lookup_started.emit(term)
        
        self._current_task = asyncio.create_task(self._lookup_internal(term))
        
        try:
            await self._current_task
        except asyncio.CancelledError:
            pass # Silent cancel

    async def _lookup_internal(self, term: str):
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                self._executor, 
                self._adapter.lookup, 
                term
            )
            
            if result:
                self.lookup_success.emit(result)
            else:
                self.lookup_failed.emit(f"No definition found for '{term}'")
                
        except Exception as e:
            self._logger.error(f"Lookup error: {e}")
            self.lookup_failed.emit("Error accessing dictionary.")

    def close(self):
        self._executor.shutdown(wait=False)
        self._adapter.close()