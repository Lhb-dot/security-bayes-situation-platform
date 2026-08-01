# pip install -r requirements.txt
lightrag-server &
# 等待10s
sleep 10
python -m app.main
