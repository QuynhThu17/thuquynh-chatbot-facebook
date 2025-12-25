# Kế Hoạch Refactor Backend thuquynh-chatbot-facebook

## Mục Tiêu
- Chuyển dự án từ “AI-coded vibe” sang kiến trúc chuẩn, dễ bảo trì, an toàn, hiệu năng cao.
- Chuẩn hóa asyncio, PEP 8, clean code; loại bỏ I/O sync trong async; chuẩn hóa DI, cấu hình, bảo mật, logging, test.
- Mỗi sprint có phạm vi, công việc, tiêu chí chấp nhận, rủi ro, rollback, ước lượng thời gian, và phụ thuộc rõ ràng.

## Tiêu Chuẩn Max-Hóa
- Hiệu năng
  - Toàn bộ I/O ngoài tiến hành async (`httpx.AsyncClient`, `aiosmtplib`) hoặc offload `await asyncio.to_thread(...)` nếu thư viện không có async.
  - Timeout, retry/backoff có giới hạn; tránh block event loop; hạn chế deadlock/cancel không kiểm soát.
  - Tránh N+1 queries; dùng `asyncio.gather` cho truy vấn độc lập; đảm bảo index đầy đủ cho truy vấn lớn.
  - Hạn chế tải nặng lúc import; lazy-init cho các mô-đun nặng (LLM, transformers).
- Bảo trì
  - Router mỏng, tách `schemas` (Pydantic) + `services` + `repositories` (manager) + `utils` rõ ràng.
  - Không để business logic nặng trong router; tránh file vượt quá 400–600 dòng.
  - Tên biến/hàm/field thống nhất (`created_at`, `updated_at`), snake_case, module hóa hợp lý.
  - Loại bỏ global singletons nếu có thể; dùng DI qua `app.state`.
- Bảo mật
  - Không hardcode secrets; tất cả secrets từ env (hoặc secrets store). Không có fallback insecure.
  - JWT/refresh tokens quản lý an toàn; CORS chuẩn; input validation đầy đủ; rate limiting thực tế.
  - TLS verify cho HTTP outbound; hạn chế SSRF; kiểm soát payload kích thước; kiểm tra chữ ký webhook.
- Độ tin cậy
  - Xử lý lỗi có phân loại; idempotency cho endpoint cần thiết; đồng bộ hoá thời gian (UTC aware).
  - Test đơn vị, tích hợp, e2e cho các luồng quan trọng; coverage ≥ 70% sau sprint chất lượng.
- Khả quan sát
  - Logging có cấu trúc (JSON hoặc key-value); gắn request-id/correlation-id; metrics cơ bản (error rates, latency, throughput).
  - Audit logs cho hành động quan trọng (auth, thanh toán, cấu hình hệ thống).
- Triển khai/CI
  - Pipeline lint (`ruff`), format (`black`, `isort`), typecheck (`mypy` khi phù hợp), tests (`pytest`); pre-commit cấu hình đầy đủ.
  - Docker/compose cập nhật theo chuẩn; không để credential trong compose; dùng env an toàn.

---

## Sprint 0 — Baseline & Setup (1–2 ngày)

### Phạm Vi
- Chuẩn hóa cấu hình, loại bỏ secrets hardcode; thiết lập cơ bản cho lint/test/CI; chuẩn DI để thay thế singleton factory.

### Công Việc Cụ Thể
- Cấu hình & secrets
  - Xóa default MongoDB URI có credential: `controllers/databases/mongodb/mongodb.py:34` → đọc từ `MONGODB_CONNECTION` qua env, không có fallback nguy hiểm.
  - Xóa SMTP test hardcode: `configs/constant.py:114–115` → đọc `SMTP_USER`, `SMTP_PASSWORD` từ env, không có giá trị default gán sẵn.
  - CORS: thu gọn danh sách origin, đọc từ `FRONTEND_URL` và allow list rõ ràng. Sửa `app.py:118–135`.
