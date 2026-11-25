# Benchmark & Observability Report — Day 14

**Họ tên:** Phí Hoàng Nam · **MSSV:** 2A202603435  
**Ngày chạy:** 25/11/2026 (GMT+7)  
**Môi trường:** Windows + Ubuntu WSL2, Python 3.11.18; Docker 29.5.3, 16 CPU logic và 7.47 GiB RAM theo Docker info. Đây là tài nguyên môi trường, không phải CPU/RAM dành riêng cho từng agent. Mỗi agent Compose bị giới hạn 0.5 CPU/256 MB.

## 1. SLO

| SLI | Mục tiêu | Lý do |
|---|---|---|
| p95 /ask local | ≤ 500 ms | Giữ trải nghiệm đa số request tương tác |
| Error rate local | ≤ 2% | Có khoảng 1% lỗi mock mặc định |
| Accuracy | 100% (23/23) sau sửa KB | Theo yêu cầu lab; đồng thời không regression |

Prometheus sử dụng ngưỡng alert riêng của bài: error >5% trong 1 phút, p95 >1 giây trong 2 phút, instance down 30 giây, cost >2 USD/giờ trong 2 phút. Không đồng nhất các ngưỡng alert này với SLO local.

## 2. Benchmark hiệu năng local

Mỗi lần chạy 300 request, có warm-up không tính vào kết quả; latency chỉ tính request HTTP 200. Error rate tính mọi request không phải 200. Lệnh và exit code nằm trong `reports/commands.json`.

### 2.1 Concurrency

| Concurrency | RPS | p50 ms | p95 ms | p99 ms | Error rate | SLO |
|---|---:|---:|---:|---:|---:|---|
| 1 | 4.49 | 189.2 | 218.5 | 1696.7 | 1.33% | PASS |
| 10 | 43.42 | 191.3 | 219.8 | 1680.9 | 1.33% | PASS |
| 50 | 101.32 | 205.1 | 296.9 | 1723.2 | 0.67% | PASS |
| 100 | 90.2 | 359.0 | 2539.9 | 2809.0 | 1.33% | FAIL |

RPS không tăng tuyến tính: tại concurrency cao, tác vụ asyncio, connection pooling, log I/O và giới hạn tài nguyên của máy tạo thêm chờ đợi. Concurrency 100 có throughput thấp hơn concurrency 50 và p95 vượt SLO. Đây là một phép đo 300 request mỗi mức, chưa phải ước lượng tải bền vững lâu dài; không suy ra nhân quả riêng cho một nút thắt khi chưa profile.

### 2.2 Tail latency, concurrency 20

| MOCK_SLOW_RATE | Avg ms | p95 ms | p99 ms |
|---|---:|---:|---:|
| 0 | 190.4 | 217.5 | 223.3 |
| 0.03 | 228.9 | 219.4 | 1690.7 |
| 0.1 | 354.4 | 1699.2 | 1723.3 |

Request chậm là phần đuôi phân phối. Khi xác suất chậm tăng lên 10%, p95 cũng đi vào nhóm request chậm. p99 nhạy với phần đuôi nhỏ hơn p95; average gộp phần lớn request nhanh với một số request chậm nên che giấu trải nghiệm xấu. So sánh cần tính đến dao động ngẫu nhiên và nhiễu tải máy; lab này không cố định seed và không lấy trung bình nhiều lần chạy.

## 3. Benchmark chất lượng

| Chỉ số | v1 | v2 ban đầu | v2 sau sửa KB |
|---|---:|---:|---:|
| Accuracy | 1/23 (4.35%) | 21/23 (91.30%) | 23/23 (100.00%) |
| Avg tokens/câu | 57.4 | 109.0 | 119.9 |
| Tổng cost USD | 0.000409 | 0.00076 | 0.000844 |
| Cost/câu đúng USD | 0.00040875 | 3.619e-05 | 3.671e-05 |
| Quality gate | FAIL | PASS | PASS |

