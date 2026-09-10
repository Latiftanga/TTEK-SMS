# Self-built Playwright screenshot tool for TTEK-SMS's dev docker-compose stack.
# Built from a plain Node base (not a pre-tagged Playwright image) so it never
# depends on guessing a matching external image tag/version — `npx playwright
# install --with-deps` pulls exactly the browser + OS libs its own installed
# `playwright` npm version needs, using ordinary apt/npm inside the build (root
# is available at build time, unlike a host dev sandbox that may lack sudo).
FROM node:22-bookworm-slim

WORKDIR /work

COPY package.json ./
RUN npm install
# Split from npm install and from each other: the OS-dep apt install is slow
# but reliable, while the browser binary download from Playwright's CDN has
# proven flaky in this environment (stalls mid-download, connection reset) —
# isolating it in its own layer means a retry only redoes the download, not
# the ~15-minute apt step too.
RUN npx playwright install-deps chromium
RUN npx playwright install chromium

COPY capture.mjs ./

ENTRYPOINT ["node", "capture.mjs"]
