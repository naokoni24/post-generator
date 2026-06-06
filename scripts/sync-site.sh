#!/usr/bin/env sh
set -eu

mkdir -p site/images site/assets site/js

cp index.html privacy.html commercial.html site/
cp favicon.svg _headers site/
cp robots.txt sitemap.xml site/
cp assets/wanko_ai.pdf assets/search_ai.pdf site/assets/
cp js/contact-links.js site/js/

cp \
  images/tail-tech-word-a.png \
  images/dog-event-hiyori.jpg \
  images/dog-event-service-generated-thumb.jpg \
  images/service_ai_search_knowledge_thumb.png \
  images/service_dx_highres.png \
  images/service_system_dev_highres.png \
  images/cost-navy-final-thick.png \
  images/case_pet_ai_event_photo.png \
  images/case_ai_search_highres.png \
  images/case_line_highres.png \
  images/case_system_highres.png \
  images/profile-temp-selected.png \
  site/images/
