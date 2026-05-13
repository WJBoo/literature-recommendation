import type { Metadata } from "next";
import type { ReactNode } from "react";
import { GlobalListeningPlayer } from "../components/GlobalListeningPlayer";
import "./globals.css";

export const metadata: Metadata = {
  title: "Linguaphilia",
  description: "Personalized literary discovery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
        <GlobalListeningPlayer />
      </body>
    </html>
  );
}
