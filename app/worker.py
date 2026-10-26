import argparse
import logging
import time

from app.config import get_settings
from app.database import SessionLocal
from app.judging.judge0 import Judge0Client
from app.judging.service import GradingService


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(*, once: bool, idle_seconds: float) -> None:
    judge = Judge0Client(get_settings())
    service = GradingService(SessionLocal, judge)
    while True:
        processed = service.process_next()
        if once:
            return
        if not processed:
            time.sleep(idle_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker chấm bài qua Judge0")
    parser.add_argument("--once", action="store_true", help="Xử lý tối đa một lượt rồi thoát")
    parser.add_argument("--idle-seconds", type=float, default=1.0)
    args = parser.parse_args()
    logger.info("grading_worker_started once=%s", args.once)
    run(once=args.once, idle_seconds=args.idle_seconds)


if __name__ == "__main__":
    main()
