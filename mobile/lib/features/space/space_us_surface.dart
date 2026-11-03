import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../design/makolo_theme.dart';

/// The collective identity of the active Space. All rows originate in
/// server-scoped owner projections; this widget never infers authority.
class SpaceUsSurface extends StatelessWidget {
  const SpaceUsSurface({
    super.key,
    required this.payload,
    required this.fallbackSpaceName,
    this.onOpen,
  });

  final Map<String, dynamic> payload;
  final String fallbackSpaceName;
  final ValueChanged<String>? onOpen;

  @override
  Widget build(BuildContext context) {
    final identity = _map(payload['identity']);
    final authority = _map(payload['authority']);
    final limited =
        authority?['scope'] == 'activity_limited' ||
        authority?['limited_to_activities'] == true;
    final name = _value(identity?['name']) ?? fallbackSpaceName;
    final description = _value(identity?['description']);
    final institutionalLabel = _value(
      _map(_map(payload['organization'])?['operating_preset'])?['label'],
    );
    final lifecycle = _value(identity?['lifecycle']);
    final location = _map(identity?['location']);
    final city = _value(location?['city']);
    final country = _value(location?['country']);
    final place = [?city, ?country].join(', ');
    final team = _map(payload['team']);
    final ownership = _map(payload['ownership']);
    final relations = _map(payload['relationships']);
    final relationSections = _map(relations?['sections']) ?? {};
    final displayedRelations = relationSections.entries.where((entry) =>
        entry.key != 'team' &&
        _rows(_map(entry.value)?['items']).isNotEmpty).toList();
    final responsibilities = _rows(_map(payload['responsibilities'])?['items'])
        .where((item) => item['combined'] != true)
        .toList(growable: false);
    final teamVisible =
        !limited &&
        team?['visibility'] != 'restricted' &&
        team?['items'] is List;
    final teamRows = teamVisible
        ? _rows(team?['items'])
        : const <Map<String, dynamic>>[];
    final ownershipRows = !limited && ownership?['visibility'] != 'restricted'
        ? _rows(ownership?['items'])
        : const <Map<String, dynamic>>[];
    final slug = _value(identity?['slug']);
    final handoffs = _map(payload['handoffs']);

    String? route(String depth) {
      if (slug == null) return null;
      final link = _value(handoffs?[depth]);
      final expected = '/space/$slug/us/$depth';
      // Old/offline server-provided links cannot cross actor or Space.
      return link == expected ? link : null;
    }

    final passportTarget = limited ? null : route('passport');
    final resourcesTarget = limited ? null : route('resources');
    final settingsTarget = limited ? null : route('settings');
    final connectionsTarget =
        !limited &&
            slug != null &&
            _value(handoffs?['connections']) == '/space/$slug/connections'
        ? '/space/$slug/connections'
        : null;
    final pilotTarget = limited ? null : route('pilot');
    final subscriptionTarget =
        !limited &&
            slug != null &&
            _value(handoffs?['subscription']) == '/space/$slug/subscription'
        ? '/space/$slug/subscription'
        : null;

    void open(String target) {
      if (onOpen != null) {
        onOpen!(target);
      } else {
        context.push(target);
      }
    }

    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final maxWidth = width >= 960 ? 860.0 : double.infinity;
        return ListView(
          key: const Key('space-us-projection'),
          padding: const EdgeInsets.symmetric(
            horizontal: MakoloSpacing.lg,
            vertical: MakoloSpacing.md,
          ),
          children: [
            Center(
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: maxWidth),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Nous',
                      style: text.labelLarge?.copyWith(
                        color: scheme.primary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(MakoloSpacing.lg),
                      decoration: BoxDecoration(
                        color: scheme.primaryContainer.withValues(alpha: 0.35),
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 58,
                            height: 58,
                            decoration: BoxDecoration(
                              color: scheme.primary,
                              borderRadius: BorderRadius.circular(18),
                            ),
                            child: Icon(
                              Icons.apartment_rounded,
                              size: 30,
                              color: scheme.onPrimary,
                            ),
                          ),
                          const SizedBox(width: MakoloSpacing.md),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (institutionalLabel != null) ...[
                                  Text(
                                    institutionalLabel,
                                    style: text.labelMedium?.copyWith(
                                      color: scheme.primary,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                ],
                                Text(
                                  name,
                                  style: text.headlineSmall?.copyWith(
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                if (description != null) ...[
                                  const SizedBox(height: MakoloSpacing.sm),
                                  Text(description, style: text.bodyMedium),
                                ],
                                if (place.isNotEmpty) ...[
                                  const SizedBox(height: MakoloSpacing.sm),
                                  Row(
                                    children: [
                                      const Icon(
                                        Icons.place_outlined,
                                        size: 16,
                                      ),
                                      const SizedBox(width: 4),
                                      Flexible(
                                        child: Text(
                                          place,
                                          style: text.bodySmall,
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (lifecycle == 'suspended' ||
                        lifecycle == 'archived') ...[
                      const SizedBox(height: MakoloSpacing.md),
                      _notice(
                        context,
                        lifecycle == 'archived'
                            ? 'Cet Espace est archivé.'
                            : 'Cet Espace est suspendu.',
                      ),
                    ],
                    if (limited) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      _notice(
                        context,
                        'Contexte limité à certaines activités. '
                        'Les données institutionnelles privées ne sont pas exposées.',
                      ),
                    ],
                    if (passportTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      _sectionTitle(
                        context,
                        'Passeport Makolo',
                        'Notre identité à présenter selon les faits disponibles.',
                      ),
                      _passportCard(context, passportTarget, open),
                    ],
                    const SizedBox(height: MakoloSpacing.xl),
                    _sectionTitle(
                      context,
                      'Ma place dans cet Espace',
                      'Vos rôles dans le collectif, distincts des tâches confiées.',
                    ),
                    if (responsibilities.isEmpty)
                      _quiet(
                        context,
                        'Aucune responsabilité supplémentaire visible.',
                      )
                    else
                      _panel(
                        context,
                        children: [
                          for (final item in responsibilities)
                            _fact(
                              context,
                              Icons.assignment_ind_outlined,
                              _value(item['label']) ?? 'Responsabilité',
                              _value(_map(item['activity'])?['title']) ??
                                  'Autorité ou périmètre lié à ce rôle',
                            ),
                        ],
                      ),
                    if (route('responsibilities') case final target?) ...[
                      _action(
                        context,
                        'Comprendre les responsabilités',
                        target,
                        open,
                      ),
                    ],
                    if (!limited) ...[
                      const SizedBox(height: MakoloSpacing.xl),
                      _sectionTitle(
                        context,
                        'L’équipe',
                        'Les personnes avec qui nous travaillons.',
                      ),
                      if (teamVisible) ...[
                        _panel(
                          context,
                          children: [
                            if (teamRows.isEmpty)
                              _quiet(context, 'Aucun membre actif visible.')
                            else
                              for (final person in teamRows.take(3))
                                _fact(
                                  context,
                                  Icons.person_outline_rounded,
                                  _value(_map(person['profile'])?['name']) ??
                                      'Membre',
                                  'Équipe principale',
                                ),
                            if (team?['has_more'] == true || teamRows.length > 3)
                              _quiet(
                                context,
                                'D’autres personnes sont à retrouver dans l’équipe.',
                              ),
                          ],
                        ),
                        if (route('team') case final target?)
                          _action(context, 'Ouvrir l’équipe', target, open),
                      ] else
                        _quiet(
                          context,
                          'La composition de l’équipe est réservée '
                          'aux personnes autorisées.',
                        ),
                    ],
                    if (!limited && relationSections.isNotEmpty) ...[
                      const SizedBox(height: MakoloSpacing.xl),
                      _sectionTitle(
                        context,
                        _value(relations?['label']) ?? 'Personnes & relations',
                        'Les contacts, groupes et partenaires visibles.',
                      ),
                      if (displayedRelations.isNotEmpty)
                        _panel(
                          context,
                          children: [
                            for (final entry in displayedRelations)
                              _fact(
                                context,
                                _relationIcon(entry.key),
                                _relationLabel(entry.key),
                                _relationSummary(_map(entry.value)),
                              ),
                          ],
                        ),
                      if (route('relationships') case final target?)
                        _action(
                          context,
                          'Explorer les relations',
                          target,
                          open,
                        ),
                    ],
                    if (ownershipRows.isNotEmpty) ...[
                      const SizedBox(height: MakoloSpacing.xl),
                      _sectionTitle(
                        context,
                        'Gouvernance',
'Les personnes qui représentent et gouvernent cet Espace.',
                      ),
                      _panel(
                        context,
                        children: [
                          for (final owner in ownershipRows)
                            _fact(
                              context,
                              Icons.verified_user_outlined,
                              _value(_map(owner['profile'])?['name']) ??
                                  'Représentant',
                              _value(_map(owner['responsibility'])?['label']) ??
                                  'Autorité Space',
                            ),
                        ],
                      ),
                      if (route('ownership') case final target?)
                        _action(context, 'Voir la gouvernance', target, open),
                    ],
                    if (route('trust') case final target?) ...[
                      const SizedBox(height: MakoloSpacing.xl),
                      _sectionTitle(
                        context,
                        'Confiance',
                        'Des faits vérifiables, sans classement global du collectif.',
                      ),
                      _notice(
                        context,
                        _map(payload['trust'])?['verified'] == true
                            ? 'Des faits publics de vérification sont établis.'
                            : 'Aucune vérification publique active à afficher.',
                      ),
                      _action(
                        context,
                        'Consulter les faits de confiance',
                        target,
                        open,
                      ),
                    ],
                    if (resourcesTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.xl),
                      _sectionTitle(
                        context,
                        'Nos ressources',
                        'Les ressources institutionnelles accessibles dans cet Espace.',
                      ),
                      _action(
                        context,
                        'Consulter les ressources',
                        resourcesTarget,
                        open,
                      ),
                    ],
                    if (subscriptionTarget != null ||
                        connectionsTarget != null ||
                        settingsTarget != null ||
                        pilotTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.xl),
                      _sectionTitle(
                        context, 'Informations et gestion',
                        'Les autres fonctions de cet Espace.',
                      ),
                    ],
                    if (subscriptionTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      _action(
                        context,
                        'Abonnement de cet Espace',
                        subscriptionTarget,
                        open,
                      ),
                    ],
                    if (connectionsTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      _action(
                        context,
                        'Gérer les connexions de cet Espace',
                        connectionsTarget,
                        open,
                      ),
                    ],
                    if (settingsTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      _action(
                        context,
                        'Modifier les informations collectives',
                        settingsTarget,
                        open,
                      ),
                    ],
                    if (pilotTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      _action(
                        context,
                        'Comprendre notre activité',
                        pilotTarget,
                        open,
                      ),
                    ],
                    const SizedBox(height: MakoloSpacing.xl),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  static Widget _passportCard(
    BuildContext context,
    String target,
    ValueChanged<String> open,
  ) {
    final colors = Theme.of(context).colorScheme;
    return Material(
      color: colors.primary,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () => open(target),
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          child: Row(
            children: [
              Icon(Icons.badge_outlined, color: colors.onPrimary, size: 32),
              const SizedBox(width: MakoloSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Passeport de cet Espace',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: colors.onPrimary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Présenter notre collectif avec les faits disponibles',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: colors.onPrimary,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.arrow_forward_rounded, color: colors.onPrimary),
            ],
          ),
        ),
      ),
    );
  }

  static Map<String, dynamic>? _map(Object? value) {
    if (value is! Map) return null;
    return {
      for (final entry in value.entries)
        if (entry.key is String) entry.key as String: entry.value,
    };
  }

  static List<Map<String, dynamic>> _rows(Object? value) {
    if (value is! List) return const [];
    return value
        .map(_map)
        .whereType<Map<String, dynamic>>()
        .toList(growable: false);
  }

  static String? _value(Object? value) =>
      value is String && value.trim().isNotEmpty ? value.trim() : null;

  static String _relationLabel(String kind) => switch (kind) {
    'team' => 'Équipe',
    'groups' => 'Groupes',
    'crm_contacts' => 'Contacts',
    'audiences' => 'Publics',
    'partners' => 'Partenaires',
    _ => 'Relations',
  };

  static IconData _relationIcon(String kind) => switch (kind) {
    'team' => Icons.groups_outlined,
    'groups' => Icons.hub_outlined,
    'crm_contacts' => Icons.contacts_outlined,
    'audiences' => Icons.people_outline,
    'partners' => Icons.handshake_outlined,
    _ => Icons.link_outlined,
  };

  static String _relationSummary(Map<String, dynamic>? section) {
    final items = _rows(section?['items']);
    if (items.isEmpty) {
      return 'Aucune relation visible';
    }
    final count = items.length;
    return section?['has_more'] == true
        ? '$count éléments visibles dans cet aperçu · d’autres sont disponibles'
        : '$count relation${count == 1 ? '' : 's'} visible${count == 1 ? '' : 's'}';
  }

  static Widget _sectionTitle(
    BuildContext context,
    String title,
    String subtitle,
  ) => Padding(
    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 4),
        Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
      ],
    ),
  );

  static Widget _panel(
    BuildContext context, {
    required List<Widget> children,
  }) => Card(
    margin: EdgeInsets.zero,
    clipBehavior: Clip.antiAlias,
    child: Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: MakoloSpacing.md,
        vertical: MakoloSpacing.sm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    ),
  );

  static Widget _fact(
    BuildContext context,
    IconData icon,
    String name,
    String subtitle,
  ) => Padding(
    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: Theme.of(context).colorScheme.primary, size: 22),
        const SizedBox(width: MakoloSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 3),
              Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ],
    ),
  );

  static Widget _quiet(BuildContext context, String message) => Padding(
    padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.sm),
    child: Text(message, style: Theme.of(context).textTheme.bodySmall),
  );

  static Widget _notice(BuildContext context, String message) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(MakoloSpacing.md),
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(12),
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
    ),
    child: Row(
      children: [
        const Icon(Icons.info_outline, size: 20),
        const SizedBox(width: MakoloSpacing.sm),
        Expanded(
          child: Text(message, style: Theme.of(context).textTheme.bodySmall),
        ),
      ],
    ),
  );

  static Widget _action(
    BuildContext context,
    String label,
    String target,
    ValueChanged<String> open,
  ) => Align(
    alignment: Alignment.centerLeft,
    child: TextButton.icon(
      onPressed: () => open(target),
      icon: const Icon(Icons.arrow_forward_rounded),
      label: Text(label),
    ),
  );
}
