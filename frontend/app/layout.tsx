import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Resume Tailoring",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header>
          <h1>ResumePilot AI 📝</h1>
          <h2>| Ivan Yazykov, Tsinghua 2026</h2>
        </header>

        {children}
      </body>
    </html>
  );
}
