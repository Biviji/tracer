import type { Metadata } from "next";
import { Archivo, DM_Mono } from "next/font/google";
import { Suspense } from "react";
import "lenis/dist/lenis.css";
import "./globals.css";
import { SmoothScroll } from "@/components/motion/SmoothScroll";

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
    "Find out if you can trust a coding agent, and which model to pay for: TRACE runs the same task N times in isolated Vultr sandboxes on your own repo.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${archivo.variable} ${dmMono.variable}`}>
      <body>
        <Suspense fallback={null}>
          <SmoothScroll />
        </Suspense>
        {children}
      </body>
    </html>
  );
}