- Thiết lập Settings hợp nhất
  - Tạo lớp `Settings` (ví dụ `core/settings.py`) dùng `pydantic-settings` để gom tất cả biến môi trường (JWT, PayOS, AWS, Facebook, Qdrant, SMTP, Mongo, CORS).
  - Xóa các fallback secrets trong `configs/constant.py` sau khi chuyển sang `Settings`.
- Dependency Injection cho factory
  - Trong `app.py:35–86`, lưu `MongoDBManagementFactory` vào `app.state.factory` sau khi connect.
  - Viết `get_management_factory(request: Request)` trả về `request.app.state.factory` thay vì global. Sửa usage tại các router, ví dụ `api/v1/auth/api_authentication.py:116–127`.
- Chất lượng cơ bản
  - Thêm `ruff`, `black`, `isort`, `pytest` vào dev dependencies; cấu hình `pyproject.toml`.
  - Thiết lập `pre-commit` hook chạy `ruff`, `black`, `isort` trước commit.

### Tiêu Chí Chấp Nhận
- Không còn secrets hardcode trong code; chạy app với env đầy đủ.
- `get_management_factory` lấy từ `app.state` ở mọi router chính.
- Lint/format chạy sạch (`ruff`, `black`, `isort`); cấu hình pre-commit hoạt động.

### Rủi Ro & Rollback
- Nếu DI qua `app.state` gây lỗi không khởi tạo: tạm thời giữ `get_mongodb_factory()` fallback, nhưng ghi log cảnh báo; rollback bằng cách đổi lại dependency trong các router điểm nóng trước khi tái áp dụng.

### Phụ Thuộc
- Môi trường `.env` đầy đủ; thiết lập secrets cho SMTP, Mongo, AWS, Facebook, PayOS.

---

## Sprint 1 — Async I/O Correctness (2–3 ngày)

### Phạm Vi
- Chuyển toàn bộ I/O sync (HTTP, SMTP, S3) sang async hoặc offload đúng cách; thêm timeout/backoff; không block event loop.

### Công Việc Cụ Thể
- Facebook Connect (HTTP)
  - `controllers/socials/facebook/facebook_connect.py:21`: đổi `requests.get` sang `httpx.AsyncClient.get` với `timeout=30s`, `follow_redirects=False`, `verify=True`.
  - Viết helper `async_http_get(url, params, headers)` chuẩn hoá; dùng lại ở các nơi cần (avatar, pages).
- Facebook Send Messenger
  - `controllers/socials/facebook/facebook_send_messenger.py`: 
    - Biến `send_typing_action`, `send_text_message`, `send_images` thành async (`httpx.AsyncClient.post`), thêm `timeout`, `raise_for_status` xử lý lỗi.
    - Sửa `async def send_facebook_messenger(...)` để gọi trực tiếp `await send_*` thay vì `asyncio.to_thread` (không cần nếu HTTP async).
  - Router `api/v1/socials/api_social_media.py:766–823`: đảm bảo đường gửi message dùng các hàm async mới.
- Email Service
  - `controllers/ultils/email_service.py:75`: thay `smtplib` bằng `aiosmtplib`. Nếu không thể, bọc toàn bộ gửi bằng `await asyncio.to_thread(...)` và thêm timeout.
- S3 Service
  - `controllers/rag/load_documents/storage/s3_service.py`: xác nhận mọi `put_object`, `delete_object`, `head_object` gọi qua `await asyncio.to_thread(...)` là chấp nhận được, bổ sung timeout ở layer gọi (nếu boto3 không hỗ trợ).
- Timeouts & Retries
  - Chuẩn timeout mặc định: 10–30s; retry max 3 lần với backoff 0.5–2s cho lỗi transient (5xx, network).

### Tiêu Chí Chấp Nhận
- Không còn gọi sync HTTP (`requests`) trong hàm async. Kiểm tra các vị trí: 
  - `facebook_connect.py:21`
  - `facebook_send_messenger.py:...` tất cả post/get.
- Email gửi không block event loop (đã async hoặc to_thread).
- Đường gửi tin nhắn Facebook chạy ổn định, có timeout và xử lý lỗi rõ ràng.