| ID sai ban đầu | Keyword thiếu | Sửa KB |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Bổ sung tài liệu chuyên biệt tương ứng trong KNOWLEDGE_BASE |
| scaling-03 | cpu, memory, custom metrics | Bổ sung tài liệu chuyên biệt tương ứng trong KNOWLEDGE_BASE |

Đã sửa KNOWLEDGE_BASE trong cả bản develop và production, rồi khởi động lại v2. Không sửa golden dataset hoặc cách chấm. v2 dùng retrieval nên prompt dài, tăng token và chi phí mỗi câu; đổi lại cost trên một câu đúng giảm mạnh so với v1.

Chạy v1 với baseline v2 fixed trả exit code 1 và ghi regression trong `reports/eval_v1_regression.json`. Workflow `.github/workflows/quality-gate.yml` dùng exit code của eval để chặn CI khi accuracy dưới 100% hoặc có regression; CI tắt fault injection upstream để kiểm tra chất lượng ổn định. Đây là workflow đã chuẩn bị, chưa khẳng định GitHub Actions đã chạy trước khi push.

## 4. Observability stack

### 4.1 Dashboard và metrics (Exercise 7.4)
Stack Nginx → agent, Prometheus/Grafana và OpenTelemetry/Jaeger đã chạy thật. Đã sửa Dockerfile observability: user có home /app nhưng dependencies được copy sang /home/agent/.local; bổ sung PYTHONUSERBASE để Python tìm được thư viện, thay vì container restart vì ModuleNotFoundError.

Snapshot PromQL ở cuối lần chạy 3 instance, cửa sổ 1 phút, timestamp Unix 1795612670.0:
- p95 HTTP /ask: **294.55 ms**.
- Average HTTP /ask: **238.32 ms**; chênh lệch **56.23 ms**.
- Input token/s: **4991.88**, output token/s: **2728.73**.

Đây là percentile ước lượng từ histogram bucket phía server, nên không nhất thiết trùng percentile Locust phía client. p99 của load test cho thấy nhóm chậm khoảng 1.7 giây dù average thấp; average không thể hiện đầy đủ tail latency.

| Instance ở snapshot | Requests/s /ask | Tỉ trọng |
|---|---:|---:|
| 172.22.0.5:8000 | 20.510 | 33.12% |
| 172.22.0.8:8000 | 20.583 | 33.24% |
| 172.22.0.9:8000 | 20.838 | 33.65% |

Traffic được phân phối gần đều. Snapshot này có 3 instance sau bài scaling, thay vì 2 instance mặc định trong mô tả dashboard. Input token/s cao hơn output vì prompt chứa system instruction, câu hỏi và context retrieval; output chỉ là đoạn trả lời của mock.

GET http://localhost:8080/metrics đã kiểm tra trả **404**: Nginx chặn endpoint vận hành này. Prometheus scrape trực tiếp từng agent qua mạng Docker; chặn /metrics ở Nginx không ngăn Prometheus thu thập nội bộ. Bằng chứng số liệu và biểu thức: `reports/dashboard-metrics.json`.

### 4.2 Alert rules và chaos (Exercise 7.6)
`promtool test rules` đã trả SUCCESS; output lưu ở `reports/promtool-alert-tests.txt`. Các alert được quan sát qua API Prometheus thật, không sửa ngưỡng rule để làm chúng firing.

Thời gian dưới đây tính từ trước lúc bắt đầu áp dụng cấu hình, gồm thời gian recreate container và chờ DNS 15 giây. Trạng thái được lấy mỗi 5 giây; đây là thời gian quan sát đầu tiên, không phải thời điểm chuyển trạng thái chính xác tuyệt đối.

