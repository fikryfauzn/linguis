import sys
import asyncio
from pathlib import Path

import qasync
from PyQt6.QtWidgets import QApplication

from src.views.main_window import MainWindow
from src.utils.logging import setup_logging, get_logger


# --- DEV BOOTSTRAP (USER DATA, NOT PROJECT DATA) -----------------

TEST_PDF = (
    Path.home()
    / "Documents/Books/Philosophy/Marcus Aurelius - Meditations"
)

# ----------------------------------------------------------------


def main() -> None:
    setup_logging()
    logger = get_logger("Main")

    app = QApplication(sys.argv)
    app.setApplicationName("LinuxReader")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    # --- TEMP DEV LOAD ---
    if TEST_PDF.exists():
        logger.info(f"Opening: {TEST_PDF}")
        window.load_file(str(TEST_PDF))
    else:
        logger.warning(f"File not found: {TEST_PDF}")
    # --------------------

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