### Rủi Ro & Rollback
- Nếu thư viện async không sẵn: fallback to `asyncio.to_thread` tạm thời. Rollback bằng cách giữ phiên bản sync, nhưng cảnh báo và kế hoạch chuyển đổi dần.

### Phụ Thuộc
- `httpx`, `aiosmtplib` thêm vào dependencies dev/prod; cấu hình SMTP/TLS đúng.

---

## Sprint 2 — Kiến Trúc Modules (3–5 ngày)

### Phạm Vi
- Tách router khổng lồ thành modules mỏng; đưa nghiệp vụ vào services; schemas riêng; DI hợp lệ; chuẩn hóa timestamps.

### Công Việc Cụ Thể
- Tách Router theo feature nhỏ
  - `api/v1/auth/api_authentication.py` (~979 dòng) tách thành:
    - `auth/login.py` (đăng nhập), `auth/register.py` (đăng ký), `auth/verification.py` (email verify), `auth/password.py` (forgot/reset/change), `auth/tokens.py` (refresh/logout).
  - `api/v1/bots/api_bot_management.py` (~1811 dòng): tách theo `identities`, `procedures`, `bots`.
  - `api/v1/system/api_system_management.py` (~1547 dòng): tách `notifications`, `settings`, `api_keys`, `sessions`, `audit_logs`, `help`.
  - `api/v1/business/api_business_managerment.py` (~1992 dòng): tách `companies`, `products`, `warehouses`, `orders`, `shipments`.
- Schemas
  - Tạo `schemas/` cho tất cả request/response (Pydantic v2), router import từ schemas thay vì khai báo inline. Ví dụ các model hiện ở `api/v1/auth/api_authentication.py:59–115` chuyển sang `schemas/auth.py`.
- Services
  - Viết `services/auth_service.py` (mở rộng từ `controllers/auth/auth_service.py`) để chứa logic đăng ký, xác thực, token, email, rate-limit orchestration; router chỉ gọi service.
  - Viết `services/socials/facebook_service.py` cho connect/send/warm caches; tách khỏi router.
  - Viết `services/business_service.py`, `services/crm_service.py` để gom validate và thao tác nghiệp vụ.
- Repositories
  - Tiếp tục dùng `controllers/data/managements/*` làm repository layer. Chuẩn hóa interface và không để logic nghiệp vụ “dài” trong manager.
- Timestamps & Datetime
  - `controllers/data/managements/base_manager.py:49–53`: đổi `create_at` → `created_at`, `update_at` → `updated_at`. Lưu UTC aware; convert ở presentation nếu cần.
  - Rà soát toàn bộ nơi dùng `get_vietnam_now_naive()` để dùng `now_utc()` khi lưu DB, và chuyển timezone ở response nếu bắt buộc hiển thị.
- DI & App State
  - Đảm bảo mọi `Depends(get_management_factory)` sử dụng app.state (Sprint 0 đã sửa), cập nhật các router đã tách.

### Tiêu Chí Chấp Nhận
- Mọi router ≤ 300–600 dòng; không chứa business logic nặng.
- Schemas nằm trong `schemas/`, services điều phối; manager/repo chỉ thực thi CRUD & truy vấn.
- Timestamps chuẩn hoá, không còn `create_at`/`update_at`.

### Rủi Ro & Rollback
- Rủi ro đứt phụ thuộc import: tiến hành refactor theo module nhỏ, chạy lint/test sau mỗi nhóm; rollback bằng cách giữ module cũ song song cho đến khi thay thế xong.

### Phụ Thuộc
- Tài liệu domain để định nghĩa boundary rõ; tham chiếu các manager sẵn có (`controllers/data/managements/*`).

---

## Sprint 3 — Security Hardening (2–3 ngày)

### Phạm Vi
- Siết chặt bảo mật: CORS, JWT, rate limit, webhook validation, secrets, TLS, input validation.

