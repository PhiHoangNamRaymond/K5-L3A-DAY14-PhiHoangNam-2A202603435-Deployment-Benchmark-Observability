
## Part 1 — Localhost vs Production

### Exercise 1.1 — Các vấn đề trong bản develop

Dẫn chứng từ `01-localhost-vs-production/develop/app.py`:

1. Dòng 17–18: API key giả lập và URL database được ghi trực tiếp trong code. Với secret thật, việc chia sẻ hoặc commit code có thể làm lộ thông tin truy cập.
2. Dòng 34: API key được in ra log. Người đọc log có thể nhìn thấy secret.
3. Dòng 21–22: DEBUG và MAX_TOKENS được cấu hình cố định trong code, khó thay đổi giữa các môi trường.
4. Dòng 51: server chỉ bind localhost, không phù hợp khi cần nhận kết nối từ bên ngoài container.
5. Dòng 52: port cố định là 8000, không đọc biến PORT mà nền tảng cloud cung cấp.
6. Dòng 53: reload=True bật cơ chế theo dõi và nạp lại code, không phù hợp để chạy production.
7. Không có endpoint /health và /ready để hệ thống kiểm tra trạng thái ứng dụng.

### Exercise 1.2 — Chạy bản develop

Chạy trong `01-localhost-vs-production/develop`:

    python app.py

Kết quả thực tế:

| Request | HTTP |
|---|---|
| GET http://localhost:8000/ | 200 OK |
| POST http://localhost:8000/ask?question=Hello | 200 OK |
| GET http://localhost:8000/health | 404 Not Found |

Bản develop nhận question qua query parameter. Việc /ask trả 200 cho thấy endpoint xử lý được request, nhưng chưa chứng minh ứng dụng sẵn sàng cho production.

### Exercise 1.3 — Chạy và so sánh bản production

Chạy trong `01-localhost-vs-production/production`:

    ENVIRONMENT=development DEBUG=false PORT=8001 python app.py

Ban đầu cổng 8000 đang được sử dụng nên server không bind được. Tôi chuyển production sang cổng 8001 bằng biến môi trường PORT.

Kết quả thực tế:

| Request | HTTP | Nội dung |
|---|---|---|
| POST http://localhost:8001/ask với JSON {"question":"Hello"} | 200 OK | Có question, answer, model |
| GET http://localhost:8001/health | 200 OK | status=ok, có uptime, version, environment |
| GET http://localhost:8001/ready | 200 OK | {"ready":true} |

Câu trả lời /ask nhận được:

    {"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","model":"gpt-4o-mini"}

Ứng dụng sử dụng mock LLM; trường model không chứng minh có request đến nhà cung cấp LLM thật.

Bảng so sánh từ mã nguồn:

| Feature | Develop | Production | Ý nghĩa |
|---|---|---|---|
| Config | Nhiều giá trị cố định | config.py đọc os.getenv | Đổi cấu hình giữa các môi trường |
| Host | localhost | settings.host, mặc định 0.0.0.0 | Nhận kết nối qua mạng container |
| Port | Cố định 8000 | settings.port đọc PORT | Phù hợp cổng do cloud cấp |
| Reload | Luôn True | Theo settings.debug | Có thể tắt khi triển khai |
| Logging | print, có in key | Dùng logging, không in key trong luồng /ask | Hạn chế lộ secret, hỗ trợ vận hành |
| Health check | Không có | Có /health | Cung cấp trạng thái liveness |
| Readiness | Không có | Có /ready | Cho biết khả năng nhận request |
| Lifecycle | Không có phần cleanup riêng | Có lifespan startup/shutdown | Có chỗ khởi tạo và dọn tài nguyên |

Dẫn chứng một điểm đã sửa:
- Develop app.py dòng 52 đặt port=8000.
- Production config.py dòng 18 đọc PORT từ môi trường.
- Production app.py dòng 197 truyền settings.port cho uvicorn.
- Thực tế tôi đã chạy production trên cổng 8001.

