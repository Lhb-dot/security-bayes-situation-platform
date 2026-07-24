import pandas as pd

# 路径不要改
file_path = r"./data/nf_unsw/KDDTrain+_20Percent0503"
output_csv = r"./data/nf_unsw/sample_demo.csv"

# ========== 核心修复：只截取@data后面的真实数据行 ==========
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 找到@data标记，只取后面内容
start_index = 0
for idx, line in enumerate(lines):
    if line.strip().upper() == "@DATA":
        start_index = idx + 1
        break

data_lines = lines[start_index:]

# 写入临时内存文本，再交给pandas解析
from io import StringIO
data_str = "".join(data_lines)
df = pd.read_csv(StringIO(data_str), header=None, sep=",")

# 提取三列特征，和之前规则保持一致
df_clean = pd.DataFrame()
df_clean["flowLength"] = df[4]    # src_bytes
df_clean["duration"] = df[0]      # duration
df_clean["accessFreq"] = df[5]    # dst_bytes

# 三分类风险等级映射（推荐）
def map_risk_by_row(row_data):
    label = row_data.iloc[-1].strip()
    protocol = row_data[1].strip()

    if label == "normal":
        return "低风险"
    else:
        if protocol in ["tcp", "udp"]:
            return "高风险"
        elif protocol == "icmp":
            return "中风险"
        else:
            return "中风险"

df_clean["risk_level"] = df.apply(map_risk_by_row, axis=1)

# 导出最终可用csv
df_clean.to_csv(output_csv, index=False, encoding="utf-8-sig")

print("✅ ARFF文件清洗成功，已生成后端训练用sample_demo.csv")
print("风险分布统计：")
print(df_clean["risk_level"].value_counts())