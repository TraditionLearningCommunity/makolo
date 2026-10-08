import 'destination.dart';

class DeepLinkResolver {
  const DeepLinkResolver();

  String? resolve(StructuredDestination target) {
    switch (target.kind.toLowerCase()) {
      case 'occurrence_day_of':
        return '/occurrences/${target.id}/day-of';
      case 'occurrence_live':
        return '/occurrences/${target.id}/live';
      case 'space_occurrence_day_of':
        return '/space/occurrences/${target.id}/day-of';
      case 'space_occurrence_live':
        return '/space/occurrences/${target.id}/live';
      case 'journey':
        return '/journeys/${target.id}';
      case 'activity':
        return '/activities/${target.id}';
      case 'occurrence':
        return '/occurrences/${target.id}';
      case 'access':
        return '/accesses/${target.id}';
      case 'dossier':
        return '/dossiers/${target.id}';
      case 'project':
        return '/projects/${target.id}';
      case 'group':
        return '/groups/${target.id}';
      default:
        return null;
    }
  }
}
