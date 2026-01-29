# Web App Template - Coding Rules

> Implementation guidelines and best practices for Next.js web applications

## Table of Contents

1. [Project Structure](#project-structure)
2. [Component Guidelines](#component-guidelines)
3. [Data Fetching](#data-fetching)
4. [State Management](#state-management)
5. [Styling](#styling)
6. [API Routes](#api-routes)
7. [Database](#database)
8. [Authentication](#authentication)
9. [Error Handling](#error-handling)
10. [Testing](#testing)
11. [Security](#security)
12. [Performance](#performance)

---

## Project Structure

### Directory Organization

```
app/
├── (auth)/                 # Route groups (no URL impact)
├── api/                    # API routes only
├── [slug]/                 # Dynamic routes
└── page.tsx                # Page components only

components/
├── ui/                     # Primitive, reusable UI components
├── features/               # Feature-specific components
└── layouts/                # Layout components

lib/
├── db.ts                   # Database client (singleton)
├── auth.ts                 # Auth configuration
├── utils.ts                # Pure utility functions
└── validations/            # Zod schemas
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Components | PascalCase | `UserCard.tsx` |
| Utilities | camelCase | `formatDate.ts` |
| Constants | SCREAMING_SNAKE | `API_BASE_URL` |
| Types | PascalCase | `UserProfile` |
| Files | kebab-case or PascalCase | `user-card.tsx` |
| CSS Modules | camelCase | `styles.container` |

---

## Component Guidelines

### Server vs Client Components

```tsx
// ✅ DEFAULT: Server Component (no directive needed)
async function ProductList() {
  const products = await db.product.findMany()
  return <ul>{products.map(p => <ProductItem key={p.id} product={p} />)}</ul>
}

// ✅ CLIENT: Only when needed (interactivity)
"use client"

import { useState } from 'react'

function Counter() {
  const [count, setCount] = useState(0)
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>
}
```

### When to Use Client Components

Use `"use client"` only for:
- Event handlers (onClick, onChange, etc.)
- useState, useEffect, useReducer
- Browser-only APIs (localStorage, window)
- Third-party libraries that require client

### Component Structure

```tsx
// ✅ Recommended component structure
import { type ComponentProps } from 'react'

// Types first
interface ButtonProps extends ComponentProps<'button'> {
  variant?: 'primary' | 'secondary'
  isLoading?: boolean
}

// Component
export function Button({
  variant = 'primary',
  isLoading = false,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(styles[variant], isLoading && styles.loading)}
      disabled={isLoading}
      {...props}
    >
      {isLoading ? <Spinner /> : children}
    </button>
  )
}
```

### Props Guidelines

```tsx
// ✅ Good: Destructure with defaults
function Card({ title, children, className = '' }: CardProps) {
  // ...
}

// ❌ Bad: Access props.x everywhere
function Card(props) {
  return <div className={props.className}>{props.title}</div>
}
```

---

## Data Fetching

### Server Components (Preferred)

```tsx
// ✅ Direct database access in Server Components
async function UserProfile({ userId }: { userId: string }) {
  const user = await db.user.findUnique({ where: { id: userId } })

  if (!user) return notFound()

  return <ProfileCard user={user} />
}
```

### API Routes for Client Components

```tsx
// ✅ Use API routes when client needs data
"use client"

import useSWR from 'swr'

function UserList() {
  const { data, error, isLoading } = useSWR('/api/users', fetcher)

  if (isLoading) return <Skeleton />
  if (error) return <Error message={error.message} />

  return <ul>{data.users.map(user => <UserItem key={user.id} user={user} />)}</ul>
}
```

### Caching Strategy

```tsx
// ✅ Configure caching per fetch
const data = await fetch(url, {
  next: {
    revalidate: 60,        // Revalidate every 60 seconds
    tags: ['products']     // Tag for on-demand revalidation
  }
})

// Force dynamic
export const dynamic = 'force-dynamic'

// Force static
export const revalidate = false
```

---

## State Management

### Hierarchy

1. **URL State** (searchParams) - for shareable state
2. **Server State** (React Query/SWR) - for API data
3. **Local State** (useState) - for UI state
4. **Context** (useContext) - for global UI state (theme, auth)

### URL State (Preferred for filters/pagination)

```tsx
// ✅ Use URL for shareable state
import { useSearchParams } from 'next/navigation'

function ProductFilters() {
  const searchParams = useSearchParams()
  const category = searchParams.get('category')

  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams)
    params.set(key, value)
    router.push(`?${params.toString()}`)
  }

  return (
    <Select value={category} onChange={v => updateFilter('category', v)}>
      {/* options */}
    </Select>
  )
}
```

### Form State

```tsx
// ✅ Use react-hook-form + zod
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { userSchema, type UserInput } from '@/lib/validations/user'

function UserForm() {
  const form = useForm<UserInput>({
    resolver: zodResolver(userSchema),
    defaultValues: { name: '', email: '' }
  })

  const onSubmit = async (data: UserInput) => {
    await createUser(data)
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <Input {...form.register('name')} error={form.formState.errors.name?.message} />
      <Input {...form.register('email')} error={form.formState.errors.email?.message} />
      <Button type="submit" isLoading={form.formState.isSubmitting}>Save</Button>
    </form>
  )
}
```

---

## Styling

### Tailwind CSS (Primary)

```tsx
// ✅ Use Tailwind utility classes
function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-card p-6 shadow-sm">
      {children}
    </div>
  )
}

// ✅ Use cn() utility for conditional classes
import { cn } from '@/lib/utils'

function Button({ variant, className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'rounded-md px-4 py-2 font-medium',
        variant === 'primary' && 'bg-primary text-white',
        variant === 'secondary' && 'bg-secondary text-black',
        className
      )}
      {...props}
    />
  )
}
```

### CSS Modules (When needed)

```tsx
// For complex, component-specific styles
import styles from './complex-component.module.css'

function ComplexComponent() {
  return <div className={styles.container}>{/* ... */}</div>
}
```

### Forbidden Patterns

```tsx
// ❌ NEVER: Inline styles for layout
<div style={{ marginTop: 20, display: 'flex' }}>

// ❌ NEVER: CSS-in-JS (styled-components, emotion)
const Button = styled.button`
  background: blue;
`

// ❌ NEVER: !important in Tailwind
className="text-red-500 !important"
```

---

## API Routes

### Route Handler Structure

```typescript
// app/api/users/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'
import { db } from '@/lib/db'
import { getServerSession } from 'next-auth'

// Schema for input validation
const createUserSchema = z.object({
  name: z.string().min(2),
  email: z.string().email()
})

// GET /api/users
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const page = parseInt(searchParams.get('page') || '1')
    const limit = parseInt(searchParams.get('limit') || '10')

    const users = await db.user.findMany({
      skip: (page - 1) * limit,
      take: limit
    })

    return NextResponse.json({ users, page, limit })
  } catch (error) {
    console.error('GET /api/users error:', error)
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    )
  }
}

// POST /api/users
export async function POST(request: NextRequest) {
  try {
    // Auth check
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Validate input
    const body = await request.json()
    const result = createUserSchema.safeParse(body)

    if (!result.success) {
      return NextResponse.json(
        { error: 'Validation failed', details: result.error.flatten() },
        { status: 400 }
      )
    }

    // Create user
    const user = await db.user.create({ data: result.data })

    return NextResponse.json(user, { status: 201 })
  } catch (error) {
    console.error('POST /api/users error:', error)
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    )
  }
}
```

### Dynamic Route Handlers

```typescript
// app/api/users/[id]/route.ts
import { NextRequest, NextResponse } from 'next/server'

type Params = { params: { id: string } }

export async function GET(request: NextRequest, { params }: Params) {
  const user = await db.user.findUnique({ where: { id: params.id } })

  if (!user) {
    return NextResponse.json({ error: 'User not found' }, { status: 404 })
  }

  return NextResponse.json(user)
}

export async function DELETE(request: NextRequest, { params }: Params) {
  await db.user.delete({ where: { id: params.id } })
  return new NextResponse(null, { status: 204 })
}
```

---

## Database

### Prisma Client Singleton

```typescript
// lib/db.ts
import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient }

export const db = globalForPrisma.prisma || new PrismaClient({
  log: process.env.NODE_ENV === 'development' ? ['query'] : []
})

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = db
}
```

### Schema Best Practices

```prisma
// prisma/schema.prisma

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String?
  posts     Post[]
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  @@index([email])
}

model Post {
  id        String   @id @default(cuid())
  title     String
  content   String?
  published Boolean  @default(false)
  author    User     @relation(fields: [authorId], references: [id], onDelete: Cascade)
  authorId  String
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  @@index([authorId])
}
```

### Query Patterns

```typescript
// ✅ Select only needed fields
const users = await db.user.findMany({
  select: { id: true, name: true, email: true }
})

// ✅ Use transactions for multiple operations
await db.$transaction([
  db.user.delete({ where: { id: userId } }),
  db.post.deleteMany({ where: { authorId: userId } })
])

// ✅ Use pagination
const users = await db.user.findMany({
  skip: (page - 1) * pageSize,
  take: pageSize,
  orderBy: { createdAt: 'desc' }
})
```

---

## Authentication

### NextAuth.js Configuration

```typescript
// lib/auth.ts
import { NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'
import { db } from './db'
import { compare } from 'bcryptjs'

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' }
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null
        }

        const user = await db.user.findUnique({
          where: { email: credentials.email }
        })

        if (!user || !user.password) {
          return null
        }

        const isValid = await compare(credentials.password, user.password)

        if (!isValid) {
          return null
        }

        return { id: user.id, email: user.email, name: user.name }
      }
    })
  ],
  session: { strategy: 'jwt' },
  pages: {
    signIn: '/login',
    error: '/auth/error'
  }
}
```

### Protected Routes

```typescript
// middleware.ts
import { withAuth } from 'next-auth/middleware'