| Thí nghiệm | Thay đổi | Alert mong đợi | Quan sát lần đầu firing | Ghi chú |
|---|---|---|---:|---|
| A | {"MOCK_ERROR_RATE": "0.2"} | AgentHighErrorRate | 112.79 s | Quan sát chu kỳ mới |
| B | {"MOCK_SLOW_RATE": "0.3"} | AgentHighLatencyP95 | 170.90 s | Quan sát chu kỳ mới |
| C | {"LLM_MODEL": "mock-llm-large"} | LLMCostBurnRateHigh | 165.74 s | Đã firing trước thay đổi; cần đọc timeline để phân biệt chu kỳ cũ và tái-firing |
| D | docker pause một agent | AgentInstanceDown | 66.30 s | Quan sát chu kỳ mới |
| E | {"AGENT_VERSION": "v1"} | Không có alert chất lượng | Không có rule đánh giá accuracy | Alert hạ tầng còn tồn dư từ thí nghiệm trước không chứng minh phát hiện chất lượng v1 |

Sau các thử nghiệm riêng, cấu hình kết hợp error=0.2 và slow=0.3 đã được dùng để quan sát đồng thời. Snapshot cuối ghi nhận các rule firing: **AgentHighErrorRate, AgentHighLatencyP95**. JSON gốc và toàn bộ timeline từng poll nằm trong `reports/chaos-experiments.json`.

Cost alert đã xuất hiện trong tải benchmark mặc định: snapshot cuối scale 3 đo khoảng 8.59 USD/giờ quy đổi, vượt ngưỡng 2 USD/giờ. Vì vậy không coi mọi lần thấy cost alert sau đổi model là một phát hiện mới. Các con số là chi phí mô phỏng, không phải hóa đơn thật.

Khi pause container, nó vẫn nằm trong Docker DNS nhưng không trả lời scrape, nên up=0 có thể kích hoạt AgentInstanceDown. Nếu stop container, nó có thể biến mất khỏi DNS discovery và không còn target để biểu thức up==0 đánh giá. Lỗi 504 do Nginx chờ timeout có thể không được counter của agent ghi nhận; cần metric ở proxy hoặc synthetic check.

Đổi sang v1 làm retrieval biến mất và chất lượng giảm nhưng chưa có rule accuracy nên metric hạ tầng không đủ phát hiện. Dùng golden eval/quality gate trước deploy, eval định kỳ và phản hồi chất lượng có kiểm chứng. Phép thử v1 so với baseline v2 fixed đã trả exit code 1 trong báo cáo local.

### 4.3 Debug trace (Exercise 7.5)
Jaeger 2.23 tại môi trường này dùng API v3; endpoint nội bộ cũ /api/services trả 404. Trace được truy vấn theo API v3 và đối chiếu trace_id với log JSON thực tế.

**Trace chậm**
- trace_id: `a476c361899107a80dccdc5277920b68`.
- Tổng thời gian: 1724.696 ms.
- Span LLM `chat mock-llm-small`: 1699.218 ms, chiếm 98.52% thời gian trace.
- Phạm vi tìm: 500 traces returned by Jaeger API v3 searchDepth=500; không khẳng định đây là trace chậm nhất của toàn bộ lịch sử.
- Chi tiết span/event: `reports/slow-trace.json`.
- Dòng JSON log có cùng trace_id:

```json
{"ts": "2026-11-25T13:30:49.738371+00:00", "level": "INFO", "service": "observable-agent", "instance": "e226ecaac08a", "event": "llm_call", "trace_id": "a476c361899107a80dccdc5277920b68", "span_id": "82eadd2e37514010", "request_id": "593dd5424b56", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 108, "output_tokens": 70, "cost_usd": 5.8e-05, "llm_ms": 1698.6}
```

**Trace lỗi**
- trace_id: `2da5055fb71e4fc17856c92bcc293d66`.
- Tổng thời gian: 111.191 ms.
- Span LLM `chat mock-llm-small`: 86.815 ms, chiếm 78.08% thời gian trace.
- Phạm vi tìm: 500 traces returned by Jaeger API v3 searchDepth=500; không khẳng định đây là trace chậm nhất của toàn bộ lịch sử.
- Chi tiết span/event: `reports/error-trace.json`.
- Dòng JSON log có cùng trace_id:

