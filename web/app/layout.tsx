import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Evidrai',
  description: 'Claim-level evidence assessment',
  icons: {
    icon: '/brand/evidrai-icon.png',
    apple: '/brand/evidrai-icon.png',
  },
  openGraph: {
    title: 'Evidrai',
    description: 'Claim-level evidence assessment',
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