Health check giúp nền tảng phát hiện ứng dụng không phản hồi. Graceful shutdown giúp hoàn thành request đang xử lý và đóng tài nguyên trước khi thoát. Trong Part 1, tôi mới đọc phần lifecycle; chưa kiểm thử graceful shutdown bằng SIGTERM.

## Part 2 — Docker Containerization

### Exercise 2.1 — Đọc Dockerfile cơ bản

1. Base image là `python:3.11`, cung cấp Python và môi trường hệ điều hành để chạy ứng dụng.
2. Working directory là `/app`, được đặt bằng `WORKDIR /app`. Các lệnh tiếp theo dùng thư mục này làm thư mục làm việc nếu không chỉ định đường dẫn khác.
3. COPY requirements.txt trước phần source giúp tận dụng Docker layer cache: khi chỉ sửa source mà không đổi requirements, bước cài dependencies có thể dùng lại cache.
4. CMD đặt lệnh hoặc tham số mặc định, có thể được thay thế bằng lệnh truyền sau tên image trong docker run. ENTRYPOINT xác định chương trình chính; với exec form, tham số sau tên image thường được nối vào chương trình đó. Có thể thay ENTRYPOINT bằng tùy chọn --entrypoint.

### Exercise 2.2 — Build và chạy bản develop

Build từ gốc repo:

    docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .

Chạy container:

    docker run -d --name k5-day14-basic -p 8003:8000 my-agent:develop

Kết quả thực tế:
- Container ở trạng thái Up.
- GET http://localhost:8003/health trả HTTP 200, body có status=ok và container=true.
- POST http://localhost:8003/ask?question=Hello trả HTTP 200 và câu trả lời mock.
- Cổng 8003 của máy được chuyển vào cổng 8000 trong container.

### Exercise 2.3 — Multi-stage build và so sánh kích thước

Build từ gốc repo:

    docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .

Chạy container:

    docker run -d --name k5-day14-advanced -p 8004:8000 -e ENVIRONMENT=production my-agent:advanced

Kết quả thực tế:
- Container đạt trạng thái healthy.
- GET http://localhost:8004/health trả HTTP 200.
- POST http://localhost:8004/ask với JSON {"question":"Hello"} trả HTTP 200.
- docker exec k5-day14-advanced whoami trả appuser.

Hai stage:
- Builder: dùng python:3.11-slim, cài gcc, libpq-dev và dependencies Python.
- Runtime: dùng python:3.11-slim, copy dependencies từ builder và source cần chạy, cấu hình user appuser và HEALTHCHECK.
- Image cuối nhỏ hơn nhờ dùng base slim và không mang các công cụ build từ builder sang runtime.

Số đo bằng docker image ls:

| Image | DISK USAGE | CONTENT SIZE |
|---|---:|---:|
| my-agent:develop | 1.67 GB | 426 MB |
| my-agent:advanced | 240 MB | 57.4 MB |

Số đo bằng docker image inspect với trường .Size:

| Image | Byte | MB, quy ước 1 MB = 1,000,000 byte |
|---|---:|---:|
| my-agent:develop | 426320000 | 426.320000 |
| my-agent:advanced | 57409231 | 57.409231 |

So sánh theo cùng trường .Size:

    (426320000 - 57409231) / 426320000 * 100 = 86.53%

Advanced giảm 86.53% theo phép đo này. Không trộn số DISK USAGE với CONTENT SIZE khi tính phần trăm.

### Exercise 2.4 — Docker Compose stack

Chạy trong 02-docker/production:

    touch .env.local
    docker compose -p k5-day14-docker up -d --build

Các service và địa chỉ nội bộ:
- nginx: nhận HTTP qua cổng 80 của máy.
- agent: FastAPI tại agent:8000, không publish trực tiếp ra host trong Compose.
- redis: Redis tại redis:6379.
- qdrant: vector database tại qdrant:6333.

Sơ đồ luồng request:

    Client
      |
      | HTTP localhost:80
      v
    Nginx
      |
      | HTTP agent:8000
      v
    FastAPI agent -> Mock LLM

