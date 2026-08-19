# PYF

Print Your Fit is a static single-page web app for generating AI-assisted sewing pattern concepts, fitting them to body measurements, and exporting a printable tiled PDF.

## Local development

```bash
npm install
npm run dev
```

## Production build

```bash
npm run build
npm run preview
```

## Deployment readiness

- Vite build pipeline configured for static hosting
- Service worker enabled for offline shell caching
- Manifest configured for PWA installability
- Output is generated to the `dist/` folder for hosting on Netlify, Vercel, Azure Static Web Apps, or any static host

## Notes

The app is front-end only and designed for static hosting. Add API integration or a backend when you want real AI pattern generation, user accounts, and payments.
