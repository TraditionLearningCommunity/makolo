import 'destination.dart';

class DeepLinkResolver {
  const DeepLinkResolver();

  String? resolve(StructuredDestination target) {
    switch (target.kind) {
      case 'Journey':
        return '/journeys/${target.id}';
      case 'Activity':
        return '/activities/${target.id}';
      case 'Occurrence':
        return '/occurrences/${target.id}';
      case 'Access':
        return '/accesses/${target.id}';
      case 'Dossier':
        return '/dossiers/${target.id}';
      case 'Project':
        return '/projects/${target.id}';
      case 'Group':
        return '/groups/${target.id}';
      default:
        return null;
    }
  }
}
