import type { Metadata } from "next";
import "./globals.css";
import "./theme.css";
import ThemeProvider from '@/lib/ThemeProvider';
import {THEME_BOOTSTRAP} from '@/lib/theme.mjs';
import {PaoRuntimeProvider} from "@/lib/PaoRuntimeContext";

export const metadata: Metadata = {
  title: "PAO — Trợ lý AI local",
  description:
    "PAO: trợ lý AI tự host cho cá nhân và nhóm nội bộ, sử dụng mô hình local qua Ollama.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" data-theme="dark" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{__html:THEME_BOOTSTRAP}}/></head>
      <body><ThemeProvider><PaoRuntimeProvider>{children}</PaoRuntimeProvider></ThemeProvider></body>
    </html>
  );
}
