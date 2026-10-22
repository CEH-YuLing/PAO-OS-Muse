# Muse — nghiệm thu trọn luồng job nghiệp vụ local

Ngày22/10/2026 · nguồn `F:\PAO-ACOS` · **local_accepted trong phạm vi bên dưới**.

## Kết quả và phạm vi

Đã chạy một vòng nghiệp vụ có hai việc phụ thuộc nhau bằng **thuê bao Muse thật**:

1. Tạo hồ sơ doanh nghiệp và kế hoạch có cấu trúc bằng dữ liệu tổng hợp.
2. Xuất bản agent/skill văn bản và cấu hình routing hai model, ngân sách32.768,
   output512 và timeout120s qua luồng validate/review/publish hiện hữu.
3. Chủ sở hữu thử nghiệm duyệt kế hoạch và tạo các Task/Goal/Project native.
4. Tạo job nghiên cứu; gửi lại cùng request key vẫn nhận cùng job, không tạo lượt mới.
5. Sau khi job đã xếp hàng, đổi routing mặc định sang Spark1.2. Job đầu giữ pin
   Spark1.3/minimal và revision1, không bị sửa theo cấu hình mới.
6. Outbox → Redis15 → ARQ burst worker thật → Run/Studio/LlmAttempt → Muse native.
   Sau nhịp thu kết quả của scheduler hiện hữu, task ở chờ duyệt/progress90.
7. Việc nội dung bị chặn khi nghiên cứu chưa được duyệt, dù Run đã completed.
   Duyệt sai artifact hash bị409; duyệt đúng mới cho phép việc phụ thuộc.
8. Job nội dung dùng Spark1.2/low theo routing revision2, nhận nội dung nguồn đã
   duyệt, qua ARQ thật và được duyệt riêng. Hai task100%, Goal/Project completed.
9. Truy cập job bằng SME khác bị404. Đọc lại artifact giữ nguyên hash/nội dung;
   gọi lại Run đã hoàn tất không gửi prompt mới. Không sao chép dữ liệu SME.
10. Tạo báo cáo nội bộ và gửi lại cùng request key: cùng báo cáo, usage khớp
    actual LlmAttempt, KPI/chi phí provider chưa có bằng chứng vẫn để chưa rõ.

Không sửa backend/frontend/schema/.env, không thêm runner, bảng dữ liệu hoặc
wizard cấp quyền AI. Thay đổi là bổ sung bài nghiệm thu và chế độ kiểm thử vào
`scripts/check_gd01_local.py` hiện hữu. API binding vẫn
`c251430392234918fd7f86635b758ac0c3cd2cd6b21ec260a34d8451aee09edb`,
schema0077/161bảng/435operations.

## Bằng chứng

| Kiểm tra | Kết quả và receipt |
|---|---|
| Regression nghiệp vụ/Muse không provider | 134pass,0fail/error/skip,129.96s;4ARQ deprecation warnings. `.runtime/gd01-tests-2b132c26682e49d48ab7ac0f0bdb1878/receipt.json` |
| Hai job thuê bao thật | 1pytest pass,36.60s,2ARQ warnings;2native calls,0tools/0API fallback, cleanup process và khóa Redis thử đã kiểm. `.runtime/gd01-tests-0fc4f9ad193943afbe16b35f889a0e69/receipt.json` và `live-summary.json` |
| Dữ liệu/source | Cả hai lượt đều giữ primary rows/source/env/runtime pin/schema; không restore primary hoặc chỉnh hash |
| Bản cài sau nghiệm thu | `.runtime/gd01-installed-f3176c8904de4af69237d7c21a4b7938/receipt.json`: GET-only,2SME/5Muse/6Codex/3replay, contract khớp, API/ready/Web200, worker khỏe;0mutation/provider |

Hai lần gọi model thực tế:

| Việc | Model | Effort | Input token | Output token |
|---|---|---|---:|---:|
| Nghiên cứu | muse-spark-1.3 | minimal | 14336 | 317 |
| Nội dung | muse-spark-1.2 | low | 14353 | 310 |
| Tổng báo cáo | | | **28689** | **627** |

Hai attempt `studio_skill` đều completed/usage reported/cleanup verified.
Đây là token actual do native báo cáo, **không phải quota còn lại hoặc hóa đơn API**.
Native có thể tính cả reasoning trong output; không suy số token từ độ dài marker.
Replay/đọc lại/gửi trùng không thêm call. Không gửi dữ liệu primary cho provider.

