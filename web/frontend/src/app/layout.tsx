import "./globals.css";
import type { Metadata } from "next";
import { MethodologyProvider } from "@/components/MethodologyDrawer";

export const metadata: Metadata = {
  title: "SurveySparrow SE Coach",
  description: "Demo performance & coaching portal for Solution Engineers",
  icons: {
    icon: [
      { url: "/logo.svg", type: "image/svg+xml" },
    ],
    shortcut: "/logo.svg",
    apple: "/logo.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <MethodologyProvider>
          {children}
        </MethodologyProvider>
      </body>
    </html>
  );
}
