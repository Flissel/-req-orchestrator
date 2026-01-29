# Web App Template - Follow Guide

> Step-by-step instructions to use this template

## Prerequisites

Before starting, ensure you have:

- [ ] Docker Desktop installed and running
- [ ] Node.js 18+ installed (optional for local development)
- [ ] Git installed

## Quick Start (5 minutes)

### Step 1: Import Template

```bash
# From the project root
python templates/tools/import_template.py 01-web-app my-webapp

# Or with custom output path
python templates/tools/import_template.py 01-web-app my-webapp --output ./projects/
```

### Step 2: Navigate to Project

```bash
cd my-webapp
```

### Step 3: Start Docker Services

```bash
# Start PostgreSQL database
docker-compose up -d

# Wait for database to be ready (~10 seconds)
```

### Step 4: Install Dependencies

```bash
npm install
```

### Step 5: Setup Database

```bash
# Generate Prisma client
npx prisma generate

# Run migrations
npx prisma migrate dev --name init

# (Optional) Seed database
npx prisma db seed
```

### Step 6: Start Development Server

```bash
npm run dev
```

### Step 7: Open in Browser

Navigate to: **http://localhost:3000**

---

## Project Structure After Import

```
my-webapp/
├── app/                      # Next.js App Router
│   ├── layout.tsx            # Root layout
│   ├── page.tsx              # Homepage
│   ├── globals.css           # Global styles
│   ├── (auth)/               # Auth route group
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   └── api/                  # API routes
│       ├── auth/[...nextauth]/route.ts
│       └── users/route.ts
├── components/
│   ├── ui/                   # Primitive UI components
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   └── card.tsx
│   └── features/             # Feature components
│       └── header.tsx
├── lib/
│   ├── db.ts                 # Prisma client
│   ├── auth.ts               # Auth configuration
│   └── utils.ts              # Utility functions
├── prisma/
│   ├── schema.prisma         # Database schema
│   └── seed.ts               # Seed script
├── public/                   # Static assets
├── docs/
│   └── requirements/         # Requirements documentation
├── .env.example              # Environment template
├── docker-compose.yml        # Docker services
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── README.md
```

---

## Common Tasks

### Adding a New Page

1. Create file in `app/` directory:
   ```bash
   mkdir -p app/dashboard
   touch app/dashboard/page.tsx
   ```

2. Add page component:
   ```tsx
   export default function DashboardPage() {
     return <div>Dashboard</div>
   }
   ```

3. Access at: `http://localhost:3000/dashboard`

### Adding a New API Route

1. Create route handler:
   ```bash
   mkdir -p app/api/products
   touch app/api/products/route.ts
   ```

2. Implement handler:
   ```typescript
   import { NextResponse } from 'next/server'

   export async function GET() {
     return NextResponse.json({ products: [] })
   }
   ```

### Adding a Database Model

1. Edit `prisma/schema.prisma`:
   ```prisma
   model Product {
     id        String   @id @default(cuid())
     name      String
     price     Float
     createdAt DateTime @default(now())
   }
   ```

2. Run migration:
   ```bash
   npx prisma migrate dev --name add_product
   ```

3. Use in code:
   ```typescript
   import { db } from '@/lib/db'
   const products = await db.product.findMany()
   ```

### Adding Authentication

1. Configure providers in `lib/auth.ts`
2. Protect routes with middleware
3. Use `useSession()` hook in components

---

## Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/db` |
| `NEXTAUTH_SECRET` | Auth encryption key | `your-secret-key` |
| `NEXTAUTH_URL` | App URL | `http://localhost:3000` |

---

## Deployment

### Option 1: Vercel (Recommended)

1. Push to GitHub
2. Import in Vercel
3. Add environment variables
4. Deploy

### Option 2: Docker

```bash
# Build production image
docker build -t my-webapp .

# Run container
docker run -p 3000:3000 my-webapp
```

---

## Troubleshooting

### Database Connection Failed

```bash
# Check if PostgreSQL is running
docker-compose ps

# Restart database
docker-compose restart db

# Check logs
docker-compose logs db
```

### Prisma Client Not Generated

```bash
npx prisma generate
```

### Port Already in Use

```bash
# Find process using port 3000
npx kill-port 3000

# Or use different port
npm run dev -- -p 3001
```

---

## Next Steps

1. [ ] Review `CODING_RULES.md` for implementation guidelines
2. [ ] Check `docs/requirements/` for project requirements
3. [ ] Customize the UI in `components/ui/`
4. [ ] Add your business logic in `app/api/`
5. [ ] Deploy to production

---

*Template Version: 1.0.0*
*Last Updated: 2024*