import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';

import '../../design/makolo_theme.dart';
import '../../design/identity_surface.dart';

/// The collective identity of the active Space. All rows originate in
/// server-scoped owner projections; this widget never infers authority.
class SpaceUsSurface extends StatefulWidget {
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
  State<SpaceUsSurface> createState() => _SpaceUsSurfaceState();
}

class _SpaceUsSurfaceState extends State<SpaceUsSurface> {
  static const _storage = FlutterSecureStorage();
  MakoloTerritoryLayout _layout = MakoloTerritoryLayout.list;

  String? get _spaceSlug => _value(_map(widget.payload['identity'])?['slug']);

  String? get _layoutKey {
    final slug = _spaceSlug;
    return slug == null ? null : 'space.us.layout.$slug';
  }

  @override
  void initState() {
    super.initState();
    unawaited(_restoreLayout());
  }

  @override
  void didUpdateWidget(covariant SpaceUsSurface oldWidget) {
    super.didUpdateWidget(oldWidget);
    final previous = _value(_map(oldWidget.payload['identity'])?['slug']);
    if (previous != _spaceSlug) {
      _layout = MakoloTerritoryLayout.list;
      unawaited(_restoreLayout());
    }
  }

  Future<void> _restoreLayout() async {
    final key = _layoutKey;
    if (key == null) return;
    try {
      final saved = await _storage.read(key: key);
      if (!mounted || key != _layoutKey) return;
      setState(() {
        _layout = saved == 'grid'
            ? MakoloTerritoryLayout.grid
            : MakoloTerritoryLayout.list;
      });
    } on Object {
      // A device preference is never required to display owner-backed data.
    }
  }

  void _chooseLayout(MakoloTerritoryLayout next) {
    if (next == _layout) return;
    setState(() => _layout = next);
    final key = _layoutKey;
    if (key == null) return;
    unawaited(_rememberLayout(key, next));
  }

  Future<void> _rememberLayout(
    String key,
    MakoloTerritoryLayout next,
  ) async {
    try {
      await _storage.write(
        key: key,
        value: next == MakoloTerritoryLayout.grid ? 'grid' : 'list',
      );
    } on Object {
      // The presentation switch remains functional without secure storage.
    }
  }

