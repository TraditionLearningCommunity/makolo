#!/bin/sh
# Lot 7 validation gate for Makolo Conversations on the current checkout.
# No deploy, no data mutation: run against a disposable development/test DB.
# Usage: VERIFY_MOBILE=0 sh scripts/verify_conversations_lot7.sh
set -eu

if [ ! -f manage.py ]; then
  echo "Run this from the Makolo repository root." >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-python}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python runtime unavailable." >&2
  exit 2
fi

echo "== Django system checks =="
"$PYTHON_BIN" manage.py check

echo "== Additive migration consistency and plan =="
"$PYTHON_BIN" manage.py makemigrations conversations questionnaires --check --dry-run
"$PYTHON_BIN" manage.py migrate --plan

echo "== Conversation/Questionnaire/Notification regression tests =="
"$PYTHON_BIN" manage.py test \
  conversations.test_lot7_closure \
  conversations.test_j7_contracts \
  conversations.test_j7_hardening \
  conversations.test_j6_forms \
  conversations.test_c3_typed_media \
  conversations.test_c4_rich \
  conversations.test_c5_mature \
  conversations.test_m9c_performance \
  questionnaires.test_lot7_media \
  notifications.test_domain_events \
  -v 2

echo "== First-party Web gallery/composer syntax =="
if ! command -v node >/dev/null 2>&1; then
  echo "Node unavailable: Web syntax gate cannot be skipped." >&2
  exit 2
fi
for script in \
  static/js/conversations-media-gallery.js \
  static/js/conversations-identity-picker.js \
  static/js/conversations-rich-composer.js \
  static/js/conversations-semantic-composer.js
do
  node --check "$script"
done

if [ "${VERIFY_MOBILE:-1}" = "1" ]; then
  if ! command -v dart >/dev/null 2>&1 || ! command -v flutter >/dev/null 2>&1; then
    echo "Dart/Flutter unavailable: use a Flutter SDK runner for Lot 7." >&2
    exit 2
  fi
  echo "== Flutter format, analysis and widget tests =="
  (
    cd mobile
    dart format --output=none --set-exit-if-changed \
      lib/features/continuity/conversation_attachment_viewer.dart \
      lib/features/continuity/conversation_screens.dart \
      lib/features/continuity/conversation_details_screen.dart \
      lib/notifications/notification_router.dart \
      test/notification_router_test.dart \
      test/conversation_lot7_media_cleanup_test.dart
    flutter analyze \
      lib/features/continuity \
      lib/notifications \
      test/notification_router_test.dart \
      test/conversation_lot7_media_cleanup_test.dart
    flutter test \
      test/notification_router_test.dart \
      test/conversation_lot7_media_cleanup_test.dart \
      test/conversation_mature_repository_test.dart \
      test/conversation_c5_mature_test.dart \
      test/conversation_details_screen_test.dart
  )
else
  echo "Mobile checks explicitly skipped (VERIFY_MOBILE=0)."
fi

echo "Lot 7 targeted gates passed locally; manual Web/Android smoke tests and"
echo "PR CI approval/review remain separately required before merge."
