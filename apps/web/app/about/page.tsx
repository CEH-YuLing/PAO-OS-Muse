import Link from "next/link";

export default function About() {
  return (
    <main style={{ minHeight: "100vh", padding: "72px 24px", background: "#04080f", color: "#f0ede8", fontFamily: "sans-serif" }}>
      <article style={{ maxWidth: 720, margin: "0 auto", lineHeight: 1.8 }}>
        <h1>PAO</h1>
        <p>Trợ lý AI tự host cho cá nhân và nhóm nội bộ, sử dụng mô hình local qua Ollama.</p>
        <p>Phiên bản Phase 1 có một Chief of Staff, hội thoại lưu bền và phản hồi theo thời gian thực. Các node agent khác hiện là phần giới thiệu giao diện.</p>
        <h2>Nguồn gốc mã nguồn</h2>
        <p>Giao diện phát triển từ <a href="https://github.com/RubenM1990/APEX-UI">APEX-UI</a> của Ruben Mouradian (Reznikov Engineering), theo giấy phép MIT. PAO là tên của dự án phái sinh này.</p>
        <p>Copyright (c) 2026 Ruben Mouradian (Reznikov Engineering). Thông báo bản quyền và toàn bộ điều khoản MIT được giữ trong LICENSE của mã nguồn.</p>
        <p>Nền shader và bảng đèn overview có nguồn gốc từ các thành phần cộng đồng MIT trên <a href="https://21st.dev/community/components">21st.dev</a>. Chi tiết ghi công được giữ trong CREDITS.md.</p>
        <Link href="/" style={{ color: "#75d8ef" }}>← Trở về PAO</Link>
      </article>
    </main>
  );
}
