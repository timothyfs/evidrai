import type { Metadata } from 'next';
import './globals.css';
import SiteFooter from './components/SiteFooter';

export const metadata: Metadata = {
  title: 'Evidrai',
  description: 'Claim-level evidence assessment',
  icons: {
    icon: [
      { url: '/brand/evidrai-eye-light.png', media: '(prefers-color-scheme: light)' },
      { url: '/brand/evidrai-eye-dark.png', media: '(prefers-color-scheme: dark)' },
    ],
    apple: '/brand/evidrai-eye-light.png',
  },
  openGraph: {
    title: 'Evidrai',
    description: 'Claim-level evidence assessment',
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}<SiteFooter /></body>
    </html>
  );
}
