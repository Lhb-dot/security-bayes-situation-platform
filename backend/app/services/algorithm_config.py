"""Runtime configuration shared by Java algorithm clients."""

import os

from app.paths import MODEL_STORAGE_ROOT


PMWNB_SERVICE_URL = os.getenv("PMWNB_SERVICE_URL", "http://127.0.0.1:12313")
PREDICT_SERVICE_URL = os.getenv("PREDICT_SERVICE_URL", "http://127.0.0.1:12314")
TRAIN_TIMEOUT = int(os.getenv("NB_TRAIN_TIMEOUT", "600"))
PREDICT_TIMEOUT = int(os.getenv("NB_PREDICT_TIMEOUT", "60"))
# 5 个 NB 算法共用同一个服务进程：jar 字节完全相同，算法由请求体的 algorithm_code 指定。
# 单算法独立部署时可用 <算法名>_SERVICE_URL 覆盖其中一路。
NB_ALGORITHM_SERVICE_URL = os.getenv("NB_ALGORITHM_SERVICE_URL", "http://127.0.0.1:12315")
ALGORITHM_SERVICE_URLS = {
    code: os.getenv(f"{code}_SERVICE_URL", NB_ALGORITHM_SERVICE_URL)
    for code in ("A2WNB", "CAVWNB", "EMAWNB", "MAWNB", "DIWNB")
}

MODEL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
TRAINED_MODEL_DIR = str(MODEL_STORAGE_ROOT)
