# Giai đoạn 3 — Nghiệm thu CI trên GitHub

Ngày 17/10/2026. Target chạy ứng dụng: `F:\PAO-ACOS`.

**Chốt hosted CI đã đạt. Toàn Giai đoạn 3, M6/S6 và production vẫn chưa đóng.**

## 1. Mã nguồn và repository

- Repository private: [CEH-YuLing/Pao-ACOS](https://github.com/CEH-YuLing/Pao-ACOS).
- Nhánh: `phase3/hosted-ci`; commit `3151851752c4c446969cbc7f99eb11d0f9fdbbee`.
- Parent là commit remote ban đầu `6e6dff0b4242fe5840a88890ad472f738f66b0bd`.
  Không force-push, không merge hoặc đổi main; không mang lịch sử local sang remote.
- Checkout phát hành riêng: `F:\Apex\pao-github-publish-20261017`.
  Mỗi file source được so SHA256 với PAO trước/sau copy. Không commit/reset
  working tree đang chạy. Git local giữ HEAD cũ và các thay đổi chưa commit.
- 1.291 file source đã review; commit có 1.292 file, thêm tài liệu phát hành,
  giữ hai thông báo bản quyền MIT và thêm artifact audit Python trong workflow.
- Không đưa .env thật, database, checkpoint, runtime, uploads/exports, dependency,
  build, khóa riêng hoặc báo cáo có dữ liệu doanh nghiệp lên GitHub.

## 2. Review secret trước push

Gitleaks 8.30.1 tải từ release chính thức, ZIP đối chiếu checksum; chạy local,
che hoàn toàn giá trị. Không upload source lên dịch vụ quét.

- Quét 16 commit local trước fetch; 3 cảnh báo là request_key chống chạy lặp
  trong tests/browser fixture, không là authentication key.
- Snapshot/source phát hành có 9 cảnh báo: marker tổng hợp qua MockTransport,
  request_key, SHA OpenAPI và JWT vector công khai có key tổng hợp được unit-test.
  Không xóa findings, không ignore toàn thư mục tests, không sửa dữ liệu để ép xanh.
- Heuristic current source được review từng vị trí/hash, bổ sung dotfiles,
  Caddy/SQL và migration template bị suffix filter cũ bỏ qua. Inventory đủ 1.291 file.
- Không thấy giá trị secret cấu hình local trong source hoặc history; 6 password
  literal kiểm thử không khớp 2 tài khoản local đang hoạt động. Không đăng nhập,
  tạo token thật, rotate key hoặc thay dữ liệu để làm kiểm tra này.
- Đây là review theo pattern, nội dung và giá trị local đang biết; không phải
  bảo đảm tuyệt đối mọi credential lịch sử của dịch vụ bên ngoài đều được biết.

Báo cáo riêng (không đưa Git):
`F:\Apex\audit-reports\github-publish-2026-10-17\publish-review.json` và
`staged-manifest.json`; findings redacted và hashes giữ nguyên để truy vết.

## 3. CI thật đã chạy và đối chiếu artifact

[Run 39030584315](https://github.com/CEH-YuLing/Pao-ACOS/actions/runs/39030584315)
được kích hoạt bởi push đúng commit trên, không dùng kết quả local thay thế.

| Kiểm tra | Kết quả |
|---|---|
| Toàn pipeline | 18/18 bước, job success, 25 phút 14 giây |
| Backend | 2.258 passed, 0 failed/error/skipped, 1.297,51 giây; 62 ARQ warnings |
| Node frontend | 120 passed, 0 failed |
| TypeScript / contract / restore guards | đạt trong pipeline |
| Native portability smoke | 13 passed |
| Production frontend | build thành công, 23/23 trang |
| Python runtime audit | 57 packages, 0 advisory được báo |
| Npm runtime audit | 0 advisory |
| Npm toàn bộ | 5 high dev, vẫn cần review; chưa có production waiver |

Runner thực tế Ubuntu 24.04, Python 3.12.15, Node 22. Không dùng khóa hoặc DB
production; runner có PostgreSQL/Redis và dữ liệu tổng hợp riêng.

Artifact `backend-regression-results`, ID `12101056272`, digest
`sha256:ee11fa0bdfda2b6d7390e2a5bacf06c837ed5d41a6b665c36fa93fd4b2c5b777`.
Đã tải và đối chiếu repository/private/commit/branch/event/job success, đủ 18
stage, JUnit trùng ci-result và các audit. Artifact chỉ có backend-full.xml,
ci-result.json, js-security.json, python-security.json; không chứa source DB.

Requirements Git blob LF có SHA256
`02cc6d2bf46569136185c39ae2e857143c228d70920df3b70cf1f11f22868edc`;
khác hash file CRLF Windows là bình thường. Audit đã so với chính Git blob của
commit, không bỏ kiểm hash hoặc giả hai byte stream giống nhau.

Receipt mới: `.runtime/phase3-hosted-ci.json`;
artifact giữ ở `.runtime/phase3-hosted-39030584315/`.
Trạng thái tổng hợp: `.runtime/phase3-current-status.json`.
Các receipt local-only cũ vẫn giữ nguyên; hosted_ci_executed=false trong những
receipt lịch sử không phủ định run mới này và không được sửa lại để giả chúng
từng chạy trên GitHub. Báo cáo này và trạng thái tổng hợp sở hữu cập nhật mới.

## 4. Những gì còn mở

- Runner có annotation: các Actions hiện dùng Node 20 đã deprecated và được ép
  chạy Node 24; ubuntu-latest cảnh báo sắp đổi image. Lượt này PASS trên Ubuntu
  24.04; cần nâng/pin Actions và image trong đợt CI maintenance riêng, kiểm lại
  trên đúng commit sau thay đổi. Không gọi một lượt xanh là môi trường đã ghim.
- Redis runner cảnh báo memory overcommit; không sửa sysctl máy Windows/host
  dùng chung từ cảnh báo này. Cấu hình host riêng cần review trong production.
- Giữ 5 high dev advisories và 62 ARQ warnings, không audit-fix force/xóa lint.
- Host riêng, DNS/HTTPS/firewall/proxy, private storage/alerts, key rotation/
  offsite/private-blob recovery, reboot/failover và owner production review còn mở.
- Dữ liệu/action provider thật và owner pilot vẫn đã hoãn; không tự bật quảng cáo,
  Telegram, đổi .env, deploy công khai hoặc chạy action thật sau khi CI xanh.

Main trên GitHub vẫn giữ nguyên, chưa merge. Đây là nghiệm thu chốt hosted CI,
không là quyền merge/release/deploy production hoặc đóng toàn M6/S6.