export default withAuth({
  pages: { signIn: '/login' }
})

export const config = {
  matcher: ['/dashboard/:path*', '/api/protected/:path*']
}
```

---

## Error Handling

### Error Boundaries

```tsx
// app/error.tsx
"use client"

export default function Error({
  error,
  reset
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h2 className="text-2xl font-bold">Something went wrong!</h2>
      <p className="text-muted-foreground">{error.message}</p>
      <button onClick={reset} className="mt-4 btn">Try again</button>
    </div>
  )
}
```

### Not Found Pages

```tsx
// app/not-found.tsx
export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h2 className="text-4xl font-bold">404</h2>
      <p className="text-muted-foreground">Page not found</p>
    </div>
  )
}
```

---

## Testing

### Component Testing

```tsx
// __tests__/components/Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { Button } from '@/components/ui/button'

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText('Click me')).toBeInTheDocument()
  })

  it('calls onClick when clicked', () => {
    const handleClick = jest.fn()
    render(<Button onClick={handleClick}>Click</Button>)
    fireEvent.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when isLoading', () => {
    render(<Button isLoading>Loading</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })
})
```

### E2E Testing with Playwright

```typescript
// e2e/auth.spec.ts
import { test, expect } from '@playwright/test'

test('user can log in', async ({ page }) => {
  await page.goto('/login')

  await page.fill('input[name="email"]', 'test@example.com')
  await page.fill('input[name="password"]', 'password123')
  await page.click('button[type="submit"]')

  await expect(page).toHaveURL('/dashboard')
  await expect(page.locator('h1')).toContainText('Dashboard')
})
```

---

## Security

### Input Validation

```typescript
// Always validate on server side
import { z } from 'zod'

const userSchema = z.object({
  email: z.string().email(),
  name: z.string().min(2).max(100),
  age: z.number().int().min(0).max(150)
})

// In API route
const result = userSchema.safeParse(body)
if (!result.success) {
  return NextResponse.json({ error: result.error }, { status: 400 })
}
```

### XSS Prevention

```tsx
// ✅ React automatically escapes
<p>{userInput}</p>

// ❌ NEVER use dangerouslySetInnerHTML with user input
<div dangerouslySetInnerHTML={{ __html: userInput }} />
```

### CSRF Protection

NextAuth.js handles CSRF automatically for auth routes.

---

## Performance

### Image Optimization

```tsx
import Image from 'next/image'

// ✅ Always use next/image
<Image
  src="/hero.jpg"
  alt="Hero"
  width={1200}
  height={600}
  priority  // For above-fold images
/>
```

### Code Splitting

```tsx
import dynamic from 'next/dynamic'

// ✅ Dynamic import for heavy components
const Chart = dynamic(() => import('@/components/Chart'), {
  loading: () => <Skeleton />,
  ssr: false  // If component uses browser APIs
})
```

### Metadata

```tsx
// app/layout.tsx
export const metadata = {
  title: {
    default: 'My App',
    template: '%s | My App'
  },
  description: 'My awesome application'
}
```

---

*These rules ensure consistency, maintainability, and performance across the application.*