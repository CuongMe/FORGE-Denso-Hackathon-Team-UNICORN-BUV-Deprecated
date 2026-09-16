import type { Metadata } from "next";
import "./globals.css";
import "./forge-theme.css";
import "./forge-workspaces.css";

export const metadata: Metadata = {
  title: "FORGE | Factory operations intelligence",
  description: "Grounded retrieval across factory documents.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