### Công Việc Cụ Thể
- Secrets & Env
  - Đảm bảo tất cả khóa/URL từ env; không còn fallback insecure. Kiểm tra toàn bộ `configs/constant.py` các trường `SECRET_KEY`, `JWT_REFRESH_KEY`, `PAYOS_*`, `AWS_*`, `FACEBOOK_*`.
- JWT & Refresh
  - `controllers/auth/auth_service.py`: xác thực token `verify_token` có `aud`/`iss` chuẩn (nếu áp dụng), kiểm tra thời gian hợp lệ.
  - Xóa refresh token khi logout: xác nhận `api/v1/auth/api_authentication.py:424–438` xử lý đầy đủ và trả về mã đúng.
- CORS
  - `app.py:118–135`: chỉ allow origin từ env list; bỏ `allow_origin_regex` nếu không cần; không để dải IP tùy ý.
- Rate Limit
  - `controllers/data/managements/rate_limit_management.py:16–133`: thêm bucket theo IP/email/user; xem xét Redis (tùy hạ tầng) để thực hiện rate limit thực tế.
- Webhook Validation
  - `api/v1/socials/api_social_media.py` phần webhook: kiểm tra chữ ký HMAC (Facebook) với secret, `verify=True` cho HTTP inbound nếu reverse-proxy terminate TLS.
- Input Validation
  - Rà tất cả endpoints có upload, large payload; giới hạn kích thước `MAX_FILE_SIZE` (`configs/constant.py`), reject quá size.
  - Sanitize nội dung text nếu đưa ra HTML (`fastapi.responses.HTMLResponse`) như reset password page.

### Tiêu Chí Chấp Nhận
- Secrets/keys chỉ từ env; không còn hardcode.
- CORS còn đúng danh sách; JWT kiểm tra chuẩn; webhook validate chữ ký.
- Rate limiting hoạt động, trả mã 429 với thông điệp đúng; input validation đầy đủ.

### Rủi Ro & Rollback
- Khóa thiếu trong env gây lỗi start: rollback bằng cách thêm giá trị tạm thời trong `.env`, nhưng không commit.

### Phụ Thuộc
- Hỗ trợ Redis (nếu dùng) cho rate limit; proxy/TLS cấu hình đúng.

---

## Sprint 4 — Domain & Data Layer Optimizations (3–4 ngày)

### Phạm Vi
- Tối ưu logic domain lớn (bots, CRM, business, knowledge); cải thiện truy vấn, index, caching, concurrency.

### Công Việc Cụ Thể
- Bots/Facebook
  - `bot/bot_facebook_messenger.py`: xác nhận buffer/concurrency; đảm bảo không memory leak; cleanup hợp lý; metrics số lượng buffer.
  - `get_bot_info_from_page_id`/`get_bot_info_from_bot_id`: tối ưu truy vấn manager, thêm index theo nhu cầu; kiểm tra mapping `fb_page_id` với `social_account_id` (`lines ~560–726`). 
- Knowledge/RAG
  - Lazy load document content; chỉ fetch IDs ở meta; tải nội dung khi cần. Tối ưu embedding calls qua batch.
  - Giới hạn kích thước file ở `MAX_FILE_SIZE`; validate loại file (`api/v1/knowledge/rag_api_service.py:323–331` đã có danh sách).
- Business/CRM
  - `api/v1/business/api_business_managerment.py`: tách endpoint nặng; tối ưu các tổng hợp, dùng `count_documents` thay vì `find_many` với limit khi phù hợp.
- Indexes
  - Rà `controllers/databases/mongodb/ensure_indexes.py`: bổ sung index theo trường hay dùng; đo `created vs existing` để tránh trùng.
- Caching ngắn hạn
  - `controllers/data/limit_service.py`: đã có cache TTL 60s; mở rộng cho các lookups tần suất cao (page tokens, user settings) với invalidation rõ ràng.

### Tiêu Chí Chấp Nhận
- Các endpoint domain chính phản hồi ổn định, latency giảm; không còn N+1 rõ ràng.
- Index tạo đầy đủ; logs xác nhận “✅ Đã tạo” hoặc “ℹ️ đã tồn tại” (file `ensure_indexes.py`).

