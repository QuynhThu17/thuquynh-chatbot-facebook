# Hướng dẫn cài đặt RAGFlow Parser Integration

## 📦 Cài đặt Dependencies

### Bước 1: Kích hoạt virtual environment

```powershell
cd D:\projects\python\mekongai-social
.\.venv\Scripts\Activate.ps1
```

### Bước 2: Cài đặt RAGFlow dependencies

```powershell
pip install pdfplumber>=0.10.0
pip install xgboost>=2.0.0
pip install trio>=0.23.0
pip install huggingface-hub>=0.20.0
```

Hoặc cài tất cả cùng lúc:

```powershell
pip install pdfplumber xgboost trio huggingface-hub
```

### Bước 3: Verify installation

```python
python -c "import pdfplumber; import xgboost; import trio; from huggingface_hub import snapshot_download; print('✅ All dependencies installed successfully')"
```

## 🚀 Sử dụng

### API Request với RAGFlow (mặc định)

```javascript
const formData = new FormData();
formData.append('file', pdfFile);
formData.append('name', 'My Document');
formData.append('parser_engine', 'ragflow'); // Mặc định - tốt nhất

// Upload
const response = await fetch('/api/v1/knowledge/documents/upload', {
    method: 'POST',
    body: formData,
    headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
    }
});
```

### Fallback về Legacy Parser

```javascript
formData.append('parser_engine', 'legacy'); // Nếu cần dùng parser cũ
```

## 🔍 Kiểm tra

### Test RAGFlow Parser

```python
from controllers.rag.load_documents.processors.ragflow_parser import get_ragflow_parser

# Initialize parser
parser = get_ragflow_parser()

# Test với file
with open('test.pdf', 'rb') as f:
    file_data = f.read()
    sections, tables = await parser.parse(file_data, 'test.pdf', '.pdf')
    
print(f"Sections: {len(sections)}")
print(f"Tables: {len(tables)}")
```

## 📊 So sánh Performance

| Feature | Legacy Parser | RAGFlow Parser |
|---------|--------------|----------------|
| PDF Layout | Basic | ✅ Advanced |
| Table Detection | OK | ✅ Excellent |
| Structure Preservation | No | ✅ Yes |
| Multi-column | No | ✅ Yes |
| Processing Speed | Fast | Medium |
| Quality | Good | ✅ Excellent |

## ⚠️ Troubleshooting

### 1. Import Error: xgboost not found

```powershell
pip install xgboost
```

### 2. pdfplumber error

```powershell
pip install --upgrade pdfplumber
```

### 3. RAGFlow parsing failed

Hệ thống sẽ tự động fallback về legacy parser. Check logs:

```python
# Trong log sẽ thấy:
# "RAGFlow parsing failed, falling back to legacy"
```

### 4. Force legacy parser

Nếu muốn dùng legacy parser:

```javascript
formData.append('parser_engine', 'legacy');
```

## 📝 Notes

- RAGFlow parser được set làm **mặc định** cho quality tốt nhất
- System tự động fallback về legacy nếu RAGFlow fail
- Không break backward compatibility
- Có thể switch parser engine bất cứ lúc nào

## 🎯 Best Practices

1. **Upload documents phức tạp**: Dùng RAGFlow (mặc định)
2. **Upload nhanh, simple text**: Có thể dùng legacy
3. **Documents có nhiều tables**: RAGFlow tốt hơn nhiều
4. **Multi-column PDFs**: RAGFlow xử lý tốt hơn

## 🔗 References

- [RAGFlow GitHub](https://github.com/infiniflow/ragflow)
- [pdfplumber Documentation](https://github.com/jsvine/pdfplumber)
- [XGBoost](https://xgboost.readthedocs.io/)
