#!/bin/sh
set -eu

if [ "${ENABLE_QIDIAN:-false}" = "true" ]; then
  scrapy crawl qidian_trends
else
  echo "Skip qidian_trends because ENABLE_QIDIAN is not true."
fi

scrapy crawl zongheng_trends
