import sys
sys.path.insert(0, 'backend')
from app.utils.arff_reader import read_arff

fields, rows = read_arff('data/geological/DIS_raw_data.arff', max_rows=3)

print('=== FIELD NAMES ===')
for i, f in enumerate(fields):
    print(f'{i}: {f["name"]} ({f["type"]}) samples={f["sample_values"]}')

print()
print('=== FIRST ROW ===')
for i, v in enumerate(rows[0]):
    print(f'  [{i}] = {repr(v)}')

print()
print('=== ENUM VALUES for Aspect (field 2) ===')
for v in fields[2]['enum_values']:
    print(f'  {repr(v)}')

print()
print('=== ENUM VALUES for Slope (field 3) ===')
for v in fields[3]['enum_values']:
    print(f'  {repr(v)}')