Các dịch vụ phụ trợ trong cùng mạng Compose:

    Redis redis:6379       Qdrant qdrant:6333
           ^                       ^
           |                       |
           +-- agent được cấu hình URL --+

Các service phân giải tên nhau qua DNS nội bộ của mạng Compose. Agent được cấu hình REDIS_URL và QDRANT_URL, nhưng code Part 2 hiện chưa dùng các dịch vụ này để lưu session hoặc retrieval; luồng trả lời vẫn dùng mock LLM.

Compose chờ Redis và Qdrant healthy trước khi khởi động agent. Lần kiểm tra ps ban đầu, Redis và Qdrant healthy, agent đang health: starting và Nginx Up.

Kiểm tra thực tế qua Nginx:
- GET http://localhost/health trả HTTP 200, Server: nginx, body có status=ok và version=2.0.0.
- POST http://localhost/ask với JSON {"question":"Explain microservices"} trả HTTP 200, Server: nginx và câu trả lời mock.

Sự cố và cách xử lý:
- Lần đầu pull Redis gặp HTTP 429 từ Docker Hub.
- Tôi đăng nhập bằng docker login, sau đó tải image bằng:
  COMPOSE_PARALLEL_LIMIT=1 docker compose -p k5-day14-docker pull redis qdrant nginx
- Sau đó chạy lại Compose thành công.
- Cảnh báo version is obsolete không chặn stack khởi động.

## Part 3 — Cloud Deployment

### Exercise 3.1 — Railway
Nền tảng chính được chọn là Railway. Deploy chính agent Part 6 trong `06-lab-complete/`, kèm Redis riêng; không deploy app minh họa Part 3.

Code và kiểm tra local đã hoàn thành (PASS 12/12). Đăng nhập Railway CLI đang chờ chủ tài khoản xác thực thiết bị. Chưa có URL public đã được kiểm chứng tại thời điểm ghi mục này. Trạng thái thực tế và các lệnh kiểm tra nằm ở DEPLOYMENT.md.

### Exercise 3.2 — So sánh Railway và Render

| Nội dung | Railway | Render |
|---|---|---|
| File | railway.toml | render.yaml |
| Build | builder=DOCKERFILE, Dockerfile trong root service Part 6 | Blueprint với runtime=docker và rootDir=06-lab-complete |
| Health check | healthcheckPath=/health | healthCheckPath=/health |
| Port | CMD đọc PORT do nền tảng cấp | Cùng Docker CMD đọc PORT |
| Redis | Tạo service Redis, app dùng biến tham chiếu REDIS_URL | Blueprint khai báo keyvalue và fromService.connectionString |
| API key | Đặt trong Variables của service, không commit giá trị | generateValue: true, không ghi secret trong YAML |
| Dữ liệu deploy | railway up upload source từ thư mục Part 6 | Render Blueprint lấy source từ repository |

Hai cấu hình đều mô tả app dùng Docker và Redis. Cấu hình Render dùng plan free để tham khảo; chưa deploy Render, không khẳng định đã kiểm chứng runtime trên Render.

### Exercise 3.3 — Đọc pipeline Cloud Run
1. cloudbuild.yaml có bước cài dependencies/pytest và gọi pytest tests/ để kiểm tra trước build.
2. Bước build tạo image gcr.io/$PROJECT_ID/ai-agent với tag COMMIT_SHA và latest, rồi bước push đẩy các tag lên registry.
3. Bước deploy gọi gcloud run deploy tại asia-southeast1, cấu hình tài nguyên, giới hạn instance, environment và secret từ Secret Manager.
4. service.yaml mô tả service declarative: container image, port, concurrency 80, timeout 60 giây, min/max instance 1/10 và các probe. Bài này chỉ đọc pipeline, không deploy GCP.

Lưu ý khi dùng template thật: bước shell test chưa bật fail-fast, nên cần bảo đảm lỗi pytest làm build thất bại; không chỉ dựa vào dòng echo Tests passed.

## Part 4 — API Security

### Exercise 4.1 — API key authentication