### Rủi Ro & Rollback
- Index sai gây lỗi: rollback bằng cách drop index vừa tạo và khôi phục cấu hình cũ; lưu script tạo/dỡ index rõ ràng.

### Phụ Thuộc
- Dữ liệu thực hoặc staging để đánh giá hiệu năng; quyền tạo index trên cluster Mongo.

---

## Sprint 5 — Testing & Quality Gate (2–3 ngày)

### Phạm Vi
- Bổ sung test đơn vị/tích hợp cho auth, socials, bots, business, knowledge; thiết lập ngưỡng chất lượng.

### Công Việc Cụ Thể
- Khung test
  - Thiết lập `pytest` với `pytest-asyncio`; fixture `httpx.AsyncClient` kết nối app; fake env.
  - Mock external I/O: httpx responses, SMTP, S3 (moto hoặc stub).
- Auth Flow
  - Test `/login`, `/register`, `/refresh`, `/logout`, `/send-verification-email`, `/verify-email`, `/reset-password`.
  - Kiểm tra rate limit trả 429, email verification hoạt động.
- Socials/Facebook
  - Test webhook receive, chữ ký; gửi tin nhắn (mock HTTP outbound).
- Bots
  - Test buffer gộp tin nhắn, cleanup sau 5s; đảm bảo không leak; validate meta.
- Business/CRM/Knowledge
  - Test CRUD chính và validate input/output; giới hạn `MAX_FILE_SIZE` enforced.
- Quality Gate
  - Coverage ≥ 70% (bắt đầu); `ruff`, `black`, `isort` sạch; optional `mypy` không báo lỗi nghiêm trọng.

### Tiêu Chí Chấp Nhận
- Test chạy pass, coverage ≥ 70%; pipeline lint/format chạy trước test.
- Các test tích hợp chính cho auth/socials/bots thực thi ổn định.

### Rủi Ro & Rollback
- Thiếu dữ liệu giả: tạo fixtures rõ ràng; rollback bằng cách cô lập test phạm vi nhỏ hơn.

### Phụ Thuộc
- Bộ dữ liệu test/staging; quyền tạo người dùng/đối tượng giả trong DB test.

---

## Sprint 6 — Observability & Performance (2–3 ngày)

### Phạm Vi
- Logging có cấu trúc, metrics căn bản; benchmark latency/throughput; load test nhẹ; tối ưu tiếp.

### Công Việc Cụ Thể
- Logging
  - Chuẩn hóa logger: bỏ emoji; dùng format JSON hoặc key-value; gắn `request_id` cho mỗi request (middleware).
  - Phân cấp lỗi: warn/error/critical; không log secrets/token.
- Metrics
  - Thêm counters cho request per endpoint, error rates, latency buckets; (tùy chọn) Prometheus FastAPI middleware.
- Benchmark & Load
  - Thiết lập script `locust` hoặc `k6` cho dòng auth và socials; đo p50/p95/p99 latency.
- Tối ưu thêm
  - Rà soát hotspots từ metrics; thêm cache TTL hợp lý; tăng concurrency cho đường async an toàn.

### Tiêu Chí Chấp Nhận
- Có middleware logging với request-id, log có cấu trúc ở các endpoint chính.
- Có số liệu cơ bản (counts, error rates, latency); báo cáo benchmark ngắn.

### Rủi Ro & Rollback
- Logging quá chi tiết ảnh hưởng hiệu năng: rollback bằng cách giảm level/fields; giữ balance.

### Phụ Thuộc
- Hệ thống thu thập logs/metrics (ELK/Prometheus) nếu dùng; quyền cấu hình.

---

## Phân Công & Lịch Dự Kiến
- Sprint 0: 1–2 ngày
- Sprint 1: 2–3 ngày
- Sprint 2: 3–5 ngày
- Sprint 3: 2–3 ngày
- Sprint 4: 3–4 ngày
- Sprint 5: 2–3 ngày
- Sprint 6: 2–3 ngày

