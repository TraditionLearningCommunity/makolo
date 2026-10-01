import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../navigation/secondary_screen.dart';
import 'access_credential_screen.dart';
import 'access_detail_screen.dart';

List<RouteBase> accessRoutes(AppRuntime runtime) => [
  GoRoute(
    path: '/accesses/:id',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.accesses;
      if (repository == null) {
        return const MakoloSecondaryScreen(
          title: 'Accès',
          message: 'Cet accès n’est pas disponible sur cet appareil.',
        );
      }
      return AccessDetailScreen(
        accessId: state.pathParameters['id']!,
        repository: repository,
        onOpenDayOf: (handoff) =>
            context.push('/occurrences/${handoff.occurrenceId}/day-of'),
        onOpenJourney: (journeyId) => context.push('/journeys/$journeyId'),
      );
    },
  ),
  GoRoute(
    path: '/accesses/:id/credential',
    builder: (context, state) {
      runtime.recovery.rememberLocation(state.uri.toString());
      final repository = runtime.accesses;
      final credentialPath = state.extra is String
          ? state.extra! as String
          : null;
      if (repository == null || credentialPath == null) {
        return const MakoloSecondaryScreen(
          title: 'QR d’accès',
          message: 'Rouvrez ce QR depuis le Jour J afin de revalider son lien propriétaire.',
        );
      }
      return AccessCredentialScreen(
        accessId: state.pathParameters['id']!,
        credentialPath: credentialPath,
        repository: repository,
      );
    },
  ),
];
