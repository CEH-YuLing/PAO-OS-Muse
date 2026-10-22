"use client";

import {Cable, CheckCircle2} from "lucide-react";
import PaoAppShell from "./PaoAppShell";
import {WorkspaceModule} from "@/lib/workspace-modules";

export default function ModuleScaffold({module}: {module: WorkspaceModule}) {
  return <PaoAppShell pageTitle={module.label} pageSubtitle={module.description}>
    <section className="pao-module-scaffold">
      <span><Cable size={24}/></span>
      <p className="pao-module-kicker">ROUTE ĐỘC LẬP · {module.number}</p>
      <h2>{module.label} đã có trang riêng</h2>
      <p>Nội dung module sẽ được triển khai theo đúng thứ tự đã xác nhận. Trang hiện dùng chung phiên đăng nhập, điều hướng, Ask PAO và PAO Copilot.</p>
      <div><CheckCircle2 size={16}/> Không sử dụng dữ liệu giả</div>
    </section>
  </PaoAppShell>;
}
