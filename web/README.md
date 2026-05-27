# SE Coach Portal — Frontend + Backend

```
web/
├── backend/           FastAPI + SQLAlchemy + JWT auth
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, router mount
│   │   ├── auth.py             # bcrypt hashing + JWT issuance
│   │   ├── deps.py             # current-user + role guards
│   │   └── routers/
│   │       ├── auth.py         # POST /auth/login, GET /auth/me
│   │       ├── calls.py        # GET /calls, GET /calls/{id}
│   │       ├── upload.py       # POST /calls/upload  (transcript validator)
│   │       └── dashboard.py    # GET /dashboard/{se|manager|ceo}
│   └── requirements.txt
│
└── frontend/          Next.js 15 (app router) + Tailwind + SWR + Chart.js
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx          # root layout
    │   │   ├── page.tsx            # / → redirect to /login or /dashboard
    │   │   ├── login/page.tsx      # email + password login
    │   │   ├── dashboard/page.tsx  # SE dashboard
    │   │   ├── upload/page.tsx     # transcript upload + validation
    │   │   ├── call/[id]/page.tsx  # per-call detail (to build)
    │   │   ├── manager/page.tsx    # team leaderboard
    │   │   └── executive/page.tsx  # CEO summary (to build)
    │   └── lib/api.ts              # fetch wrapper with bearer token
    ├── package.json
    └── tsconfig.json
```

## Run locally

```bash
# Backend
cd web/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (in a 2nd terminal)
cd web/frontend
npm install
npm run dev
# open http://localhost:3000
```

## Auth flow

1. SE enters email + password on `/login`
2. POST `/auth/login` returns a JWT (24h)
3. Token stored in `localStorage` (TODO for prod: httpOnly cookie + refresh token)
4. Every API call sends `Authorization: Bearer <token>`
5. 401 response → auto-redirect to `/login`

Role-based access via `require_role(...)` dependency: `se`, `manager`, `ceo`, `admin`.

## Production deployment

- Backend: containerize, push to ECR, deploy to ECS Fargate behind an ALB
- Frontend: `next build` → static export served from CloudFront + S3 (or
  Vercel-style server runtime on ECS / App Runner if SSR is needed)
- Auth secret: AWS Secrets Manager (env var `JWT_SECRET`)
- DB: RDS Postgres (replace the `_STUB_USERS` dict in routers/auth.py with
  SQLAlchemy queries against a `users` table)
- File uploads: stream directly to S3 (presigned URLs) instead of multipart
  through the backend for files > 5 MB

See `../docs/ARCHITECTURE.md` for the full system design.
