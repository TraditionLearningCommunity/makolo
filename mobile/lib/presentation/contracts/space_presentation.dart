/// Ephemeral language and navigation assembled from authorized owner data.
/// No business state or permission is inferred here.
String? spaceText(Object? value) =>
    value is String && value.trim().isNotEmpty ? value.trim() : null;

Map<String, dynamic>? spaceMap(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : null;

String spaceStateLabel(String state) =>
    const {
      'draft': 'À préparer',
      'published': 'Publié',
      'scheduled': 'Prévu',
      'active': 'Actif',
      'inactive': 'Inactif',
      'completed': 'Terminé',
      'archived': 'Archivé',
      'cancelled': 'Annulé',
      'expired': 'Expiré',
      'submitted': 'Soumis',
      'pending': 'En attente',
      'pending_approval': 'En attente de validation',
      'pending_payment': 'En attente de paiement',
      'approved': 'Validé',
      'confirmed': 'Confirmé',
      'in_progress': 'En cours',
      'fulfilled': 'Accompli',
      'rejected': 'Refusé',
      'refunded': 'Remboursé',
      'unknown': 'Inconnu',
      'unavailable': 'Indisponible',
      'insufficient_data': 'Données insuffisantes',
    }[state] ??
    state;

const spaceMetricLabels = {
  'events_count': 'Événements couverts',
  'published_count': 'Événements publiés',
  'upcoming_count': 'Événements à venir',
  'active_tickets': 'Accès actifs',
  'used_tickets': 'Accès utilisés',
  'confirmed_orders': 'Commandes confirmées',
  'waitlist_waiting': 'Demandes en liste d’attente',
  'attendance_percent': 'Présence observée',
};

String spaceMetricValue(Map<String, dynamic> metric) {
  final state = spaceText(metric['state']) ?? 'unknown';
  if (state != 'known' || metric['value'] == null) {
    return spaceStateLabel(state == 'known' ? 'unknown' : state);
  }
  return '${metric['value']}${metric['unit'] == 'percent' ? ' %' : ''}';
}

String? spaceOwnerRoute({
  required String? slug,
  required String? kind,
  required String? id,
}) {
  if (slug == null ||
      id == null ||
      !const {
        'activity',
        'occurrence',
        'offer',
        'journey',
        'commerce_order',
        'transport_route',
        'vehicle',
        'team_member',
        'group',
        'crm_contact',
        'audience',
        'partner',
      }.contains(kind)) {
    return null;
  }
  return '/space/${Uri.encodeComponent(slug)}/retrieval/'
      '${Uri.encodeComponent(kind!)}/${Uri.encodeComponent(id)}';
}

/// The origin is presentation-only. It never grants a Space permission or
/// changes the owner selected by the server. Only known Work sections can
/// become a return destination.
const spaceWorkSectionKeys = <String>{
  'preparation',
  'upcoming',
  'active',
  'blocked',
  'completed',
  'activities',
  'offers',
  'routes',
  'vehicles',
  'requests',
};

String? spaceWorkOwnerRoute({
  required String? slug,
  required String? kind,
  required String? id,
  String? section,
  bool fromCollection = false,
}) {
  final route = spaceOwnerRoute(slug: slug, kind: kind, id: id);
  if (route == null) return null;
  if (!spaceWorkSectionKeys.contains(section)) return route;
  return Uri.parse(route)
      .replace(
        queryParameters: {
          'work_section': section!,
          if (fromCollection) 'work_collection': '1',
        },
      )
      .toString();
}

String spaceWorkReturnRoute({
  required String slug,
  String? section,
  bool fromCollection = false,
}) {
  if (fromCollection && spaceWorkSectionKeys.contains(section)) {
    return '/space/${Uri.encodeComponent(slug)}/work/'
        '${Uri.encodeComponent(section!)}';
  }
  return '/space/work';
}

/// Keep planned dates, availability and lifecycle instants distinct.
List<String> spaceTimingLines(Object? value) {
  final timing = spaceMap(value);
  if (timing == null) return const [];
  final day = spaceText(timing['start_date']);
  final clock = spaceText(timing['start_time']);
  final zone = spaceText(timing['timezone']);
  return [
    if (day != null)
      'Prévu le $day${clock == null ? '' : ' à $clock'}'
          '${zone == null ? '' : ' · $zone'}',
    for (final entry in const {
      'end_date': 'Fin prévue',
      'available_from': 'Disponible à partir du',
      'available_until': 'Disponible jusqu’au',
      'expires_at': 'Expire le',
      'started_at': 'Commencé le',
      'fulfilled_at': 'Accompli le',
      'confirmed_at': 'Confirmé le',
    }.entries)
      if (spaceText(timing[entry.key]) case final String instant)
        '${entry.value} $instant',
  ];
}