Bản develop chạy trên cổng 8005 với API key mẫu được truyền qua biến AGENT_API_KEY.

API key được đọc từ header X-API-Key bằng APIKeyHeader. Hàm verify_api_key kiểm tra key và được gắn vào /ask qua Depends(verify_api_key).

Kết quả kiểm tra thực tế:

| Trường hợp | HTTP | Detail |
|---|---|---|
| Không gửi X-API-Key | 401 Unauthorized | Missing API key |
| Gửi key sai | 403 Forbidden | Invalid API key. |
| Gửi key đúng | 200 OK | Có question và answer |

Đổi key bằng cách cập nhật AGENT_API_KEY, khởi động lại ứng dụng và cập nhật key phía client.

Bản mẫu Part 4 trả 403 khi key sai. Riêng yêu cầu Part 6 quy định cả thiếu và sai key đều phải trả 401.

### Exercise 4.2 — JWT authentication

Server JWT chạy trên cổng 8006. GET /health trả 200 và security="JWT + RateLimit + CostGuard".

Luồng xác thực:
1. Client gửi tài khoản mẫu student / demo123 tới POST /auth/token.
2. Server kiểm tra tài khoản, tạo JWT ký bằng HS256.
3. JWT chứa sub, role, iat và exp; thời hạn trong code là 60 phút.
4. Client gửi Authorization: Bearer <token> khi gọi /ask.
5. Server kiểm tra chữ ký và hạn sử dụng rồi mới xử lý request.

Token được lưu vào biến shell TOKEN, không ghi giá trị token vào bài.

Trích kết quả curl -i khi thiếu JWT:

    HTTP/1.1 401 Unauthorized
    www-authenticate: Bearer

    {"detail":"Authentication required. Include: Authorization: Bearer <token>"}

