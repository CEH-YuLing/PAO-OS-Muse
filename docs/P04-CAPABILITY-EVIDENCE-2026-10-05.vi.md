# P0.4 — Evidence-based platform catalog và frontend feature boundary
05/10/2026; F:\PAO-ACOS. PASS local.

Catalog bổ sung readiness_version/status_semantics và readiness cho từng feature,
integration/provider/compatibility mapping: implemented/configured/active/healthy/
accepted/reason/checked_at. Giữ fields legacy, không lấy chúng làm operational
evidence. Global API key không đồng nghĩa workspace router connection; Zalo/
Botcake/TikTok chưa có adapter nên readiness configured false dù có token.
Success check cũ trộn list/inference nên healthy unknown; recent explicit error
trong15phút có healthy false; stale/future unknown. Accepted không có evidence
thì null; shadow active false/accepted false. Không tự gọi provider hoặc decrypt
key trong catalog; workspace membership giữ nguyên.

UI catalog sang components/features/platform, workspace-scoped API; hiển thị
unknown rõ và old payload fallback. Nhãn endpoint-response tổng không gọi HEALTHY.
Đây hoàn thành lát cắt frontend của P0.3, không rewrite shell/console.

Backup/restore65tables/3archives/revision0024 đạt:
.runtime/m2-20261005T145020-c13785ea.dump,286494bytes. Idle9nhóm/lịch0/flags ngoài tắt.
API/ARQ drain/restart; schema không đổi. Existing source chỉ platform_api thay.

- Backend **358 passed**, không skip,355.77s,pao_test/Redis15.
- ARQ recovery79.34s/97.72s, mỗi ca mộtclaim.
- TypeScript --noEmit PASS; browser12routes mock PASS gồm readiness unknown.
- Runtime8/8; full OpenAPI baseline/source/savedUTF8/live unchanged.
- API/ready/Web HTTP200; oldartifact3/3;0job mới; DBcounts/revision/hash unchanged.
- ProcessAPI4380/worker3952 đúnginterpreter/starttime/entrypoint.
- Binding dc457782d3f08a14084f61a7cf3ed634667aa9155e9f95420c1cc2c070899672.

Không production build trongcheckpointnày; sẽ kiểm isolated build trong P0.5.
Không migration/roundtrip, nới pin/rebind/archive hoặc connector writes/M4/deploy.
Không commit/push/sửa bản gốc. Rollback review riêng service/UI/API, restart
API/ARQ sau idle/backup. Catalog accepted unknown không chứng minh connectors
đã nghiệm thu; không fabricate records để làm UI xanh.