  @override
  Widget build(BuildContext context) {
    final payload = widget.payload;
    final identity = _map(payload['identity']);
    final authority = _map(payload['authority']);
    final limited =
        authority?['scope'] == 'activity_limited' ||
        authority?['limited_to_activities'] == true;
    final name = _value(identity?['name']) ?? widget.fallbackSpaceName;
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
    final relationSections = relations?['visibility'] == 'visible'
        ? _map(relations?['sections']) ?? <String, dynamic>{}
        : <String, dynamic>{};
    final displayedRelations = relationSections.entries
        .where(
          (entry) =>
              entry.key != 'team' &&
              _rows(_map(entry.value)?['items']).isNotEmpty,
        )
        .toList();
    final responsibilities = _rows(_map(payload['responsibilities'])?['items'])
        .where((item) => item['combined'] != true)
        .toList(growable: false);
    final teamVisible =
        !limited &&
        team?['visibility'] == 'visible' &&
        team?['items'] is List;
    final teamRows = teamVisible
        ? _rows(team?['items'])
        : const <Map<String, dynamic>>[];
    final ownershipRows = !limited && ownership?['visibility'] == 'visible'
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
    final resources = _map(payload['resources']);
    final resourcesVisible =
        resourcesTarget != null && resources?['visibility'] == 'visible';
    final resourceRows = resourcesVisible
        ? _rows(resources?['items'])
        : const <Map<String, dynamic>>[];

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
    final trustTarget = limited ? null : route('trust');

    // Each entry is composed only from already-authorized Space projections.
    // A missing handoff never becomes a fabricated N2/N3 destination.
    final territories = <_SpaceUsTerritory>[
      _SpaceUsTerritory(
        keyName: 'responsibilities',
        title: 'Ma place dans cet Espace',
        subtitle: 'Mes rôles autorisés dans ce collectif',
        icon: Icons.assignment_ind_outlined,
        target: route('responsibilities'),
        previews: [
          if (responsibilities.isEmpty) 'Aucun autre rôle visible.',
          for (final item in responsibilities.take(3))
            _value(item['label']) ?? 'Rôle',
        ],
      ),
      if (teamVisible)
        _SpaceUsTerritory(
          keyName: 'team',
          title: 'Notre équipe',
          subtitle: 'Les personnes avec qui nous travaillons',
          icon: Icons.groups_outlined,
          target: route('team'),
          count: team?['active_members'] is int &&
                  (team!['active_members'] as int) >= 0
              ? team['active_members'] as int
              : null,
          previews: [
            if (teamRows.isEmpty) 'Aucun membre dans cet aperçu.',
            for (final item in teamRows.take(3))
              _value(_map(item['profile'])?['name']) ?? 'Membre',
          ],
        ),
      if (!limited && relationSections.isNotEmpty)
        _SpaceUsTerritory(
          keyName: 'relationships',
          title: 'Nos relations',
          subtitle: 'Personnes, groupes et partenaires visibles',
          icon: Icons.hub_outlined,
          target: route('relationships'),
          previews: [
            if (displayedRelations.isEmpty)
              'Aucune relation visible dans cet aperçu.',
            for (final item in displayedRelations.take(3))
              _relationLabel(item.key),
          ],
        ),
      if (resourcesVisible)
        _SpaceUsTerritory(
          keyName: 'resources',
          title: 'Nos ressources',
          subtitle: 'Documents et outils de cet Espace',
          icon: Icons.folder_copy_outlined,
          target: resourcesTarget,
          count: resources?['count'] is int &&
                  (resources!['count'] as int) >= 0
              ? resources['count'] as int
              : null,
          previews: [
            if (resourceRows.isEmpty) 'Aucune ressource dans cet aperçu.',
            for (final item in resourceRows.take(3))
              _value(item['title']) ?? 'Ressource',
          ],
        ),
      if (ownershipRows.isNotEmpty)
        _SpaceUsTerritory(
          keyName: 'ownership',
          title: 'Notre gouvernance',
          subtitle: 'Représentation et autorité de cet Espace',
          icon: Icons.admin_panel_settings_outlined,
          target: route('ownership'),
          previews: [
            for (final item in ownershipRows.take(3))
              _value(_map(item['profile'])?['name']) ?? 'Représentant',
          ],
        ),
      if (trustTarget != null)
        _SpaceUsTerritory(
          keyName: 'trust',
          title: 'Notre confiance',
          subtitle: 'Faits de vérification disponibles',
          icon: Icons.verified_user_outlined,
          target: trustTarget,
          previews: [
            _map(payload['trust'])?['verified'] == true
                ? 'Des faits publics de vérification sont établis.'
                : 'Aucune vérification publique active à afficher.',
          ],
        ),
    ];


    void open(String target) {
      if (widget.onOpen != null) {
        widget.onOpen!(target);
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
                      child: MakoloIdentityPortrait(
                        name: name,
                        eyebrow: institutionalLabel,
                        subtitle: description,
                        detail: place.isNotEmpty ? place : null,
                        padding: EdgeInsets.zero,
                        leading: Container(
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
                        'Vous voyez uniquement les activités auxquelles vous avez accès.',
                      ),
                    ],
                    if (passportTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.lg),
                      _sectionTitle(
                        context,
                        'Passeport Makolo',
                        'Les informations qui présentent notre collectif.',
                      ),
                      _passportCard(context, passportTarget, open),
                    ],
                    const SizedBox(height: MakoloSpacing.xl),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Notre espace',
                            style: text.titleMedium?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                        MakoloTerritoryViewToggle(
                          toggleKey: const Key('space-us-layout-toggle'),
                          value: _layout,
                          onChanged: _chooseLayout,
                        ),
                      ],
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    if (_layout == MakoloTerritoryLayout.list)
                      Column(
                        key: const Key('space-us-territories-list'),
                        children: [
                          for (final entry in territories)
                            MakoloTerritoryListCard(
                              tapKey: Key('space-us-entry-${entry.keyName}'),
                              title: entry.title,
                              subtitle: entry.subtitle,
                              count: entry.count,
                              symbol: Icon(
                                entry.icon,
                                color: scheme.primary,
                                size: 24,
                              ),
                              onOpen: entry.target == null
                                  ? null
                                  : () => open(entry.target!),
                              previews: [
                                for (final value in entry.previews)
                                  MakoloTerritoryPreview(title: value),
                              ],
                            ),
                        ],
                      )
                    else
                      LayoutBuilder(
                        builder: (context, field) {
                          final twoColumns = field.maxWidth >= 320;
                          final itemWidth = twoColumns
                              ? (field.maxWidth - 12) / 2
                              : field.maxWidth;
                          return Wrap(
                            key: const Key('space-us-territories-grid'),
                            spacing: 10,
                            runSpacing: 10,
                            children: [
                              for (final entry in territories)
                                SizedBox(
                                  width: itemWidth,
                                  child: MakoloTerritoryGridCard(
                                    tapKey: Key('space-us-grid-${entry.keyName}'),
                                    title: entry.title,
                                    subtitle: entry.subtitle,
                                    symbol: Icon(
                                      entry.icon,
                                      color: scheme.primary,
                                      size: 32,
                                    ),
                                    countDescription: entry.count == null
                                        ? null
                                        : '${entry.count} éléments visibles',
                                    onOpen: entry.target == null
                                        ? null
                                        : () => open(entry.target!),
                                  ),
                                ),
                            ],
                          );
                        },
                      ),
                    if (subscriptionTarget != null ||
                        connectionsTarget != null ||
                        settingsTarget != null ||
                        pilotTarget != null) ...[
                      const SizedBox(height: MakoloSpacing.xl),
                      _sectionTitle(
                        context,
                        'Informations et gestion',
                        'Les fonctions institutionnelles autorisées.',
                      ),
                    ],
                    if (subscriptionTarget != null)
                      _action(
                        context,
                        'Abonnement de cet Espace',
                        subscriptionTarget,
                        open,
                      ),
                    if (connectionsTarget != null)
                      _action(
                        context,
                        'Gérer les connexions de cet Espace',
                        connectionsTarget,
                        open,
                      ),
                    if (settingsTarget != null)
                      _action(
                        context,
                        'Modifier les informations collectives',
                        settingsTarget,
                        open,
                      ),
                    if (pilotTarget != null)
                      _action(
                        context,
                        'Comprendre notre activité',
                        pilotTarget,
                        open,
                      ),
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
  ) => MakoloPassportGateway(
    title: 'Passeport de cet Espace',
    subtitle: 'Présenter notre collectif avec les faits disponibles',
    onOpen: () => open(target),
  );

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

