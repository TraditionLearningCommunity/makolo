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
      case 'space_request':
        return '/space/requests/${target.id}';
      case 'space_work_journey':
      case 'space_work_activity':
      case 'space_commerce_order':
        final expectedOwner = switch (target.kind.toLowerCase()) {
          'space_work_journey' => 'journey',
          'space_work_activity' => 'activity',
          _ => 'commerce_order',
        };
        final link = target.link;
        final uri = link == null ? null : Uri.tryParse(link);
        if (uri == null ||
            uri.hasScheme ||
            uri.hasAuthority ||
            uri.hasQuery ||
            uri.hasFragment ||
            uri.pathSegments.length != 5 ||
            uri.pathSegments[0] != 'space' ||
            uri.pathSegments[1].isEmpty ||
            uri.pathSegments[2] != 'retrieval' ||
            uri.pathSegments[3] != expectedOwner ||
            uri.pathSegments[4] != target.id) {
          return null;
        }
        return link;
      case 'conversation':
        return '/conversations/${target.id}';
      case 'journey':
        return '/journeys/${target.id}';
      case 'share_delivery':
        return '/shares/${Uri.encodeComponent(target.id)}';
      case 'share_link':
        return '/s/${Uri.encodeComponent(target.id)}';
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
      case 'space_us_team':
      case 'space_us_responsibilities':
      case 'space_us_relationships':
      case 'space_us_ownership':
      case 'space_us_trust':
      case 'space_us_pilot':
      case 'space_us_settings':
        return target.link;
      default:
        return null;
    }
  }
}
