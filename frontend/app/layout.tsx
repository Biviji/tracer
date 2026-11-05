import type { Metadata } from "next";
import { Archivo, DM_Mono } from "next/font/google";
import { Rail } from "@/components/layout/Rail";
import "./globals.css";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  weight: ["600", "700", "800", "900"],
});

const dmMono = DM_Mono({
  variable: "--font-dm-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: { default: "TRACE — Agent Reliability Lab", template: "%s · TRACE" },
  description:
    "Run the same agent task N times in isolated Vultr sandboxes and measure how often it agrees with itself.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${archivo.variable} ${dmMono.variable}`}>
      <body>
        <div className="grid min-h-dvh grid-cols-1 bg-ink desk:grid-cols-[200px_1fr]">
          <Rail />
          <main className="min-w-0 bg-paper px-4 pt-[22px] pb-10 sm:px-5">{children}</main>
        </div>
      </body>
    </html>
  );
}
