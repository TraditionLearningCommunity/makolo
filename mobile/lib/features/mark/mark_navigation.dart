import '../../app/runtime/actor_context.dart';
import 'mark_repository.dart';

/// Only known Flutter destinations may be opened from a Mark owner handoff.
/// The backend's links point to owner APIs or Web views, not GoRouter paths.
String? markHandoffRoute(MarkResult result, ActorContext actor) {
  if (!{'resolved', 'completed', 'unsupported'}.contains(result.state)) {
    return null;
  }
  final owner = result.handoff?['owner']?.toString();
  final surface = result.handoff?['surface']?.toString();
  if (owner == null || surface == null) return null;

  if (actor is SpaceActorContext) {
    // Nous owns the team experience; a Space handoff does not open a
    // personal route or infer a mandate.
    return owner == 'organizations' && surface == 'team' ? '/space/us' : null;
  }

  final raw = result.raw['result'];
  final data = raw is Map ? raw : const {};
  final id = data['id']?.toString();
  String? detail(String prefix) => id == null || id.trim().isEmpty
      ? null
      : '$prefix/${Uri.encodeComponent(id)}';

  return switch ('$owner/$surface') {
    'access/personal_accesses' => '/accesses',
    'access/access_detail' => detail('/accesses'),
    'journey/ongoing' || 'objectives/ongoing' => '/ongoing',
    'journey/journey_detail' => detail('/journeys'),
    'objectives/dossier_detail' => detail('/dossiers'),
    'objectives/project_detail' => detail('/projects'),
    'operations/occurrence_day_of' =>
      detail('/occurrences') == null
          ? null
          : '${detail('/occurrences')}/day-of',
    'discovery/discover' => Uri(
      path: '/discover/search',
      queryParameters: {'q': data['query']?.toString() ?? ''},
    ).toString(),
    'discovery/watch' || 'discovery/watches' => '/discover/watches',
    'discovery/saved' || 'discovery/saved_possibility' => '/me/saved',
    'personal_assets/resources' => '/me/resources',
    'history/history' => '/history',
    'passport/passport' => '/me/passport',
    'profile/me' => '/me',
    'profile/considerations' => '/me/considerations',
    'attention/now' => '/now',
    _ => null,
  };
}

/// A clarification offers context, never authority. Unknown option kinds,
/// missing identities and incomplete Discovery references remain editable text.
Map<String, String>? markClarificationSelection(Object? option) {
  if (option is! Map) return null;
  final kind = option['kind'];
  final id = option['id'];
  if (kind is! String || id is! String || id.trim().isEmpty) return null;
  const supported = {
    'access',
    'journey',
    'dossier',
    'project',
    'occurrence',
    'discovery_item',
    'recognition_reward',
  };
  if (!supported.contains(kind)) return null;
  final family = option['family'];
  if (kind == 'discovery_item' && (family is! String || family.isEmpty)) {
    return null;
  }
  return {
    'kind': kind,
    'id': id,
    if (family is String && family.isNotEmpty) 'family': family,
  };
}
