# S2 — Sổ nghiệm thu theo từng checkpoint

Ngày 11/10/2026, F:\PAO-ACOS. Người dùng yêu cầu hoàn thiện toàn S2 từng bước,
không hỏi lại các quyết định đã chốt. Master vẫn sở hữu thứ tự. Không gọi quyền
model thành quyền tool, không dùng fixture làm nghiệm thu connector thật.

**Toàn S2 đạt local14/10/2026:**1684backend/0fail/0skip,21browser tích hợp,
80Node/typecheck/build21,installed0058/334/binding mới và exact restore đạt.
[Bằng chứng tích hợp](S2-FINAL-INTEGRATION-2026-10-14.vi.md) giữ cả các lượt lỗi
và giới hạn. S3.1A nay đã đóng local theo [evidence](S31A-LOCAL-ACCEPTANCE-2026-10-14.vi.md);
S3.1B và tổng S3.1 đã đạt local15/10 theo [evidence](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md):
1737backend/5browser/96Node/build21/0060/live338/exact restore. Tiếp theo duy nhất
**S3.2C — bridge/webhook/report integration**; S3.2A/B source_verified theo
[B evidence368affected/25Node/candidate0063](S32B-SCOPED-EXECUTION-2026-10-15.vi.md).
Không làm lại S31B/S32A/B hoặc đánh dấu toàn S3 accepted.
Không dispatch lại các checkpoint S2 đã đóng.

| Checkpoint | Trạng thái | Điều kiện đóng |
|---|---|---|
| S2.1A inventory/preview | local_accepted | Evidence S21A |
| S2.1B1 staged grants | local_accepted | Evidence S21B1,0049 |
| S2.1B2a model denial | local_accepted | Evidence S21B2A |
| S2.1B2b model activation/pins/UI | local_accepted | 1298backend,29authority corpus/real ARQ,25Node/typecheck/build21/browser;0050/live321/exact restore. Evidence S21B2B; P7 intermittent ghi riêng |
| S2.1B2c MCP execution | local_accepted | 234affected/25Node/typecheck/build21/browser2+3; native authority/private Brain/rotation/real ARQ;0051/live323/backup exact restore119business. Evidence S21B2C |
| S2.1B2d Meta/Google execution | local_accepted |186affected/66focused/real ARQ;25Node/typecheck/build21/browser4; exact-account transport/no broad discovery;0052/live327/exact restore119business. Evidence S21B2D12/10; không live Ads |
| S2.2A lifecycle/vault/version | local_accepted |247affected/25Node/typecheck/build21/browser4; probe role/registered fences, append generations/old consent denial;0053/live328/restore119business; Evidence S22A12/10 |
| S2.2B quota/resource isolation | local_accepted | B1/B2a/B2b/B3 native scoped coverage đạt local; global host fairness/production chưa đạt |
| S2.2B1 model resources | local_accepted | Evidence S22B1; atomic policy/CAS/reservation,unknown accounting,expiry/no replay,probe quota,immutable model pin; chưa quota UI hoặc MCP/Ads queue caps |
| S2.2B2 native queue/resource isolation | local_accepted | B2a/B2b scoped native coverage đạt local; global host scheduling/production chưa nghiệm thu |
| S2.2B2a native read jobs | local_accepted |238affected/33focused/25Node/typecheck/build21/browser5;0055/live332/old hashes exact; Evidence S22B2A13/10 |
| S2.2B2b metadata/probes/legacy/embeddings | local_accepted |Native metadata/legacy/Memory+Knowledge coverage đạt0058/live334/bindingc136c3aa/565integrated B2b/browser2+1/build21/exact restore124business theo [evidence](S22B2B-KNOWLEDGE-EMBEDDINGS-2026-10-13.vi.md); không fullS2/global host fairness/provider thật |
| S2.2B3 quota Settings/integration | local_accepted14/10 |128affected backend+35Node/typecheck/contracts/build21/browserHTTP1; CAS/lost-response/manual recovery/admin/operator/mobile/switch/unknown accounting,0058/live334/exact restore. [Evidence](S22B3-QUOTA-SETTINGS-2026-10-14.vi.md) |
| S2.3 Settings hợp nhất | local_accepted14/10 | A/B/C/D/E/F và cổng tích hợp đạt; xem bằng chứng S2 cuối |
| S2.3A reliable observations | local_accepted14/10 |76affected/backend/browser2+49Node/typecheck/build21;9/9installed snapshots,0058/live334/binding không đổi/exact restore. [Evidence](S23A-SETTINGS-OBSERVATIONS-2026-10-14.vi.md) |
| S2.3B Cloud Model lifecycle/help | local_accepted14/10 |147affected trước console audit;57Node/typecheck/build21/finalbrowser3/9installed snapshots/0058/live334/exact restore. [Evidence](S23B-CLOUD-SETTINGS-2026-10-14.vi.md) |
| S2.3C MCP lifecycle/help | local_accepted14/10 |157affected backend/64Node/typecheck/build21/finalbrowser5/0058/live334/exact restore; [Evidence](S23C-MCP-SETTINGS-2026-10-14.vi.md); không server thật |
| S2.3D Ads lifecycle/help | local_accepted14/10 |100native backend+5browser qua affected/focused recovery,71Node/typecheck/build21/0058/live334/exact restore; [Evidence](S23D-ADS-SETTINGS-2026-10-14.vi.md); Meta official docs429/live gate còn mở |
| S2.3E Host-config lifecycle/scope | local_accepted14/10 |26affected gồm4browser/77Node/finalTypeScript/build21/0058/live334/exact restore; [Evidence](S23E-HOST-CONFIG-SETTINGS-2026-10-14.vi.md); native host gates không đổi |
| S2.3F Team/account & mobile | local_accepted14/10 |63native backend/8browser/80Node/typecheck/build21/0058/live334/exact restore; [Evidence](S23F-TEAM-ACCOUNT-MOBILE-2026-10-14.vi.md); không tự invite/grant/revoke hoặc tenant App S4 |
| S2 tích hợp cuối | local_accepted14/10 |1684backend/21browser/80Node/typecheck/build21/0058/live334/current binding/exact restore; master/unified/register đồng bộ; [Evidence](S2-FINAL-INTEGRATION-2026-10-14.vi.md) |

Không cần credential thật để hoàn thiện code/local gates. OAuth/provider thật,
remote CI, production reboot/HTTPS và hành động chi tiền vẫn nghiệm thu riêng;
không tự mở flags hoặc ghi dữ liệu business thật để làm xanh các gate đó.

S2.1B2b thêm consent record append-only, không sửa B1 status/history hoặc gia hạn
TTL. ModelAccessPanel là UI của checkpoint này, chưa là Settings toàn provider.
Không suy ra hoàn tất S2.1B2/S2.2/S2.3 từ model authority riêng lẻ; trạng thái
hiện hành dựa trên lượt nghiệm thu tích hợp14/10 bên trên.