Tổng: ~15–23 ngày tùy quy mô và kiểm thử.

---

## Checklist Tổng Hợp Theo Sprint
- Sprint 0
  - [ ] Bỏ hardcode: Mongo URI (`controllers/databases/mongodb/mongodb.py:34`), SMTP (`configs/constant.py:114–115`)
  - [ ] Tạo `Settings` hợp nhất; chuyển các đọc env sang `Settings`
  - [ ] DI qua `app.state.factory`; cập nhật `get_management_factory` trong router (`api/v1/auth/api_authentication.py:116–127`)
  - [ ] Thiết lập `ruff`, `black`, `isort`, `pytest`, `pre-commit`
- Sprint 1
  - [ ] `facebook_connect.py:21` dùng `httpx.AsyncClient`
  - [ ] `facebook_send_messenger.py` đổi tất cả post/get sang async; sửa router gọi
  - [ ] `email_service.py:75` dùng `aiosmtplib` hoặc `asyncio.to_thread`
  - [ ] Rà timeout/retry/backoff cho HTTP outbound
- Sprint 2
  - [ ] Tách router auth/bots/system/business thành modules mỏng
  - [ ] Tạo `schemas/` cho models; router import từ schemas
  - [ ] Dời nghiệp vụ vào `services/`
  - [ ] Chuẩn hóa `created_at`/`updated_at` trong `BaseManager` và DB
- Sprint 3
  - [ ] Secrets/keys chỉ từ env; không fallback insecure
  - [ ] JWT verify chuẩn; logout xóa refresh token
  - [ ] CORS thu gọn theo env
  - [ ] Rate limit thực tế; webhook signature kiểm tra
  - [ ] Input validation size/type đầy đủ
- Sprint 4
  - [ ] Tối ưu bots buffer; cleanup; metrics
  - [ ] Lazy load knowledge content; batch embeddings
  - [ ] Tối ưu business/CRM queries; bổ sung index cần thiết
  - [ ] Cache TTL ngắn hạn cho lookups thường dùng
- Sprint 5
  - [ ] Thiết lập `pytest-asyncio`, fixtures, mock I/O
  - [ ] Viết test cho auth/socials/bots/business/knowledge
  - [ ] Coverage ≥ 70%; lint/format sạch
- Sprint 6
  - [ ] Middleware logging với request-id; log cấu trúc
  - [ ] Metrics cơ bản; benchmark p50/p95/p99
  - [ ] Tối ưu hotspots theo metrics

---

## Tham Chiếu Mã (điểm sửa chính)
- `controllers/databases/mongodb/mongodb.py:34` — bỏ URI hardcode, đọc từ env qua `Settings`.
- `configs/constant.py:114–115` — bỏ SMTP test hardcode, yêu cầu env.
- `app.py:118–135` — CORS allow origins từ env, bỏ dải IP tĩnh.
- `api/v1/auth/api_authentication.py:116–127` — `get_management_factory` lấy từ `app.state`.
- `controllers/socials/facebook/facebook_connect.py:21` — đổi `requests.get` sang `httpx.AsyncClient.get` (async).
- `controllers/socials/facebook/facebook_send_messenger.py` — tất cả `requests.post` thành async `httpx`, các hàm public đều async.
- `controllers/ultils/email_service.py:75` — dùng `aiosmtplib` hoặc offload.
- `controllers/data/managements/base_manager.py:49–53` — `created_at`/`updated_at` UTC aware.
- `controllers/databases/mongodb/ensure_indexes.py` — rà bổ sung index theo patterns sử dụng.
- `controllers/data/limit_service.py:98–142` — giữ `asyncio.gather`; mở rộng cache TTL/layers nếu cần.

---

## Ghi Chú Cuối
- Mọi thay đổi liên quan bảo mật (secrets, JWT, CORS) phải được kiểm thử trên staging trước khi áp dụng sản xuất.
- Tránh commit secrets hoặc `.env`; sử dụng vault/secret manager khi có.

---