Regression134 còn bao gồm stop/cancel/thu hồi actor, thay profile/plan, routing,
quyền SME, đối soát/budget mô phỏng và báo cáo theo lịch hiện hữu. Các nhánh lỗi
này dùng gateway/native giả lập; **không gọi chúng là bài hủy giữa chừng trên
Muse thật**. Lượt live chỉ chạy hai job thành công, không lặp prompt lỗi để tiêu quota.

## Hai lỗi bài thử được giữ lại

- `.runtime/gd01-tests-85e0125009f24a3a873e14d03c4b0dae/receipt.json`: test đòi
  task chờ duyệt ngay sau ARQ nhưng bỏ qua nhịp thu kết quả. Bổ sung gọi scheduler
  hiện hữu, giữ nguyên assertion và backend; không ép status trong database.
- `.runtime/gd01-tests-07f536c1b2b7402791432d1d53c840ae/receipt.json`: bài thử gọi
  nhầm archive `skill-replay` legacy cho kết quả Studio. Business artifact đúng
  được đọc qua GET job và hash; legacy409 được giữ và kiểm tra, không tạo archive giả.
  Cả hai lượt này không gọi Muse/provider thật và không thay primary.

Source test của lượt134 được đóng trước khi thêm assertion xác minh Redis cleanup.
Lượt live sau đó chạy bản mới và chứng minh `redis_cleanup_verified=true`.
Không mô tả hai source test là một pipeline hoặc một lượt full regression chung.

## Giới hạn nghiệm thu — không suy rộng

- Đây là **vòng nghiệp vụ kỹ thuật local, API + hàng đợi ARQ thật + Muse thật**
  trong `pao_test`/Redis15; không tạo job thử trong SME thật trên UI của chủ.
  Không có một lượt thao tác trình duyệt end-to-end mới cho hai job live này.
- Kế hoạch do bài thử tạo có cấu trúc; output JSON marker tổng hợp nhằm nghiệm
  thu đường chạy/schema, không đánh giá chất lượng nghiên cứu hoặc content kinh doanh.
  Chưa chứng minh AI tự lập kế hoạch tháng hoàn chỉnh hoặc tự tạo ảnh/video/Ads.
- Goal/Project completed là trạng thái tổng hợp nghiệp vụ sau hai task được
  duyệt, **không phải nghiệm thu P6 Goal runner hoặc Temporal bằng Muse**.
- Không chạy quảng cáo, ghi/gửi/đăng ra ngoài, chi tiền hoặc kết nối dữ liệu thực.
  Báo cáo chưa có KPI thực, chi Ads hay quota còn lại thì không đổi thành0.
- Không nâng ngân sách của job/skill đã xuất bản. Bài thử tạo phiên bản mới có
  ngân sách được duyệt rõ ràng trong phạm vi test.
- Giữ giới hạn adapter: native overhead khoảng14k input/call, output gom đến
  terminal, codec usage trace pin1.4.10; chưa bảo đảm hard output-token cap upstream.
  Chưa Contributor/Wonder inference, Linux/VPS/public/pilot hoặc toàn GD01.

## Backup và cách chạy lại

Checkpoint trước bổ sung bài nghiệm thu:
`.runtime/checkpoints/p0-20261022T043937-9ea999af/manifest.json`.
Đích đã đối chiếu hash8file/private roundtrip và phục hồi clone161bảng/3archive:
`F:\PAO-BOS Backup 001\PAO-ACOS-Backups\20261022T043950Z-9434c66e574b43b8b35496f18131c33f`.
Không sao chép profile/token Muse, không ghi đè backup cũ; không phải offsite/portable key.

- `scripts/check_gd01_local.py --muse-business-local`: regression cách ly,0quota.
- `scripts/check_gd01_local.py --live-muse-business`: hai call thuê bao thật;
  chỉ chạy khi operator có chủ đích nghiệm thu, không đưa vào CI tự động.
- Dùng interpreter đã pin và biến PAO_ROOT/PYTHONPATH theo launcher hiện hữu.
  Các probe dùng khóa `isolated_test_slot`, không chạy chồng pao_test/Redis15.
  Không chạy lại bài live khi input/source không đổi chỉ để tăng số lần pass.

Kế tiếp: kiểm chất lượng với một brief tổng hợp sát nghiệp vụ, rồi dữ liệu thực
được chủ chọn/duyệt; tối ưu overhead trước chạy hàng loạt. Các nhánh Client khác
và giới hạn GD01 giữ nguyên theo master roadmap.
