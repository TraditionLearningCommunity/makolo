import 'package:flutter/material.dart';

import '../../design/action_controls.dart';
import '../../design/interaction_primitives.dart';
import '../../design/makolo_patterns.dart';
import '../../navigation/destination.dart';
import 'me_selector.dart';

enum _CollectiveTab { all, spaces, teams, groups }

/// Composition locale de relations deja autorisees par personal.me.
/// Les appartenances Team/Group ne sont jamais des autorisations Space.
class MeCollectivesContent extends StatefulWidget {
  const MeCollectivesContent({
    super.key,
    required this.items,
    required this.collectives,
    required this.offline,
    required this.hasMore,
    required this.onOpen,
    this.onActSpace,
  });

  final List<MeItemPresentation> items;
  final Object? collectives;
  final bool offline;
  final bool hasMore;
  final bool Function(StructuredDestination) onOpen;
  final ValueChanged<MeItemPresentation>? onActSpace;

  @override
  State<MeCollectivesContent> createState() => _MeCollectivesContentState();
}

class _MeCollectivesContentState extends State<MeCollectivesContent> {
  final TextEditingController _search = TextEditingController();
  _CollectiveTab _tab = _CollectiveTab.all;
  bool _searchVisible = false;
  bool _alphabetical = false;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Map<String, dynamic>? _map(Object? value) {
    if (value is! Map) return null;
    return value.map((key, element) => MapEntry(key.toString(), element));
  }

  Map<String, dynamic>? _family(String key) =>
      _map(_map(widget.collectives)?[key]);

  String _familyKey(String kind) => switch (kind) {
    'space' => 'authorized_spaces',
    'team' => 'teams',
    _ => 'groups',
  };

  int? _count(String family) {
    final collection = _family(family);
    final count = collection?['count'];
    if (count is int && count >= 0) return count;
    // An acquired, complete list may be counted; a partial page may not.
    final rows = collection?['items'];
    if (rows is List && collection?['has_more'] == false) {
      return rows.length;
    }
    return null;
  }

  Map<String, dynamic>? _row(MeItemPresentation item) {
    final rows = _family(_familyKey(item.destination.kind))?['items'];
    if (rows is! List) return null;
    for (final value in rows) {
      final row = _map(value);
      if (row?['id']?.toString() == item.destination.id) return row;
    }
    return null;
  }

  StructuredDestination? _teamSpace(MeItemPresentation item) {
    if (item.destination.kind != 'team') return null;
    final space = _map(_row(item)?['space']);
    final id = space?['id'];
    final slug = space?['slug'];
    if (id is! String || id.isEmpty || slug is! String || slug.isEmpty) {
      return null;
    }
    return StructuredDestination(kind: 'space', id: id, link: slug);
  }

  bool _canAct(MeItemPresentation item) =>
      item.destination.kind == 'space' &&
      item.canOpen &&
      !widget.offline &&
      widget.onActSpace != null &&
      _row(item)?['can_act'] == true;

  List<MeItemPresentation> _visible(String kind) {
    final query = _search.text.trim().toLowerCase();
    final items = widget.items.where((item) {
      if (item.destination.kind != kind) return false;
      if (query.isEmpty) return true;
      final parent = item.subtitle ?? '';
      return item.title.toLowerCase().contains(query) ||
          parent.toLowerCase().contains(query);
    }).toList();
    if (_alphabetical) {
      items.sort((a, b) {
        final byName = a.title.toLowerCase().compareTo(b.title.toLowerCase());
        return byName != 0
            ? byName
            : a.destination.id.compareTo(b.destination.id);
      });
    }
    return items;
  }

  void _choose(_CollectiveTab tab) {
    setState(() => _tab = tab);
  }

  void _preview(MeItemPresentation item) {
    final teamSpace = _teamSpace(item);
    final destination = teamSpace ?? (item.canOpen ? item.destination : null);
    showMakoloQuickPreview(
      context,
      title: item.title,
      eyebrow: switch (item.destination.kind) {
        'space' => 'Espace',
        'team' => 'Équipe',
        _ => 'Groupe',
      },
      summary: item.subtitle,
      icon: item.destination.kind == 'space'
          ? Icons.apartment_rounded
          : Icons.groups_outlined,
      facts: item.metadata,
      onOpen: destination == null
          ? null
          : () {
              widget.onOpen(destination);
            },
    );
  }

  Widget _more(MeItemPresentation item) => MakoloActionMenu(
    tooltip: 'Autres actions pour ${item.title}',
    actions: const [
      MakoloInteractionAction(
        id: 'preview',
        label: 'Aperçu',
        intent: MakoloActionIntent.inspect,
      ),
    ],
    onSelected: (_) => _preview(item),
  );