Trích kết quả curl -i khi JWT hợp lệ:

    HTTP/1.1 200 OK

    {"question":"Explain JWT","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}

Lưu ý từ mã nguồn: trường budget_remaining_usd trong response /ask đang nhận usage.total_cost_usd, tức chi phí đã dùng, không phải ngân sách còn lại.

### Exercise 4.3 — Rate limiting

Thuật toán trong code là sliding window lưu timestamp của từng request:
- Mỗi user có một deque.
- Khi có request, loại bỏ timestamp ngoài cửa sổ 60 giây.
- Nếu đã đủ số request cho phép thì trả 429.
- Nếu còn lượt thì thêm timestamp mới.

Giới hạn theo role:
- User: 10 request / 60 giây.
- Admin: 100 request / 60 giây.
- Admin được chọn limiter có ngưỡng cao hơn, không được miễn hoàn toàn rate limit.

Kết quả thực tế với tài khoản student:
- Đã có một request /ask thành công trước vòng lặp.
- Trong vòng lặp 20 request: request 01–09 trả 200, request 10–20 trả 429.
- Tổng cộng 10 request được chấp nhận trong cửa sổ đang xét.

Trích output request sau vòng lặp:

    HTTP/1.1 429 Too Many Requests
    x-ratelimit-limit: 10
    x-ratelimit-remaining: 0
    retry-after: 35

    {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":35}}

Retry-After cho biết thời gian cần chờ theo cửa sổ tại thời điểm response đó, không phải thời gian cố định của mọi lần gọi.

State bản mẫu nằm trong RAM, không dùng chung giữa nhiều worker và mất khi restart. Part 6 cần lưu state trong Redis.

### Exercise 4.4 — Cost guard

Rate limit giới hạn tốc độ gọi API; cost guard giới hạn tổng chi phí. Một request có thể dùng nhiều token nên cần cả hai cơ chế.

Code mẫu:
- Budget mỗi user: 1 USD/ngày.
- Budget toàn hệ thống: 10 USD/ngày.
- Kiểm tra ngân sách trước khi gọi LLM.
- Sau khi gọi LLM, ghi nhận input/output token và cộng chi phí.
- Khi chi phí user đã đạt hoặc vượt budget: ném HTTPException 402.
- Khi chi phí toàn hệ thống đã đạt hoặc vượt budget: bản mẫu trả 503.

Phép thử trực tiếp bằng một đối tượng CostGuard riêng:
- daily_budget_usd = 0.0005.
- Input giả lập = 1000 token, output giả lập = 1000 token.
- Giá trong code: 0.00015 USD/1000 input token và 0.0006 USD/1000 output token.
- Chi phí tính được = 0.00075 USD.

Output thực tế:

    Trước khi ghi nhận usage: được phép gọi LLM
    Ngân sách mẫu: 0.0005 USD
    Chi phí từ token giả lập: 0.00075 USD
    HTTP: 402
    {"error": "Daily budget exceeded", "used_usd": 0.00075, "budget_usd": 0.0005, "resets_at": "midnight UTC"}

Đây là phép thử trực tiếp class CostGuard với token giả lập, không phải response HTTP từ server hay số đo LLM thật.

Giới hạn của cách kiểm tra hiện tại: request đang thực hiện vẫn có thể làm tổng chi phí vượt budget; lần kiểm tra tiếp theo mới bị chặn. Để bảo vệ chặt hơn cần dự trù hoặc giữ trước chi phí.

Thiết kế cho yêu cầu budget 10 USD/tháng bằng Redis:
- Dùng key theo user và tháng, ví dụ budget:<user_id>:<YYYY-MM>, thống nhất mốc thời gian UTC.
- Kiểm tra tổng đã dùng cộng chi phí dự kiến trước khi cho phép gọi.
- Thực hiện kiểm tra và giữ ngân sách bằng thao tác nguyên tử, ví dụ Redis Lua, để tránh nhiều request đồng thời cùng vượt qua kiểm tra.
- Sau khi gọi LLM, đối soát phần đã giữ với chi phí thực tế.
- Sang tháng dùng key mới; đặt TTL để dọn key cũ.

Phần Redis theo tháng ở trên là thiết kế giải thích, chưa được triển khai trong Part 4. Mã nguồn mẫu Part 4 chưa được sửa.

## Part 5 — Scaling & Reliability

### Exercise 5.1 — Health và readiness

Chạy bản develop trên cổng 8007:

    PORT=8007 python app.py

Kết quả thực tế:

GET /health:

    HTTP/1.1 200 OK
    {"status":"ok","uptime_seconds":51.1,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T10:50:26.360961+00:00","checks":{"memory":{"status":"ok","used_percent":17.3}}}

GET /ready:

    HTTP/1.1 200 OK
    {"ready":true,"in_flight_requests":1}

Liveness kiểm tra ứng dụng còn phản hồi. Readiness cho biết instance sẵn sàng nhận traffic; hệ thống điều phối có thể dùng kết quả này để quyết định chuyển request vào instance.

in_flight_requests=1 có thể bao gồm chính request /ready đang được middleware theo dõi.

### Exercise 5.2 — Graceful shutdown

Kịch bản đã chạy:
1. Server develop có PID 13909.
2. Gửi POST /ask?question=Long%20task ở chế độ nền.
3. Sau 1 giây, gửi kill -TERM 13909.
4. Chờ curl hoàn thành.

Kết quả thực tế:

    Curl exit code: 0
    {"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
    HTTP 200

Request đang xử lý vẫn hoàn thành sau khi gửi SIGTERM.

Dòng "Server exit code: 0" ban đầu chạy ở terminal curl chưa chứng minh mã thoát server. Sau đó đã kiểm tra lại bằng subprocess do runner trực tiếp quản lý: gửi SIGTERM khi request đang chạy, request trả HTTP 200 và server thoát với exit code 0. Bằng chứng: `reports/part5-graceful.json` và `reports/part5-graceful.log`.

Graceful shutdown cần ngừng nhận request mới, hoàn thành request đang xử lý, đóng tài nguyên rồi thoát. SIGTERM cho phép xử lý shutdown; SIGKILL không cho ứng dụng chạy cleanup.

### Exercise 5.3 — Stateless design

Nếu history nằm trong dictionary của process, request sau chuyển sang instance khác sẽ không đọc được history của instance trước.

Bản production tách state ra Redis:
- Các agent cùng dùng REDIS_URL=redis://redis:6379/0.
- save_session lưu JSON vào key session:<session_id>.
- load_session đọc dữ liệu từ Redis.
- Theo code, session có TTL mặc định 3600 giây và history giữ tối đa 20 tin nhắn.

Stateless ở đây nghĩa là agent không phụ thuộc vào state riêng trong RAM để duy trì session; state vẫn tồn tại trong Redis dùng chung.

Code mẫu có fallback sang RAM nếu không kết nối Redis. Fallback này không đáp ứng yêu cầu chia sẻ state khi scale.

### Exercise 5.4 — Load balancing

Chạy trong 05-scaling-reliability/production:

    touch .env.local
    docker compose -p k5-day14-scaling up -d --build --scale agent=3

Sơ đồ:

    Client -> Nginx localhost:8080
                    |
                    +-> agent-1:8000
                    +-> agent-2:8000
                    +-> agent-3:8000
                              |
                              v
                         Redis dùng chung

docker compose ps xác nhận:
- agent-1, agent-2, agent-3: healthy.
- redis: healthy.
- nginx: Up, publish cổng 8080 của máy tới cổng 80 trong container.

### Exercise 5.5 — Test stateless

Chạy:

    python test_stateless.py

Session ID thực tế:

    cce48759-1d27-480d-b5ef-460b8d6ed605

Phân phối request:

| Request | Instance |
|---|---|
| 1 | instance-400a04 |
| 2 | instance-b539ee |
| 3 | instance-ce3411 |
| 4 | instance-400a04 |
| 5 | instance-b539ee |

Kết quả:
- Total requests: 5.
- Instances used: 3 instance khác nhau.
- Total messages: 10, gồm 5 user và 5 assistant.
- History giữ đủ thứ tự các lượt hội thoại dù request được xử lý bởi nhiều instance.

Script kiểm tra nhiều request qua các instance và đọc lại history. Script không tự kill instance; chưa thử tình huống một instance bị tắt.

## Part 6 — Production AI Agent

Đã hoàn thiện code trong `06-lab-complete/`; không sửa script chấm.

Lệnh kiểm tra đầy đủ đã chạy, có cả runtime 2 worker và Docker:

```bash
cd 06-lab-complete
python check_production_ready.py --redis-url redis://127.0.0.1:16379/0
```

Redis local của bài đang publish cổng 16379. Truyền URL Redis vì Docker Desktop không tạo được Redis tạm trên cổng ngẫu nhiên ở lần thử đầu. Không dùng --static-only hoặc --skip-docker cho kết quả dưới đây.

```text
📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

Bằng chứng đầy đủ: `reports/production-readiness.txt`.

- Sliding window dùng sorted set và Lua nguyên tử; Redis TIME làm mốc thời gian chung, API key được hash trước khi tạo tên key.
- Cost guard theo ngày UTC: giữ trước chi phí output tối đa của mock bằng Lua, rồi đối soát với token ước lượng thực tế. Số tiền lưu bằng nano-dollar nguyên, có thời hạn đến ngày UTC tiếp theo.
- Redis lỗi thì /ready trả 503, /health vẫn 200; /ask trả 503 nếu không kiểm tra được rate limit/ngân sách.
- /ask dùng thread pool của FastAPI cho mock đồng bộ. Lifespan đóng client Redis sau khi server hoàn tất request; không thay signal handler của Uvicorn.
- Log app là JSON, không ghi API key hoặc nội dung câu hỏi.
- Docker multi-stage, slim, non-root, uvicorn PID 1 qua exec, port đọc PORT. Checker đo image khoảng 63 MB theo trường size của Docker.
- Kiểm tra 100 lời gọi Redis đồng thời: đúng 7 được chấp nhận, 93 bị chặn khi limit=7. 100 yêu cầu giữ ngân sách chỉ nhận 6 khoản giữ; tổng 0.00009 USD không vượt budget 0.0001 USD. Bằng chứng `reports/redis-concurrency.json`.
- PASS tiêu chí cấu hình deploy của checker chưa đồng nghĩa URL cloud đã được kiểm tra; trạng thái deploy thực tế ghi ở DEPLOYMENT.md.

## Part 7 — Benchmark & Observability

### Exercise 7.1 — Metrics và cardinality
- Counter: http_requests_total, chỉ tăng khi có request được middleware quan sát.
- Gauge: agent_in_flight_requests, tăng khi request bắt đầu và giảm khi hoàn tất.
- Histogram: http_request_duration_seconds, các bucket cho phép ước lượng percentile.
- Nếu dùng URL thật làm label, bot quét hàng nghìn đường dẫn không tồn tại sẽ tạo hàng nghìn tổ hợp label/time series; bộ nhớ và chi phí query tăng. route.path cùng nhãn unmatched gom các đường dẫn không khớp route vào cùng nhóm.
- Đã thêm Histogram agent_question_length_chars trong develop/app.py và observe độ dài câu hỏi trước khi gọi LLM. Không đặt độ dài hay câu hỏi vào label.
- Phép thử thật: một câu hỏi, histogram count=1 và sum bằng độ dài ký tự; ba URL lạ đều gom route=unmatched. Bằng chứng: reports/question-metric-test.json và reports/question-metrics.prom.

### Exercise 7.2–7.7
Số đo và phân tích nằm trong BENCHMARK_REPORT.md, JSON trong reports/, CSV trong benchmark-results/, ảnh trong screenshots/. Phần observability/deploy chỉ được đánh dấu hoàn tất sau khi có bằng chứng tương ứng.

## AI log

### Hỗ trợ setup và Part 1
- Hỏi: cách chuẩn bị WSL2, Docker, Python và thực hiện Part 1.
- Nhận: hướng dẫn lệnh chạy, giải thích lỗi quyền Docker, môi trường Python, cổng bị chiếm và bản nháp phân tích code.
- Tự thực hiện: chạy lệnh trong Ubuntu, sửa môi trường và cấu hình cổng theo hướng dẫn; chưa sửa mã nguồn Part 1.
- Tự kiểm tra: Docker hello-world chạy thành công; Python 3.11.18 chạy trên posix; gọi curl và đối chiếu các mã HTTP ghi phía trên.

### Hỗ trợ Part 2
- Hỏi: cách build/run Docker, so sánh multi-stage và chạy Compose.
- Nhận: hướng dẫn lệnh, giải thích các thành phần và hỗ trợ xử lý lỗi Docker Hub 429.
- Tự thực hiện: chạy lệnh build, run, inspect, exec, login, pull và Compose.
- Tự kiểm tra: gọi API develop/advanced/Nginx; kiểm tra healthy và appuser; lấy kích thước từ output Docker.
- AI hỗ trợ tính mức giảm 86.53% từ hai số byte đo được và soạn bản nháp báo cáo.

### Hỗ trợ Part 4
- Hỏi: cách kiểm tra API key, JWT, rate limit và cost guard.
- Nhận: lệnh kiểm tra, giải thích mã nguồn và bản nháp báo cáo.
- Tự thực hiện: kiểm tra API key thiếu/sai/đúng; đăng nhập lấy JWT; gọi /ask; chạy vòng lặp 20 request; chạy phép thử CostGuard riêng.
- Tự kiểm tra: API key trả 401/403/200; JWT trả 401/200; vượt rate limit trả 429; CostGuard ném HTTPException 402 trong phép thử trực tiếp.
- Chưa sửa mã nguồn Part 4; chưa triển khai cost guard Redis ở phần này.

### Hỗ trợ Part 5
- Hỏi: cách kiểm tra health/readiness, SIGTERM và stateless scaling.
- Nhận: hướng dẫn lệnh, giải thích PID, mã thoát và Redis dùng chung.
- Tự thực hiện: chạy server develop, gọi health/readiness, gửi SIGTERM khi có request; chạy Compose với 3 agent và test_stateless.py.
- Tự kiểm tra: health/readiness trả 200; request khi gửi SIGTERM hoàn thành với HTTP 200; 3 agent healthy; 5 request qua 3 instance và history đủ 10 tin nhắn.
- Đã bổ sung phép thử SIGTERM có quản lý subprocess và xác nhận exit code 0 trong reports/part5-graceful.json; chưa thử tắt một instance trong stack Part 5.
- Chưa sửa mã nguồn Part 5.

### Hỗ trợ Part 6 — config, health, logging và API key
- Hỏi: cách hoàn thiện các phần nền tảng từ bản khung.
- Nhận: code config đọc environment, xác thực API key, /health, logging JSON và lifespan.
- Thay đổi: app/config.py, app/auth.py, app/main.py và .env.example.
- Kiểm tra trước khi sửa: --static-only báo 0/12 tiêu chí.
- Kiểm tra thực tế bước đầu: /health trả 200; thiếu/sai API key trả 401; key đúng trả 200. Chưa đối chiếu output log JSON.

### Hỗ trợ Part 6 — Redis và readiness
- Nhận: code Redis client kết nối theo nhu cầu, /ready và đóng client khi shutdown.
- Thay đổi: app/redis_client.py và app/main.py.
- Thiết kế: không ping Redis khi import; /ready kiểm tra ping và trả 503 nếu Redis không truy cập được; /health độc lập với Redis.
- Chưa ghi nhận kết quả kiểm tra sau thay đổi.

### Hoàn thiện tự động Part 6
- Yêu cầu: hoàn thành bài lab.
- AI triển khai Redis sliding window nguyên tử và giữ trước ngân sách theo ngày UTC; nối vào /ask, thêm Docker/Compose và cấu hình cloud.
- Token và chi phí Part 6 là ước lượng cho mock, không phải usage nhà cung cấp thật.
- Kết quả kiểm tra sẽ được bổ sung từ output thực tế, không chỉnh script chấm hoặc golden dataset.

### Kiểm tra hoàn thiện Part 6 và benchmark local
- AI trực tiếp chạy script chấm đầy đủ với Redis local: PASS 12/12, 43/43 checks.
- AI chạy load test 300 request ở concurrency 1/10/50/100 và ba mức slow rate, giữ cả các kết quả FAIL SLO.
- Eval baseline v1/v2 được đo trước khi bổ sung KB JWT/HPA; sau sửa v2 đạt 23/23, không regression.
- Kiểm tra lại Part 5 bằng subprocess: request hoàn thành với HTTP 200, server exit code 0.
- Đối chiếu protected files với HEAD sau chuẩn hóa line ending: script chấm và golden dataset không đổi nội dung.

### Hỗ trợ Exercise 7.1
- AI thêm histogram phân bố độ dài câu hỏi và kiểm tra qua endpoint /metrics thật.
- Xác nhận ba URL 404 khác nhau gom vào label route=unmatched, không tạo label theo URL tùy ý.

### Chuẩn bị deploy Railway và báo cáo Part 3
- AI tạo cấu hình Docker/Railway/Render và so sánh từ nội dung các file thực tế.
- Chủ tài khoản chọn Railway; CLI đã cài từ website chính thức. Chưa xác nhận deploy khi chưa đăng nhập và kiểm tra URL thật.

### Hỗ trợ observability và báo cáo cuối số đo
- AI sửa PYTHONUSERBASE trong Dockerfile observability sau khi log xác nhận ModuleNotFoundError.
- Đã chạy Locust thật 100 users/2 phút cho 1 và 3 instance; chạy A/B/C/D/E và fault kết hợp để quan sát nhiều rule firing.
- Giữ nguyên alert_rules.yml; promtool test rules trả SUCCESS. Timeline alert và CSV được lưu nguyên số đo, bao gồm lỗi mock.
- Trace được lấy từ Jaeger API v3, chọn trace chậm/lỗi có log JSON trùng trace_id. Ảnh UI và deploy cloud vẫn cần bằng chứng trước khi hoàn thành toàn bộ bài.
