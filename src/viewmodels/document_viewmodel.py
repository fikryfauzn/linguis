import asyncio
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage
from ..models.documents.pdf_parser import PdfParser
from ..models.selection.selection_model import SelectionModel
from ..utils.logging import get_logger


class DocumentViewModel(QObject):
    document_loaded = pyqtSignal(list)
    page_rendered = pyqtSignal(int, QImage, int)
    load_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._logger = get_logger("DocumentVM")
        self._parser = PdfParser()
        self._executor = ThreadPoolExecutor(max_workers=2)

        self._active_tasks: dict[int, asyncio.Task] = {}
        self._current_zoom = 100

        self._selection_models: dict[int, SelectionModel] = {}

    def load_document(self, file_path: str):
        """Loads the document and pre-calculates character maps."""
        try:
            self._parser.load(file_path)
            count = self._parser.get_page_count()

            page_sizes = []
            self._selection_models.clear()

            self._logger.info(f"Processing {count} pages for selection layout...")

            for i in range(count):
                page_sizes.append(self._parser.get_page_size(i, 100))

                char_data = self._parser.get_character_map(i)

                model = SelectionModel(i)
                model.set_characters(char_data)
                self._selection_models[i] = model

            self.document_loaded.emit(page_sizes)
            self._logger.info(
                f"Loaded document: {count} pages with full selection maps"
            )

        except Exception as e:
            self._logger.error(f"Load error: {e}")
            self.load_failed.emit(str(e))

    def get_selection_model(self, page_index: int) -> SelectionModel:
        """Returns the SelectionModel for a page."""
        return self._selection_models.get(page_index)

    def set_zoom(self, zoom_level: int):
        self._current_zoom = zoom_level

    async def request_page(self, page_index: int, zoom_level: int):
        """Renders a page asynchronously."""
        if page_index in self._active_tasks:
            self._active_tasks[page_index].cancel()

        task = asyncio.create_task(
            self._render_page_internal(page_index, zoom_level)
        )
        self._active_tasks[page_index] = task

        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            if page_index in self._active_tasks:
                del self._active_tasks[page_index]

    async def _render_page_internal(self, page_index: int, zoom_level: int):
        loop = asyncio.get_running_loop()
        try:
            image = await loop.run_in_executor(
                self._executor,
                self._parser.render_page,
                page_index,
                zoom_level,
            )
            if image:
                self.page_rendered.emit(page_index, image, zoom_level)
        except Exception as e:
            self._logger.warning(
                f"Failed to render page {page_index}: {e}"
            )

    def cancel_obsolete_renders(self, keep_indices: set[int]):
        to_cancel = set(self._active_tasks.keys()) - keep_indices
        for page_index in to_cancel:
            if page_index in self._active_tasks:
                self._active_tasks[page_index].cancel()

    def close(self):
        for task in self._active_tasks.values():
            task.cancel()
        self._executor.shutdown(wait=False)
        self._parser.close()
