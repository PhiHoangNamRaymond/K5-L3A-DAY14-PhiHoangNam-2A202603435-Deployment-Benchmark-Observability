# Deployment Information

## Public URL

**https://day14-agent-6a2l.onrender.com**

## Platform

**Render** (Blueprint), deploy chính agent Part 6 trong `06-lab-complete/`.

- Blueprint file: [`06-lab-complete/render.yaml`](06-lab-complete/render.yaml), Blueprint Path đặt là `06-lab-complete/render.yaml`.
- Web service `day14-agent`: runtime Docker, `rootDir: 06-lab-complete`, health check `/health`, plan free, region Oregon.
- Key Value `day14-redis` (Valkey 8, plan free): dùng chung cho rate limit và cost guard; `REDIS_URL` của agent lấy từ `fromService.connectionString`.
- Deploy từ commit `6addfef` của nhánh `main`, trạng thái **Deploy succeeded / Live** (25/11/2026 20:57 GMT+7).

Railway là lựa chọn ban đầu (`06-lab-complete/railway.toml` vẫn giữ). Tài khoản Railway báo **Trial Ended** nên không deploy được nếu không nâng cấp gói trả phí; vì vậy chuyển sang Render. Rubric cho phép chọn Railway hoặc Render làm nền tảng chính.

## Test Commands (CP6)

Đặt `BASE` là URL public và `AGENT_API_KEY` là key do Render sinh (`generateValue: true`), rồi chạy:

```bash
BASE=https://day14-agent-6a2l.onrender.com
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'          # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'                                              # 200
```

### Kết quả thực tế (25/11/2026 13:56:17 UTC)

| Lệnh | Mong đợi | Thực tế |
|---|---:|---:|
| `GET /health` | 200 | **200** |
| `GET /ready` | 200 | **200** |
| `POST /ask` không có key | 401 | **401** |
| `POST /ask` có key | 200 | **200** |

Thêm: `POST /ask` với key sai trả 401. Ví dụ response có key:

```json
{"question":"What is Docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"input_tokens":4,"output_tokens":19,"cost_usd":1.2e-05,"source":"estimated_mock"}}
```

Output đầy đủ (không chứa key): [`reports/render-cp6.txt`](reports/render-cp6.txt).

Lưu ý: instance free của Render tắt khi không có traffic. Request đầu tiên sau một thời gian nghỉ có thể mất khoảng 50 giây để khởi động lại.

## Environment Variables Set

Đặt trên Render qua Blueprint, không ghi giá trị secret trong code hay repo:

| Biến | Nguồn |
|---|---|
| `ENVIRONMENT` | `production` |
| `AGENT_API_KEY` | `generateValue: true`, Render tự sinh, chỉ xem được trong dashboard |
| `REDIS_URL` | `fromService` → `day14-redis.connectionString` (URL nội bộ) |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` |
| `PORT` | Render cấp; Docker CMD đọc `${PORT:-8000}` |

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png): service `day14-agent`, Deploy succeeded, URL public.
- [Service running](screenshots/running.png): Events, "Deploy live for 6addfef", trạng thái Live.
- [Test results](screenshots/test.png): 4 lệnh CP6 trả 200 / 200 / 401 / 200.
- [Environment variables](screenshots/render-env.png): các biến đặt trên Render, giá trị bị che.

## Bằng chứng local

`reports/production-readiness.txt`: kiểm tra đầy đủ runtime + Docker, PASS 12/12 và 43/43 checks.

## Dọn tài nguyên

Sau khi được chấm, xóa Blueprint `day14-agent` (gồm web service và Key Value) trên Render. Không ghi API key hoặc URL Redis có password vào ảnh và báo cáo.
