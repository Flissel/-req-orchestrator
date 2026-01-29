export default function Home() {
  // PROJECT_NAME wird durch import_template.py ersetzt
  const projectName = "my-project"

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          Welcome to <span className="text-primary">{projectName}</span>
        </h1>
        <p className="mt-6 text-lg leading-8 text-muted-foreground">
          Built with Next.js 14, Tailwind CSS, and Prisma
        </p>
        <div className="mt-10 flex items-center justify-center gap-x-6">
          <a
            href="/dashboard"
            className="rounded-md bg-primary px-3.5 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            Get Started
          </a>
          <a
            href="https://nextjs.org/docs"
            className="text-sm font-semibold leading-6 text-foreground"
            target="_blank"
            rel="noopener noreferrer"
          >
            Documentation <span aria-hidden="true">→</span>
          </a>
        </div>
      </div>
    </main>
  )
}