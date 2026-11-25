# Chạy agent Part 6 đã hoàn thiện

Python 3.11 trở lên, Docker Desktop + WSL2 trên Windows. Chạy từ thư mục này.

## Docker Compose
Tạo .env từ .env.example và đặt AGENT_API_KEY bằng key local riêng. File .env được gitignore. Nếu cổng 8000 đã dùng, đặt HOST_PORT khác khi chạy Compose.

```bash
docker compose -p k5-day14-final up -d --build
docker compose -p k5-day14-final ps
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
docker compose -p k5-day14-final down
```

## Kiểm tra đầy đủ
```bash
pip install -r requirements.txt
python check_production_ready.py
```

Nếu Docker Desktop không publish được cổng ngẫu nhiên cho Redis tạm, dùng Redis có sẵn:

```bash
python check_production_ready.py --redis-url redis://127.0.0.1:16379/0
```

Không dùng --skip-docker hoặc --static-only để thay cho kết quả chấm cuối cùng. Script chấm và golden dataset được giữ nguyên.

## Luồng /ask
Xác thực API key -> Redis sliding window -> kiểm tra và giữ trước budget -> mock LLM -> ghi nhận chi phí ước lượng -> JSON response.

Thiếu/sai key: 401; quá tốc độ: 429 + Retry-After; không đủ ngân sách: 402; Redis/LLM không sẵn sàng: 503. /health không phụ thuộc Redis, /ready có kiểm tra Redis.

Ngân sách ngày UTC được lưu bằng nano-dollar nguyên và dùng Lua để tránh race giữa worker. Giữ trước tối đa output của mock, sau đó trả phần dư khi đối soát. Đây là phép ước lượng token cho LLM giả lập, không phải dữ liệu billing từ nhà cung cấp.

## Deploy
Xem DEPLOYMENT.md ở gốc repo. Railway service phải dùng thư mục 06-lab-complete làm source root, có Redis và secret AGENT_API_KEY riêng. Healthcheck config đúng chưa chứng minh public URL hoạt động: luôn kiểm tra cả /ready và /ask sau deploy.
