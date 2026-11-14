import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../presentation/contracts/space_presentation.dart';

/// MT7: only native owner destinations with a verified server handoff.
/// The API URL is evidence of a handoff, never a route to open blindly.
/// Each destination rechecks the current actor, permissions and owner.
class SpaceWorkOwnerActions extends StatelessWidget {
  const SpaceWorkOwnerActions({
    super.key,
    required this.slug,
    required this.sourceKind,
    required this.sourceId,
    required this.archetype,
    required this.handoffs,
    this.canOpenDayOf = false,
  });

  final String slug;
  final String sourceKind;
  final String sourceId;
  final String? archetype;
  final List<dynamic> handoffs;
  final bool canOpenDayOf;

  @override
  Widget build(BuildContext context) {
    final actions = <_NativeHandoff>[];
    final seen = <String>{};
    for (final raw in handoffs) {
      final item = spaceMap(raw);
      if (item?['channel'] != 'api') continue;
      final intent = spaceText(item?['intent']);
      final owner = spaceMap(item?['owner']);
      final id = spaceText(owner?['id']);
      final kind = spaceText(owner?['kind']);
      final url = spaceText(item?['url']);
      if (intent == null || id == null || url == null) continue;
      final ownerUrl = Uri.tryParse(url);
      // An API URL is not itself authority. Match the *exact* server owner
      // destination instead of accepting an arbitrary path containing an id.
      // Each native screen still revalidates the active actor and permissions.
      final spacePart = Uri.encodeComponent(slug);
      final idPart = Uri.encodeComponent(id);
      final expectedPath = switch (intent) {
        'open_request' =>
          '/api/v1/organizations/workspaces/$spacePart/requests/$idPart/',
        'open_service_case_native' =>
          '/api/v1/organizations/workspaces/$spacePart/work/service-cases/$idPart/',
        'open_day_of' => '/api/v1/operations/occurrences/$idPart/day-of/',
        _ => null,
      };
      if (ownerUrl == null ||
          ownerUrl.hasScheme ||
          ownerUrl.hasAuthority ||
          expectedPath == null ||
          ownerUrl.path != expectedPath) {
        continue;
      }
      String? route;
      String? title;
      IconData? icon;
      if (intent == 'open_request' &&
          sourceKind == 'journey' &&
          kind == 'journey_request') {
        title = 'Examiner la demande';
        icon = Icons.fact_check_outlined;
        route = '/space/requests/${Uri.encodeComponent(id)}';
      } else if (intent == 'open_service_case_native' &&
          sourceKind == 'journey' &&
          archetype == 'service_provider' &&
          kind == 'journey' &&
          id == sourceId) {
        title = 'Suivre le dossier de prestation';
        icon = Icons.work_outline;
        route =
            '/space/${Uri.encodeComponent(slug)}'
            '/services/cases/${Uri.encodeComponent(id)}';
      } else if (intent == 'open_day_of' &&
          canOpenDayOf &&
          sourceKind == 'occurrence' &&
          kind == 'occurrence' &&
          id == sourceId) {
        title = 'Jour J';
        icon = Icons.play_circle_outline;
        route = '/space/occurrences/${Uri.encodeComponent(id)}/day-of';
      }
      if (route == null || title == null || icon == null || !seen.add(route)) {
        continue;
      }
      actions.add(_NativeHandoff(title: title, route: route, icon: icon));
    }
    if (actions.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 16, bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: Text(
              'Actions disponibles',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          for (final action in actions)
            ListTile(
              leading: Icon(action.icon),
              title: Text(action.title),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push(action.route),
            ),
        ],
      ),
    );
  }
}

class _NativeHandoff {
  const _NativeHandoff({
    required this.title,
    required this.route,
    required this.icon,
  });

  final String title;
  final String route;
  final IconData icon;
}
