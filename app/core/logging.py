import logging


def setup_logging(level: int = logging.INFO) -> None:
    # shortcut: plain text logs; switch to JSON formatter when shipping to a log stack (TRD §9)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