## Bổ Sung Định Hướng OOP

### Quan Điểm
- Nên áp dụng OOP mạnh hơn cho dự án hiện tại vì đã có sẵn nền tảng lớp `MongoDBManager`, `BaseManager` và các `*ManagementFactory`. Việc tăng cường OOP sẽ:
  - Chuẩn hóa ranh giới domain (services/repositories/entities), giảm trộn logic trong router.
  - Nâng cao khả năng test/mocking, tái sử dụng, mở rộng tính năng.
  - Kiểm soát vòng đời và phụ thuộc qua DI rõ ràng.

### Kiến Trúc Lớp Đề Xuất
- Entities (Domain Models)
  - Sử dụng Pydantic v2 cho request/response và domain models không persistence logic.
  - Chuẩn hóa `User`, `Bot`, `Identity`, `Procedure`, `FacebookPage`, `Company`, `Product`, `Warehouse`, `Order`, `Document`, `KnowledgeChunk`…
  - Áp dụng Value Objects cho ID (`UserId`, `BotId` dạng wrapper str) nếu cần tính an toàn.
- Repositories
  - `RepositoryBase`: interface CRUD async chung (get_by_id, get_all, create, update_by_id, delete_by_id, count, search).
  - Mỗi repository triển khai từ `BaseManager` hiện có, đóng gói truy vấn cụ thể.
  - Đảm bảo không lẫn business logic nặng trong repository.
- Services (Business Layer)
  - `AuthService` mở rộng: đăng ký, xác thực, token, email, verification orchestration.
  - `SocialService` (FacebookAdapter bên dưới): connect, send, webhook handling, token caching.
  - `BotService`: quản lý buffer, xử lý message, điều phối tools.
  - `BusinessService`: quản lý companies/products/warehouses/orders, validate/compute.
  - `CRMService`, `KnowledgeService`, `SystemService` tương ứng module.
- Adapters & Strategies
  - `FacebookAdapter`: lớp adapter HTTP async cho Graph API (typing, text, images, connect flow). 
  - Strategy pattern cho gửi message đa nền tảng (Facebook, Instagram, Zalo) với interface `MessengerStrategy`.
  - Adapter cho SMTP (`EmailAdapter`) dùng `aiosmtplib` hoặc offload.
  - Adapter S3 (`S3Adapter`) bọc thao tác boto3 dưới async interface.
- Unit of Work (tùy chọn theo nhu cầu transaction)
  - `MongoUnitOfWork`: bắt đầu session, `commit()`, `rollback()` cho trường hợp cần atomicity (yêu cầu replica set).
- DI Container
  - Định nghĩa `AppContainer` hoặc sử dụng `app.state` làm nơi cung cấp services/repositories/adapters đã khởi tạo.
  - Router chỉ nhận interface qua `Depends(...)`—không instantiate trực tiếp.

### Quy Tắc Thiết Kế
- SOLID: tách interface/repository/service rõ ràng; đơn nhiệm; mở rộng dễ; phụ thuộc vào abstraction.
- Async-first: tất cả phương thức I/O của repository/service là `async def`.
- Không để logic nghiệp vụ trong router hoặc repository; repository chỉ truy vấn; service điều phối.
- Tên lớp/method rõ ràng, snake_case cho hàm/biến, PascalCase cho lớp.

---

## Cập Nhật Chi Tiết Theo Sprint (OOP)

### Sprint 0 — Baseline & Setup (OOP)
- Tạo `core/settings.py` với `Settings` bằng `pydantic-settings` để cung cấp cấu hình cho services/adapters.
- Xác lập DI qua `app.state` cho:
  - `MongoDBManager`
  - `MongoDBManagementFactory` (repositories)
  - Stubs cho `AuthService`, `SocialService`, `EmailAdapter`, `S3Adapter` để router có thể Inject ngay cả trước khi hoàn thiện.
- Viết tiêu chuẩn naming/class & async coding guideline để áp dụng thống nhất.

