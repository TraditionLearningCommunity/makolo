#!/usr/bin/env bash
set -euo pipefail

docs=false
design=false
app_shell=false
network=false
data=false
drift=false
sync=false
platform=false
android_native=false
ios_native=false
dependencies=false
feature=false
visual=false
ci=false
full=false
changed_file_count=0

if (($# > 0)); then
  mapfile -t paths < <(printf '%s\n' "$@")
else
  mapfile -t paths
fi

for path in "${paths[@]}"; do
  [[ -z "$path" ]] && continue
  changed_file_count=$((changed_file_count + 1))
  case "$path" in
    docs/architecture/mobile-*|mobile/README.md)
      docs=true
      ;;
    .github/workflows/mobile-*|mobile/tool/*)
      ci=true
      ;;
    mobile/pubspec.yaml|mobile/pubspec.lock|mobile/.flutter-version)
      dependencies=true
      ;;
    mobile/android/*)
      android_native=true
      ;;
    mobile/ios/*)
      ios_native=true
      ;;
    mobile/assets/*|mobile/lib/design/*|mobile/lib/*/design/*|mobile/lib/**/widgets/*|mobile/test/visual_regression_test.dart|mobile/test/goldens/*|mobile/test/goldens.sha256|mobile/test/makolo_theme_test.dart|mobile/test/makolo_mark_test.dart|mobile/test/brand_moment_test.dart|mobile/test/mark_screen_test.dart|mobile/test/shell_header_test.dart)
      design=true
      visual=true
      ;;
    mobile/lib/network/*|mobile/lib/auth/*|mobile/test/api_client_test.dart|mobile/test/account_session_test.dart)
      network=true
      ;;
    mobile/lib/data/local/*|mobile/test/local_database_test.dart|mobile/test/migration_test.dart)
      data=true
      drift=true
      ;;
    mobile/lib/data/files/*|mobile/test/file_media_core_test.dart)
      data=true
      platform=true
      ;;
    mobile/lib/sync/*|mobile/test/sync_engine_test.dart|mobile/test/outbox_processor_test.dart|mobile/test/projection_contract_test.dart)
      sync=true
      ;;
    mobile/lib/platform/*|mobile/lib/background/*|mobile/lib/observability/*|mobile/lib/navigation/incoming_intent.dart|mobile/test/background_coordinator_test.dart|mobile/test/incoming_intent_test.dart|mobile/test/observability_test.dart|mobile/test/push_signal_processor_test.dart|mobile/test/workmanager_scheduler_test.dart|mobile/test/notification_router_test.dart)
      platform=true
      ;;
    mobile/lib/app/*|mobile/lib/navigation/*|mobile/lib/notifications/*|mobile/test/app_shell_test.dart|mobile/test/auth_entry_test.dart|mobile/test/guest_router_test.dart|mobile/test/launch_gate_test.dart|mobile/test/launch_policy_test.dart|mobile/test/native_launch_contract_test.dart|mobile/test/onboarding_flow_test.dart|mobile/test/projection_screen_test.dart|mobile/test/session_recovery_test.dart|mobile/test/system_ui_test.dart|mobile/test/behavior_primitives_test.dart|mobile/test/avatar_sheet_test.dart)
      app_shell=true
      ;;
    mobile/lib/features/*|mobile/test/features/*)
      feature=true
      ;;
    mobile/lib/*|mobile/test/*)
      full=true
      ;;
    mobile/*)
      full=true
      ;;
    *)
      # Non-mobile paths are intentionally ignored here. The workflow path
      # filter prevents backend-only changes from invoking Mobile CI.
      ;;
  esac
done

core_count=0
for value in "$app_shell" "$network" "$data" "$sync" "$platform" "$feature"; do
  [[ "$value" == true ]] && core_count=$((core_count + 1))
done

flutter=false
for value in "$design" "$app_shell" "$network" "$data" "$drift" "$sync" "$platform" "$android_native" "$ios_native" "$dependencies" "$feature" "$full"; do
  if [[ "$value" == true ]]; then
    flutter=true
    break
  fi
done

codegen=$flutter
golden=$visual
android_build=false
if [[ "$dependencies" == true || "$android_native" == true || "$full" == true ]]; then
  android_build=true
fi

full_test=false
if [[ "$full" == true || "$dependencies" == true || "$feature" == true || "$core_count" -ge 3 ]]; then
  full_test=true
fi

for key in docs design app_shell network data drift sync platform android_native ios_native dependencies feature visual ci full flutter codegen golden android_build full_test changed_file_count; do
  printf '%s=%s\n' "$key" "${!key}"
done
