# WCW Referral Automation - Inspection Console

Frontend-only workflow inspection experience for West Coast Wound. It explains stages 1-7,
their microsteps, example inputs and outputs, validation rules, and human-control points.

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
- The complete and missing-information runs are deterministic walkthrough fixtures.
- Step feedback is stored in browser state only. A functional version will persist it by run and
  microstep through the authenticated backend.
- Legacy analytics and patient-scenario components remain in the repository but are not rendered in
  the primary inspection experience.
