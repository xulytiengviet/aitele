# Publish `ai-telecom` lên PyPI

Hướng dẫn đẩy package Python SDK lên [PyPI](https://pypi.org/project/ai-telecom/).

Package: **`ai-telecom`** (import: `ai_telecom`)  
Thư mục: `sdk/python/`

---

## Điều kiện trước khi publish

1. Tài khoản [PyPI](https://pypi.org/) (và nên có [TestPyPI](https://test.pypi.org/) để thử).
2. **API token** (khuyến nghị): PyPI → Account settings → API tokens  
   - Scope: toàn project hoặc chỉ project `ai-telecom`.  
   - Username khi upload: `__token__`  
   - Password: token dạng `pypi-...`
3. Version **chưa từng publish** — PyPI không cho ghi đè cùng số version.
4. Đồng bộ version ở **hai chỗ** (phải giống nhau):

```text
sdk/python/pyproject.toml          → version = "x.y.z"
sdk/python/ai_telecom/_version.py  → __version__ = "x.y.z"
```

5. Tests xanh:

```bash
cd sdk/python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

---

## 1. Bump version

Ví dụ lên `1.1.1`:

- Sửa `pyproject.toml` → `version = "1.1.1"`
- Sửa `ai_telecom/_version.py` → `__version__ = "1.1.1"`
- Cập nhật Release Notes / changelog nếu có

Quy ước gợi ý:

| Đổi | Version |
|-----|---------|
| Bugfix, docs SDK | patch (`1.1.0` → `1.1.1`) |
| API/SDK thêm field, method (tương thích ngược) | minor (`1.1.0` → `1.2.0`) |
| Phá vỡ import / bỏ method | major (`1.x` → `2.0.0`) |

---

## 2. Build

```bash
cd sdk/python
source .venv/bin/activate   # nếu chưa bật

pip install -U build twine

# Xoá bản build cũ
rm -rf dist/ build/ *.egg-info

python -m build
```

Kết quả trong `dist/`:

```text
ai_telecom-x.y.z.tar.gz
ai_telecom-x.y.z-py3-none-any.whl
```

Kiểm tra metadata / không lộ secret:

```bash
twine check dist/*
```

---

## 3. (Khuyến nghị) Thử trên TestPyPI

```bash
twine upload --repository testpypi dist/*
```

Cài thử từ TestPyPI (môi trường sạch):

```bash
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ai-telecom==x.y.z
python -c "import ai_telecom; print(ai_telecom.__version__)"
```

`--extra-index-url` để pip vẫn lấy `httpx` / `pydantic` từ PyPI thật.

---

## 4. Publish lên PyPI thật

```bash
cd sdk/python
twine upload dist/*
```

Khi hỏi:

- Username: `__token__`
- Password: `pypi-...` (token)

Hoặc dùng file `~/.pypirc` (không commit file này):

```ini
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TEST_TOKEN_HERE
```

Sau khi upload:

```bash
pip install -U ai-telecom
python -c "import ai_telecom; print(ai_telecom.__version__)"
```

Trang package: https://pypi.org/project/ai-telecom/

---

## 5. Sau khi publish

- [ ] Tag git (tuỳ chọn): `git tag sdk-v1.1.0 && git push --tags`
- [ ] Cập nhật `sdk/test-sdk/requirements.txt` nếu muốn pin bản mới
- [ ] Ghi Release Notes trong Developer docs (`/developers/docs/release-notes`)

---

## Lỗi thường gặp

| Lỗi | Cách xử lý |
|-----|------------|
| `File already exists` | Version đã có trên PyPI — bump số mới, build lại |
| `InvalidDistribution` / `twine check` fail | README/metadata; xem output `twine check` |
| Package name taken / forbidden | Tên `ai-telecom` đã claim bởi account PyPI của team — login đúng owner |
| Import được nhưng version cũ | `pip install -U ai-telecom==x.y.z` hoặc xoá cache wheel |

---

## Tóm tắt một lần (PyPI production)

```bash
cd sdk/python
# 1) Sửa version ở pyproject.toml + ai_telecom/_version.py
source .venv/bin/activate
pip install -U build twine
rm -rf dist/ build/
python -m build
twine check dist/*
twine upload dist/*
```
