#!/bin/sh
set -e

# uploads_data/secure_uploads_data are Docker-managed named volumes — they
# mount fresh, root-owned directories at container start, overriding
# whatever ownership the image set at build time. Fix it here, as root,
# before dropping privileges, so uploads/document downloads don't fail with
# permission errors under the non-root user the app actually runs as.
mkdir -p /app/uploads /app/secure_uploads
chown -R appuser:appuser /app/uploads /app/secure_uploads

exec gosu appuser "$@"
