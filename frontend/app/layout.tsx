import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-inter',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Scheme Sarathi — Find Government Schemes You Qualify For',
  description:
    'AI-powered eligibility matching across 3,397 central and state government schemes for Indian citizens.',
  keywords: ['government schemes', 'India', 'eligibility', 'welfare', 'benefits'],
  openGraph: {
    title: 'Scheme Sarathi',
    description: 'Find government schemes you qualify for',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-gray-50 font-sans antialiased">
        {children}
      </body>
    </html>
  )
}