```json
{"ts": "2026-11-25T13:31:13.552054+00:00", "level": "INFO", "service": "observable-agent", "instance": "e226ecaac08a", "event": "llm_error", "trace_id": "2da5055fb71e4fc17856c92bcc293d66", "span_id": "f59db41a4549ed09", "request_id": "afae9969ff6d", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

Trace chậm cho thấy phần lớn thời gian nằm ở lời gọi LLM mô phỏng, không phải retrieval. Trace lỗi có event exception trên span chat; có thể đi từ llm_error trong log sang đúng trace để xem lỗi upstream.

### 4.4 Ảnh bằng chứng
Ảnh chụp từ UI thật của stack đang chạy (Chrome headless, 25/11/2026 ~20:36–20:39 GMT+7), trong lúc Locust chạy 50 user với cấu hình chaos error=0.2, slow=0.3:

| Ảnh | Nội dung |
|---|---|
| `screenshots/grafana-dashboard.png` | Dashboard "Day 14 — AI Agent Overview" khi có tải: 11.4 req/s, error rate 21.13%, p95 1.89 s, 3 instance up; các panel latency, token/s, cost burn rate, request theo instance |
| `screenshots/jaeger-slow-trace.png` | Trace `a476c36…` (1.7 s): span chậm nhất `chat mock-llm-small` 1.7 s (1699.218 ms theo `reports/slow-trace.json`), retrieval chỉ 23.5 ms |
| `screenshots/jaeger-error-trace.png` | Trace `2da5055…` (111 ms, HTTP 503): span `chat mock-llm-small` 86.8 ms mang dấu lỗi, khớp log `llm_error` ở trên |
| `screenshots/prometheus-alert-firing.png` | Trang Alerts: **AgentHighErrorRate** và **AgentHighLatencyP95** cùng FIRING |

Khi chụp ảnh Prometheus: hai alert cùng chuyển sang pending lúc 13:36:32 UTC, AgentHighErrorRate firing sau `for: 1m`, AgentHighLatencyP95 firing sau `for: 2m` (quan sát firing lúc 13:38:41 UTC). Trạng thái API lúc chụp: `reports/screenshot_alerts.json`.

## 5. Benchmark scaling — Locust headless

100 users, ramp-up 10 users/giây, 2 phút mỗi mức. Bảng dùng riêng dòng POST /ask; không gộp GET /health vào RPS và percentile.

| Instance | RPS /ask | p50 ms | p95 ms | p99 ms | Failures / requests |
|---|---:|---:|---:|---:|---|
| 1 | 59.630 | 190 | 250 | 1700 | 71 / 7119 |
| 3 | 59.930 | 190 | 220 | 1700 | 82 / 7151 |

RPS /ask thay đổi +0.50%. So sánh không thể kỳ vọng tăng 3 lần: số user và khoảng nghỉ vẫn cố định, một instance async đã xử lý đồng thời được nhiều request, còn mock LLM chủ yếu chờ I/O và có slow tail. Nginx phân phối tải nhưng không rút ngắn thời gian một lời gọi LLM. Đọc p95/p99 và trace cùng throughput để tránh kết luận chỉ từ số instance.

CSV gốc: `benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv`; có thêm stats_history và failures để kiểm tra chi tiết. Locust exit code 1 do có lỗi mock được giữ nguyên, không sửa số đo hoặc bỏ request lỗi.

## 6. Kết luận hiện tại

1. Chạy được API không chứng minh khả năng chịu tải: phải đối chiếu latency/error với SLO.
2. Metric hạ tầng tốt không bảo đảm câu trả lời đúng; cần golden eval và quality gate.
3. Metrics cho biết điều gì bất thường; trace phân rã thời gian từng bước; log có trace_id giúp liên kết request cụ thể.

Nếu triển khai thật, bổ sung metric ở Nginx hoặc synthetic probe bên ngoài để bắt 504 mà agent không đếm, queue wait time, Redis saturation, và cảnh báo chất lượng theo eval định kỳ.
