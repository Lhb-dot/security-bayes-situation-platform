# pip install -r requirements.txt
lightrag-server &
# 等待10s
sleep 10
python main.py --output-dir output