  Widget _summaryStat(
    BuildContext context,
    String label,
    int? count,
    IconData icon,
  ) {
    final scheme = Theme.of(context).colorScheme;
    if (count == null || count <= 0) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: scheme.primary, size: 19),
          const SizedBox(width: 7),
          Text(
            '$count',
            style: TextStyle(
              color: scheme.primary,
              fontWeight: FontWeight.w800,
              fontSize: 18,
            ),
          ),
          const SizedBox(width: 5),
          Text(label, style: const TextStyle(fontSize: 12)),
        ],
      ),
    );
  }

  Widget _summary(BuildContext context) {
    final spaces = _count('authorized_spaces');
    final teams = _count('teams');
    final groups = _count('groups');
    final total = spaces != null && teams != null && groups != null
        ? spaces + teams + groups
        : null;
    return Container(
      key: const Key('me-collectives-summary'),
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF2B176E), Color(0xFF5232DB)],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            total != null && total > 0 ? '$total collectifs' : 'Mes collectifs',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 5),
          const Text(
            'Espaces, équipes et groupes liés à moi',
            style: TextStyle(color: Colors.white, fontSize: 13),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (spaces != null && spaces > 0)
                _summaryStat(
                  context,
                  'Espaces',
                  spaces,
                  Icons.apartment_rounded,
                ),
              if (teams != null && teams > 0)
                _summaryStat(context, 'Équipes', teams, Icons.groups_outlined),
              if (groups != null && groups > 0)
                _summaryStat(
                  context,
                  'Groupes',
                  groups,
                  Icons.group_work_outlined,
                ),
            ],
          ),
          if (widget.offline) ...[
            const SizedBox(height: 12),
            const Text(
              'Informations enregistrées. Autorisations à confirmer en ligne.',
              style: TextStyle(color: Colors.white, fontSize: 12),
            ),
          ],
        ],
      ),
    );
  }

  Widget _filters(BuildContext context) {
    final counts = [
      _count('authorized_spaces'),
      _count('teams'),
      _count('groups'),
    ];
    final total = counts.every((value) => value != null)
        ? counts.fold<int>(0, (sum, value) => sum + value!)
        : null;
    final tabs = [
      (_CollectiveTab.all, 'Tous', total),
      (_CollectiveTab.spaces, 'Espaces', counts[0]),
      (_CollectiveTab.teams, 'Équipes', counts[1]),
      (_CollectiveTab.groups, 'Groupes', counts[2]),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SingleChildScrollView(
          key: const Key('me-collectives-filter-scroller'),
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final tab in tabs) ...[
                ChoiceChip(
                  key: Key('me-collectives-filter-${tab.$1.name}'),
                  selected: _tab == tab.$1,
                  label: Text(
                    tab.$3 != null && tab.$3! > 0
                        ? '${tab.$2} (${tab.$3})'
                        : tab.$2,
                  ),
                  onSelected: (_) => _choose(tab.$1),
                ),
                const SizedBox(width: 8),
              ],
            ],
          ),
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            MakoloIconActionButton(
              tooltip: 'Rechercher un collectif',
              icon: Icons.search_rounded,
              onPressed: () {
                setState(() {
                  _searchVisible = !_searchVisible;
                  if (!_searchVisible) _search.clear();
                });
              },
            ),
            const Spacer(),
            PopupMenuButton<bool>(
              tooltip: 'Trier les collectifs',
              initialValue: _alphabetical,
              onSelected: (value) => setState(() => _alphabetical = value),
              itemBuilder: (context) => const [
                PopupMenuItem(value: false, child: Text('Ordre actuel')),
                PopupMenuItem(value: true, child: Text('Nom A à Z')),
              ],
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  vertical: 10,
                  horizontal: 12,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.sort_rounded, size: 19),
                    const SizedBox(width: 8),
                    Text(_alphabetical ? 'Nom A à Z' : 'Trier'),
                    const Icon(Icons.arrow_drop_down_rounded),
                  ],
                ),
              ),
            ),
          ],
        ),
        if (_searchVisible)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: TextField(
              key: const Key('me-collectives-search'),
              controller: _search,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                hintText: 'Rechercher parmi mes collectifs',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _search.text.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Effacer la recherche',
                        onPressed: () {
                          setState(() => _search.clear());
                        },
                        icon: const Icon(Icons.close),
                      ),
                border: const OutlineInputBorder(),
              ),
            ),
          ),
      ],
    );
  }

  Widget _sectionHeader(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required _CollectiveTab tab,
  }) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 24, bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            backgroundColor: scheme.primary.withValues(alpha: 0.09),
            child: Icon(icon, color: scheme.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleMedium),
                Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
          if (_tab == _CollectiveTab.all)
            TextButton(
              onPressed: () => _choose(tab),
              child: const Text('Tout voir'),
            ),
        ],
      ),
    );
  }

  Widget _spaceCard(BuildContext context, MeItemPresentation item) {
    final scheme = Theme.of(context).colorScheme;
    final canAct = _canAct(item);
    return SizedBox(
      width: 255,
      child: Card(
        key: Key('me-collective-space-${item.destination.id}'),
        margin: EdgeInsets.zero,
        color: scheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: scheme.outlineVariant),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    backgroundColor: scheme.primary.withValues(alpha: 0.1),
                    child: Icon(Icons.apartment_rounded, color: scheme.primary),
                  ),
                  const Spacer(),
                  _more(item),
                ],
              ),
              const SizedBox(height: 10),
              Text(item.title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text(
                item.subtitle ?? 'Espace',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 12),
              if (!widget.offline && _row(item)?['can_act'] == true)
                Chip(
                  avatar: const Icon(Icons.check_rounded, size: 16),
                  label: const Text('Espace autorisé'),
                  visualDensity: VisualDensity.compact,
                ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: MakoloActionButton(
                  label: canAct ? 'Agir' : 'Ouvrir',
                  icon: canAct
                      ? Icons.arrow_forward_rounded
                      : Icons.open_in_new_rounded,
                  appearance: canAct
                      ? MakoloActionAppearance.primary
                      : MakoloActionAppearance.secondary,
                  onPressed: canAct
                      ? () => widget.onActSpace!(item)
                      : item.canOpen
                      ? () {
                          widget.onOpen(item.destination);
                        }
                      : null,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _relationshipCard(BuildContext context, MeItemPresentation item) {
    final scheme = Theme.of(context).colorScheme;
    final isTeam = item.destination.kind == 'team';
    final teamSpace = _teamSpace(item);
    final destination = teamSpace ?? (item.canOpen ? item.destination : null);
    final relationship = _row(item)?['relationship'];
    final member = relationship == 'membership';
    return Card(
      key: Key('me-collective-${item.destination.kind}-${item.destination.id}'),
      margin: const EdgeInsets.only(bottom: 8),
      color: scheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: scheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundColor: scheme.primary.withValues(alpha: 0.09),
                  child: Icon(
                    isTeam ? Icons.groups_outlined : Icons.group_work_outlined,
                    color: scheme.primary,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    item.title,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                _more(item),
              ],
            ),
            if (item.subtitle != null) ...[
              const SizedBox(height: 6),
              Text(
                item.subtitle!,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 8),
            Row(
              children: [
                if (member)
                  Chip(
                    label: const Text('Membre'),
                    visualDensity: VisualDensity.compact,
                  ),
                const Spacer(),
                MakoloActionButton(
                  label: destination != null
                      ? isTeam
                            ? 'Voir l’Espace'
                            : 'Ouvrir'
                      : 'Aperçu',
                  icon: destination != null
                      ? Icons.open_in_new_rounded
                      : Icons.visibility_outlined,
                  appearance: MakoloActionAppearance.secondary,
                  onPressed: destination == null
                      ? () => _preview(item)
                      : () {
                          widget.onOpen(destination);
                        },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final groups = [
      (
        kind: 'space',
        tab: _CollectiveTab.spaces,
        title: 'Espaces où je peux agir',
        subtitle: 'Les Espaces où une autorité a été résolue.',
        icon: Icons.apartment_rounded,
      ),
      (
        kind: 'team',
        tab: _CollectiveTab.teams,
        title: 'Mes équipes',
        subtitle: 'Les équipes avec lesquelles je collabore.',
        icon: Icons.groups_outlined,
      ),
      (
        kind: 'group',
        tab: _CollectiveTab.groups,
        title: 'Mes groupes',
        subtitle: 'Mes groupes et relations visibles.',
        icon: Icons.group_work_outlined,
      ),
    ];
    final sections = <Widget>[];
    for (final group in groups) {
      if (_tab != _CollectiveTab.all && _tab != group.tab) continue;
      final items = _visible(group.kind);
      if (items.isEmpty) continue;
      sections.add(
        _sectionHeader(
          context,
          title: group.title,
          subtitle: group.subtitle,
          icon: group.icon,
          tab: group.tab,
        ),
      );
      if (group.kind == 'space') {
        sections.add(
          SingleChildScrollView(
            key: const Key('me-collectives-spaces'),
            scrollDirection: Axis.horizontal,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final item in items) ...[
                  _spaceCard(context, item),
                  const SizedBox(width: 10),
                ],
              ],
            ),
          ),
        );
      } else {
        sections.addAll([
          for (final item in items) _relationshipCard(context, item),
        ]);
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text('Retrouve ici les Espaces, équipes et groupes liés à toi.'),
        const SizedBox(height: 16),
        _summary(context),
        const SizedBox(height: 14),
        _filters(context),
        ...sections,
        if (sections.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: Text(
              _search.text.trim().isNotEmpty
                  ? widget.hasMore
                        ? 'Aucun résultat parmi les collectifs déjà chargés.'
                        : 'Aucun collectif ne correspond à cette recherche.'
                  : widget.hasMore
                  ? 'Les autres collectifs seront affichés après chargement.'
                  : 'Aucun collectif dans cette catégorie.',
              textAlign: TextAlign.center,
            ),
          ),
        if (widget.hasMore && _search.text.trim().isNotEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 12),
            child: Text(
              'Recherche sur les informations déjà reçues. '
              'D’autres collectifs peuvent encore être synchronisés.',
            ),
          ),
      ],
    );
  }
}
