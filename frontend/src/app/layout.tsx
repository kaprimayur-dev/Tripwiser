import type { Metadata } from 'next'
import { Epilogue, Plus_Jakarta_Sans } from 'next/font/google'
import './globals.css'

const epilogue = Epilogue({
  subsets: ['latin'],
  variable: '--font-epilogue',
  display: 'swap',
})

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-plus-jakarta',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'TripWiser — Indian Railway Journey Intelligence',
  description: 'Find practical railway journeys across India when direct trains are unavailable.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${epilogue.variable} ${plusJakartaSans.variable}`}>
      <body className="bg-cream-100 text-espresso-900 font-sans min-h-screen antialiased selection:bg-terracotta selection:text-white">
        {children}
      </body>
    </html>
  )
}
