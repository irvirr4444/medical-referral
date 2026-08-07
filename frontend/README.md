# WCW Referral Automation — Demo Dashboard

Frontend-only executive demonstration for West Coast Wound.

## Run

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173/](http://localhost:5173/).

## Scripts

- `npm run dev` — local demo server
- `npm run build` — production build
- `npm test` — Vitest unit/UI smoke tests
- `npm run lint` — Oxlint

## Notes

- All dashboard metrics and patient records are fictional/illustrative.
- The seven PDFs in `../samples/` are served only through allowlisted `/referrals/...` routes.
- No production Outlook, Monday.com, DRK, or credential integrations are used.
