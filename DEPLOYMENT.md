# Deployment Information

**Nền tảng chính:** Railway  
**Source root của service:** `06-lab-complete/`  
**Trạng thái:** Code đã PASS 12/12 local; đang chờ xác thực tài khoản Railway CLI. Chưa có URL public được xác minh. Không coi phần deploy là hoàn thành.

## Thành phần
- Agent: image Python 3.11 slim, 2 Uvicorn worker, user non-root.
- Redis: service riêng dùng chung cho rate limit và budget.
- Public HTTP qua domain Railway; /ask yêu cầu X-API-Key.

## Biến môi trường cần đặt
- ENVIRONMENT=production
- AGENT_API_KEY: secret sinh riêng cho deployment; không ghi giá trị vào repository.
- REDIS_URL: tham chiếu URL nội bộ của service Redis; không ghi giá trị vào repository.
- RATE_LIMIT_PER_MINUTE=10
- DAILY_BUDGET_USD=1.0
- PORT: nhận từ Railway, Docker CMD sử dụng giá trị này.

## Kiểm tra sau deploy
Đặt BASE bằng URL public thực tế và AGENT_API_KEY bằng key của deployment, rồi chạy:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
```

Mong đợi: 200, 200, 401, 200. Kết quả thực tế sẽ được thêm sau khi deploy; các mã mong đợi trên chưa phải bằng chứng kiểm tra public URL.

## Bằng chứng local
`reports/production-readiness.txt`: kiểm tra đầy đủ runtime + Docker, PASS 12/12 và 43/43 checks.

## Dọn tài nguyên
Sau khi được chấm, dừng/xóa service lab trên Railway để tránh tiêu credit tiếp. Không ghi token, API key hoặc URL Redis có password vào ảnh và báo cáo.