### Sprint 1 — Async I/O Correctness (OOP)
- Tạo `FacebookAdapter` (HTTP async) thay thế các hàm procedural trong `facebook_send_messenger.py` và `facebook_connect.py`:
  - Phương thức: `send_typing_action()`, `send_text()`, `send_images()`, `exchange_token()`.
  - Cấu hình qua `Settings` (client_id, client_secret, redirect_uri).
- Tạo `EmailAdapter` dùng `aiosmtplib` với `send_notification_email()` và `send_support_notification_email()` async.
- Sửa `SocialService` và `AuthService` để dùng adapters thay vì gọi trực tiếp thư viện bên dưới.

### Sprint 2 — Kiến Trúc Modules (OOP)
- Entities
  - Tạo `schemas/` và `domain/entities/` phân tách:
    - `schemas/*` cho DTO (request/response) thuần Pydantic.
    - `domain/entities/*` cho domain models (nếu cần các phương thức logic nhỏ).
- Repositories
  - Viết `RepositoryBase` (interface) và ánh xạ các `*Manager` hiện có thành repository cụ thể: `UserRepository`, `BotRepository`, `FacebookPageRepository`, `ProductRepository`, `OrderRepository`…
- Services
  - Viết `AuthService`, `SocialService`, `BotService`, `BusinessService`, `CRMService`, `KnowledgeService`, `SystemService` dưới dạng lớp, chỉ nhận repository/adapters qua constructor.
  - Router chỉ gọi methods của service, không truy xuất repository trực tiếp.
- Unit of Work (tùy chọn)
  - Xây dựng `MongoUnitOfWork` cho các thao tác cần transaction (ví dụ tạo order kèm ghi log usage, khi hạ tầng hỗ trợ transaction).

### Sprint 3 — Security Hardening (OOP)
- `AuthService` bổ sung kiểm tra JWT (`aud`, `iss` tùy chính sách), rotate/blacklist refresh khi cần.
- `SocialService` thực hiện webhook signature kiểm tra trong adapter (HMAC), expose method `verify_signature()`.
- `RateLimitService` định nghĩa interface, triển khai Redis-backed khi có hạ tầng; tách khỏi repository layer.
- `Settings` quản lý tất cả secrets; adapters/services truy cập qua `Settings`/DI.

### Sprint 4 — Domain & Data Layer Optimizations (OOP)
- `BotService` kiểm soát buffer bằng lớp `MessageBuffer` đóng gói state/lock; thêm metrics hooks.
- `KnowledgeService` lazy load và batching logic thành methods rõ ràng; adapter hoá các tích hợp embedding nếu cần.
- `BusinessService` gom các validate/compute (giá, tồn kho) thành phương thức; repositories chỉ truy vấn.
- Rà `ensure_indexes` và bổ sung index thông qua repository metadata/config nếu cần.

### Sprint 5 — Testing & Quality Gate (OOP)
- Test theo lớp:
  - Unit tests cho services với repository/adapters mocked.
  - Integration tests dùng repository thật (motor) với DB test.
  - Contract tests cho adapters (Facebook, Email, S3) với HTTP/SMTP mock.
- Mục tiêu coverage ≥ 70% cho services tầng nghiệp vụ.

### Sprint 6 — Observability & Performance (OOP)
- Middleware logging gắn `request_id`, services/adapters log có cấu trúc.
- Metrics theo lớp: số lượng call adapters, lỗi theo category, latency phân bổ theo method.
- Benchmark dựa vào endpoints gọi services tương ứng; tối ưu theo hotspots.

---

## Sơ Đồ Trách Nhiệm (Rút gọn)
- Router: nhận/validate input (schemas), gọi service, trả response (schemas).
- Service: điều phối nghiệp vụ, gọi repositories/adapters, xử lý lỗi/transaction.
- Repository: CRUD/truy vấn thuần cho một entity/collection.
- Adapter: giao tiếp ngoài (Facebook, SMTP, S3) async; chịu trách nhiệm timeout/retry/backoff.
- Settings/DI: cung cấp cấu hình và lifecycle đối tượng (singleton theo app).
