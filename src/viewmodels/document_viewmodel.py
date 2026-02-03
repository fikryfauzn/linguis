import asyncio
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage
from ..models.documents.pdf_parser import PdfParser
from ..utils.logging import get_logger

class DocumentViewModel(QObject):
    document_loaded = pyqtSignal(list)
    page_rendered = pyqtSignal(int, QImage, int)  # MODIFIED: Now includes render_zoom
    load_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._logger = get_logger("DocumentVM")
        self._parser = PdfParser()
        self._executor = ThreadPoolExecutor(max_workers=2)
        
        # Track active render tasks so we can cancel them
        self._active_tasks: dict[int, asyncio.Task] = {}
        
        # Track current zoom level
        self._current_zoom = 100

    def load_document(self, file_path: str):
        try:
            self._parser.load(file_path)
            count = self._parser.get_page_count()
            
            # Get page sizes at 100% zoom (base sizes)
            page_sizes = []
            for i in range(count):
                page_sizes.append(self._parser.get_page_size(i, 100))
            
            self.document_loaded.emit(page_sizes)
            self._logger.info(f"Loaded document skeleton: {count} pages")
        except Exception as e:
            self._logger.error(f"Load error: {e}")
            self.load_failed.emit(str(e))

    def set_zoom(self, zoom_level: int):
        """Update current zoom level for future renders."""
        self._current_zoom = zoom_level

    async def request_page(self, page_index: int, zoom_level: int):
        """
        Renders a page in background thread at specified zoom.
        Cancellable if user scrolls away before completion.
        """
        # Cancel any existing render for this page
        if page_index in self._active_tasks:
            self._active_tasks[page_index].cancel()
        
        # Create the render task
        task = asyncio.create_task(self._render_page_internal(page_index, zoom_level))
        self._active_tasks[page_index] = task
        
        try:
            await task
        except asyncio.CancelledError:
            self._logger.debug(f"Cancelled render for page {page_index}")
        finally:
            # Clean up task reference
            if page_index in self._active_tasks:
                del self._active_tasks[page_index]

    async def _render_page_internal(self, page_index: int, zoom_level: int):
        """Internal method that does the actual rendering."""
        loop = asyncio.get_running_loop()
        
        try:
            # Pass zoom level to the parser
            image = await loop.run_in_executor(
                self._executor,
                self._parser.render_page,
                page_index,
                zoom_level
            )
            
            if image:
                # Emit with zoom level so viewer knows what zoom this was rendered at
                self.page_rendered.emit(page_index, image, zoom_level)
                
        except Exception as e:
            self._logger.warning(f"Failed to render page {page_index} at {zoom_level}%: {e}")

    def cancel_obsolete_renders(self, keep_indices: set[int]):
        """
        Cancel all renders except those in the keep set.
        Called when user jumps to a new section.
        """
        to_cancel = set(self._active_tasks.keys()) - keep_indices
        
        for page_index in to_cancel:
            if page_index in self._active_tasks:
                self._active_tasks[page_index].cancel()
                self._logger.debug(f"Cancelling obsolete render: page {page_index}")

    def close(self):
        """Cleanup threads on exit"""
        # Cancel all active tasks
        for task in self._active_tasks.values():
            task.cancel()
        
        self._executor.shutdown(wait=False)
        self._parser.close()