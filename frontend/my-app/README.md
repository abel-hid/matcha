# Matcha frontend

The Next.js frontend runs only through the root Docker Compose stack.

From the repository root:

```bash
./start.sh
```

Open `http://localhost:3000`. The container builds and runs the production Next.js output, so the browser does not receive development-only HMR or React DevTools console messages.
