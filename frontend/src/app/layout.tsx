import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TripWiser — Smart Railway Journey Discovery',
  description: 'Find practical railway journeys across India when direct trains are unavailable.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-cream-100 text-espresso-900 min-h-screen antialiased selection:bg-terracotta selection:text-white">
        {children}
      </body>
    </html>
  )
}
