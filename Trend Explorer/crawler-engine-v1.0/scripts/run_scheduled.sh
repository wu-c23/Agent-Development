#!/bin/sh
set -eu

interval_hours="${CRAWL_INTERVAL_HOURS:-72}"
interval_seconds=$((interval_hours * 3600))

while true; do
  date -u +"[%Y-%m-%dT%H:%M:%SZ] start scheduled crawl"
  scrapy crawl qidian_trends || true
  scrapy crawl zongheng_trends || true
  date -u +"[%Y-%m-%dT%H:%M:%SZ] crawl finished, sleep ${interval_hours}h"
  sleep "${interval_seconds}"
done
