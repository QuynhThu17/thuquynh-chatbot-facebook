"""
Script để clean up và fix dashboard API file
- Xóa duplicate functions
- Apply context date range cho charts
"""

# Read file
with open('d:/projects/python/mekongai-social/api/v1/dashboard/api_dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find và xóa duplicate functions (giữ occurrence đầu tiên)
seen_funcs = set()
cleaned_lines = []
skip_until = -1

for i, line in enumerate(lines):
    if i < skip_until:
        continue
    
    # Check nếu là function definition
    if 'async def get_user_engagement_chart' in line or 'async def get_revenue_chart' in line:
        func_name = 'get_user_engagement_chart' if 'user_engagement' in line else 'get_revenue_chart'
        
        if func_name in seen_funcs:
            # Đây là duplicate - skip đến hàm tiếp theo
            print(f"Found duplicate {func_name} at line {i+1}, skipping...")
            # Find next async def
            for j in range(i+1, len(lines)):
                if j > i and ('async def ' in lines[j] or 'def ' in lines[j] and not lines[j].startswith(' ')):
                    skip_until = j
                    break
            continue
        else:
            seen_funcs.add(func_name)
    
    cleaned_lines.append(line)

# Write back
with open('d:/projects/python/mekongai-social/api/v1/dashboard/api_dashboard.py', 'w', encoding='utf-8') as f:
    f.writelines(cleaned_lines)

print(f"✅ Cleaned file: removed duplicates")
print(f"Original lines: {len(lines)}")
print(f"Cleaned lines: {len(cleaned_lines)}")
print(f"Removed: {len(lines) - len(cleaned_lines)} lines")