  static Widget _sectionTitle(
    BuildContext context,
    String title,
    String subtitle,
  ) {
    final scheme = Theme.of(context).colorScheme;
    final icon = switch (title) {
      'Passeport Makolo' => Icons.badge_outlined,
      'Ma place dans cet Espace' => Icons.assignment_ind_outlined,
      'L’équipe' => Icons.groups_outlined,
      'Personnes & relations' => Icons.hub_outlined,
      'Nos ressources' => Icons.folder_outlined,
      'Gouvernance' => Icons.admin_panel_settings_outlined,
      'Confiance' => Icons.verified_user_outlined,
      'Informations et gestion' => Icons.settings_outlined,
      _ => Icons.diversity_3_outlined,
    };
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: MakoloSpacing.compact),
      padding: const EdgeInsets.symmetric(
        horizontal: MakoloSpacing.md,
        vertical: MakoloSpacing.compact,
      ),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: scheme.primary, size: 23),
              const SizedBox(width: MakoloSpacing.compact),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          if (subtitle.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              subtitle,
              style: Theme.of(context).textTheme.bodySmall
                  ?.copyWith(color: scheme.onSurfaceVariant),
            ),
          ],
        ],
      ),
    );
  }

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
  ) => Semantics(
    button: true,
    child: InkWell(
      onTap: () => open(target),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: MakoloSpacing.md,
          vertical: MakoloSpacing.compact,
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              color: Theme.of(context).colorScheme.primary,
            ),
          ],
        ),
      ),
    ),
  );
}

/// A display-only adaptation of facts already scoped by the Space owner.
class _SpaceUsTerritory {
  const _SpaceUsTerritory({
    required this.keyName,
    required this.title,
    required this.subtitle,
    required this.icon,
    this.target,
    this.count,
    this.previews = const [],
  });

  final String keyName;
  final String title;
  final String subtitle;
  final IconData icon;
  final String? target;
  final int? count;
  final List<String> previews;
}
