import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Evidrai',
  description: 'Claim-level evidence assessment',
  icons: {
    icon: [
      { url: '/brand/evidrai-icon.png', media: '(prefers-color-scheme: light)' },
      { url: '/brand/evidrai-icon-dark.png', media: '(prefers-color-scheme: dark)' },
    ],
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
