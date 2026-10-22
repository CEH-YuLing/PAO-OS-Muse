#!/bin/sh
set -eu
address="${TEMPORAL_ADDRESS:-temporal:7233}"
namespace="${DEFAULT_NAMESPACE:-default}"
attempt=1
while ! temporal operator cluster health --address "$address"; do
  [ "$attempt" -lt 30 ] || exit 1
  attempt=$((attempt+1));sleep 2
done
if ! temporal operator namespace describe -n "$namespace" --address "$address" >/dev/null 2>&1; then
  temporal operator namespace create -n "$namespace" --retention 7d --address "$address"
fi
