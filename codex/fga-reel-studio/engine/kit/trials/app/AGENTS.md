# Trials Project Instructions

- The UI lives in `src/pane/` (Tailwind v4) over one engine, `src/useTrialr.js`. It copies Brainfile's UI: canvas sidebar, floating list and detail panels, sliding highlight and segmented control on Arc's spring, Geist / Inter / Source Serif / JetBrains Mono. Tokens live at the top of `src/pane/pane.css`: green (`--lead`) marks the leader on every bar, gold (`--gold`) marks a picked winner. Preserve that system.
- Keep the Zernio API key server-side. Never expose it in client code, logs, screenshots, or commits.
- Inside Reel Kit (installed by `/reel-kit:trials` into `~/reel-kit/trials/app`), the key lives in `~/reel-kit/trials/.env`, next to the history. Never write a key into the app folder or move it out of that file. Changes the creator asks for go straight into the app folder: Reel Kit updates keep any file they changed.
- Never commit `.env` or test history. History lives outside the app at `~/reel-kit/trials/` (`TRIALS_DATA_DIR` overrides) with daily backups in `backups/`, so app updates can't wipe it. Never move it back inside the app folder.
- Do not publish a real Reel during setup, testing, or debugging without the user's explicit confirmation.
- Run `npm test` and `npm run build` after code changes.
- Keep local experiment persistence backward-compatible unless a migration is included.
- Light, System, and Dark appearance modes must remain functional.
- Publishing always takes two clicks (Publish, then Publish now). Never remove the confirm step.
- Deleting a test or version only removes it from Trials. The confirm dialog must say the posts stay on Instagram.
