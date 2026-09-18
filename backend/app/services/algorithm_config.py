"""Runtime configuration shared by Java algorithm clients."""

import os

from app.paths import MODEL_STORAGE_ROOT


PMWNB_SERVICE_URL = os.getenv("PMWNB_SERVICE_URL", "http://127.0.0.1:12313")
PREDICT_SERVICE_URL = os.getenv("PREDICT_SERVICE_URL", "http://127.0.0.1:12314")
TRAIN_TIMEOUT = int(os.getenv("NB_TRAIN_TIMEOUT", "600"))
PREDICT_TIMEOUT = int(os.getenv("NB_PREDICT_TIMEOUT", "60"))
ALGORITHM_SERVICE_URLS = {
    "A2WNB": os.getenv("A2WNB_SERVICE_URL", "http://127.0.0.1:12315"),
    "CAVWNB": os.getenv("CAVWNB_SERVICE_URL", "http://127.0.0.1:12316"),
    "EMAWNB": os.getenv("EMAWNB_SERVICE_URL", "http://127.0.0.1:12317"),
    "MAWNB": os.getenv("MAWNB_SERVICE_URL", "http://127.0.0.1:12318"),
    "DIWNB": os.getenv("DIWNB_SERVICE_URL", "http://127.0.0.1:12319"),
}

MODEL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
TRAINED_MODEL_DIR = str(MODEL_STORAGE_ROOT)
