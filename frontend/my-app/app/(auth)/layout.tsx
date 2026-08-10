import Link from 'next/link';

export default function AuthLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="flex min-h-screen flex-col bg-[#15101C]">
      <header className="border-b border-[#332844] px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Link href="/login" className="font-serif text-xl text-[#F5EFE9]">
            matcha
          </Link>
          <nav className="flex gap-4 text-sm text-[#9C8FA8]" aria-label="Authentication">
            <Link href="/login" className="hover:text-[#F5EFE9]">Log in</Link>
            <Link href="/signup" className="hover:text-[#F5EFE9]">Create account</Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-[#332844] px-6 py-5 text-center text-xs text-[#6E6180]">
        <span>&copy; {new Date().getFullYear()} Matcha</span>
      </footer>
    </div>
  );
}
