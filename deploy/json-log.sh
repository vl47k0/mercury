#!/bin/sh

STAGE="$1"
shift

"$@" 2>&1 | while IFS= read -r line; do

  [ -z "$line" ] && continue

  case "$line" in
    \{*) echo "$line" ;;
    *) printf '{"time":"%s","level":"INFO","logger":"entrypoint","message":"%s","stage":"%s"}\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%S)" \
      "$(echo "$line" | sed 's/\\/\\\\/g; s/"/\\"/g')" \
      "$STAGE" ;;
  esac
done

EXIT_CODE=${PIPESTATUS:-$?}
if [ "$EXIT_CODE" != "0" ]; then
  printf '{"time":"%s","level":"ERROR","logger":"entrypoint","message":"exited with code %s","stage":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%S)" "$EXIT_CODE" "$STAGE"
fi
exit "$EXIT_CODE"
