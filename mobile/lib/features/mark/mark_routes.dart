import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import 'mark_screen.dart';

List<RouteBase> markRoutes(
  AppRuntime runtime, {
  VoidCallback? onSwitchAccount,
  VoidCallback? onLogout,
}) => [
  GoRoute(
    path: '/mark',
    builder: (context, state) {
      final query = state.uri.queryParameters;
      final kind = query['selected_kind'];
      final id = query['selected_id'];
      final family = query['selected_family'];
      return MarkScreen(
        runtime: runtime,
        onSwitchAccount: onSwitchAccount,
        onLogout: onLogout,
        selectedContext: kind == null || id == null
            ? null
            : {
                'kind': kind,
                'id': id,
                if (family != null && family.isNotEmpty) 'family': family,
              },
      );
    },
  ),
];
