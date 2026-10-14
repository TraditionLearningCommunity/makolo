import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/makolo_theme.dart';
import '../discovery/discovery_repository.dart';
import '../discovery/discovery_selector.dart';
import 'public_shell.dart';

/// Public Discovery consumes the same server projection and parser as personal
/// Discovery. It never invents a Profile or makes a client-side search corpus.
class GuestDiscoverScreen extends StatefulWidget {
  const GuestDiscoverScreen({
    super.key,
    required this.runtime,
    this.initialQuery = '',
    this.initialVertical = '',
  });

  final AppRuntime runtime;
  final String initialQuery;
  final String initialVertical;

  @override
  State<GuestDiscoverScreen> createState() => _GuestDiscoverScreenState();
}

class _GuestDiscoverScreenState extends State<GuestDiscoverScreen> {
  static const _interactionId = 'public-discover';
  static const _selector = DiscoverySelector();

  final _search = TextEditingController();
  final _place = TextEditingController();

  DiscoveryCollectionPresentation _collection =
      DiscoveryCollectionPresentation.empty;
  String _vertical = '';
  String _when = '';
  String _price = '';
  int _page = 1;
  int _generation = 0;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _search.text = widget.initialQuery;
    _vertical = widget.initialVertical;
    unawaited(_restoreAndLoad());
  }

  @override
  void didUpdateWidget(covariant GuestDiscoverScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialQuery != oldWidget.initialQuery ||
        widget.initialVertical != oldWidget.initialVertical) {
      _search.text = widget.initialQuery;
      _vertical = widget.initialVertical;
      _page = 1;
      unawaited(_load());
    }
  }

  @override
  void dispose() {
    _generation++;
    _search.dispose();
    _place.dispose();
    super.dispose();
  }

  DiscoveryQuery get _query => DiscoveryQuery(
    text: _search.text.trim(),
    place: _place.text.trim(),
    when: _when,
    vertical: _vertical,
    price: _price,
    page: _page,
    pageSize: 12,
  );

  Future<void> _restoreAndLoad() async {
    final saved = await widget.runtime.interactions?.read(_interactionId);
    if (!mounted) return;
    if (widget.initialQuery.isEmpty && widget.initialVertical.isEmpty) {
      final query = saved?['query'];
      if (query is String) _search.text = query;
      final place = saved?['place'];
      if (place is String) _place.text = place;
      final vertical = saved?['vertical'];
      if (vertical is String) _vertical = vertical;
    }
    await _load();
  }

  Future<void> _load() async {
    final generation = ++_generation;
    final query = _query;
    if (mounted) setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.runtime.interactions?.save(_interactionId, {
        'query': query.text,
        'place': query.place,
        'vertical': query.vertical,
      });
      final api = widget.runtime.api;
      if (api == null) throw StateError('Public API unavailable');
      final response = await api.publicGet(query.path);
      final payload = response.jsonObject()['data'];
      if (payload is! Map) throw const FormatException('Invalid projection');
      final collection = _selector.publicCollection(
        Map<String, dynamic>.from(payload),
      );
      if (!mounted || generation != _generation) return;
      setState(() {
        _collection = collection;
        _loading = false;
      });
    } on Object {
      if (!mounted || generation != _generation) return;
      setState(() {
        _loading = false;
        _error = 'Impossible d’actualiser les possibilités publiques.';
      });
    }
  }

  void _apply() {
    setState(() => _page = 1);
    unawaited(_load());
  }

  void _selectVertical(String vertical) {
    setState(() {
      _vertical = vertical;
      _page = 1;
    });
    unawaited(_load());
  }

  void _movePage(int page) {
    if (page < 1) return;
    setState(() => _page = page);
    unawaited(_load());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return PublicExperienceShell(
      current: 1,
      child: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          key: const Key('guest-public-landing'),
          padding: const EdgeInsets.all(MakoloSpacing.lg),
          children: [
            Text('Découvrir', style: theme.textTheme.labelMedium?.copyWith(
              color: theme.colorScheme.primary,
            )),
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              'Qu’avez-vous envie de vivre, faire ou obtenir ?',
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: MakoloSpacing.sm),
            const Text(
              'Décrivez ce que vous cherchez, choisissez une piste ou explorez librement.',
            ),
            const SizedBox(height: MakoloSpacing.lg),
            TextField(
              controller: _search,
              key: const Key('guest-search-query'),
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _apply(),
              decoration: InputDecoration(
                labelText: 'Rechercher',
                hintText: 'Ex. Voyager à Kolwezi demain',
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _search.text.isEmpty ? null : IconButton(
                  tooltip: 'Effacer',
                  icon: const Icon(Icons.clear),
                  onPressed: () {
                    _search.clear();
                    _apply();
                  },
                ),
              ),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            FilledButton(
              onPressed: _loading ? null : _apply,
              child: const Text('Découvrir'),
            ),
            const SizedBox(height: MakoloSpacing.md),
            Wrap(
              spacing: MakoloSpacing.sm,
              runSpacing: MakoloSpacing.xs,
              children: [
                for (final value in const [
                  ('', 'Tout'),
                  ('transport', 'Voyager'),
                  ('event', 'Événements'),
                  ('service', 'Services'),
                  ('other', 'Autres'),
                ])
                  ChoiceChip(
                    label: Text(value.$2),
                    selected: _vertical == value.$1,
                    onSelected: (_) => _selectVertical(value.$1),
                  ),
              ],
            ),
            const SizedBox(height: MakoloSpacing.sm),
            ExpansionTile(
              key: const Key('guest-filters'),
              title: const Text('Filtres'),
              leading: const Icon(Icons.tune),
              childrenPadding: const EdgeInsets.only(bottom: MakoloSpacing.md),
              children: [
                TextField(
                  controller: _place,
                  decoration: const InputDecoration(
                    labelText: 'Lieu',
                    hintText: 'Ville ou lieu',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: MakoloSpacing.md),
                DropdownButtonFormField<String>(
                  initialValue: _when,
                  decoration: const InputDecoration(labelText: 'Quand'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('À venir')),
                    DropdownMenuItem(value: 'today', child: Text('Aujourd’hui')),
                    DropdownMenuItem(value: 'tomorrow', child: Text('Demain')),
                    DropdownMenuItem(value: 'weekend', child: Text('Ce week-end')),
                    DropdownMenuItem(value: 'week', child: Text('Cette semaine')),
                  ],
                  onChanged: (value) => setState(() => _when = value ?? ''),
                ),
                DropdownButtonFormField<String>(
                  initialValue: _price,
                  decoration: const InputDecoration(labelText: 'Prix'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('Tous les prix')),
                    DropdownMenuItem(value: 'free', child: Text('Gratuit')),
                    DropdownMenuItem(value: 'paid', child: Text('Payant')),
                  ],
                  onChanged: (value) => setState(() => _price = value ?? ''),
                ),
                const SizedBox(height: MakoloSpacing.md),
                OutlinedButton(
                  onPressed: _apply,
                  child: const Text('Appliquer les filtres'),
                ),
              ],
            ),
            const SizedBox(height: MakoloSpacing.lg),
            if (_error != null) ...[
              Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
              TextButton(onPressed: _load, child: const Text('Réessayer')),
              const SizedBox(height: MakoloSpacing.sm),
            ],
            if (_loading && _collection.items.isEmpty)
              const Center(child: CircularProgressIndicator())
            else ...[
              Text(
                '${_collection.count} résultats',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: MakoloSpacing.md),
              if (_collection.items.isEmpty && !_loading)
                const Padding(
                  padding: EdgeInsets.all(MakoloSpacing.lg),
                  child: Text('Aucune possibilité publique à afficher pour cette recherche.'),
                ),
              for (final item in _collection.items)
                _PublicPossibilityCard(
                  item: item,
                  onTap: () => context.push(
                    '/discover/items/${Uri.encodeComponent(item.family)}/${Uri.encodeComponent(item.id)}',
                  ),
                ),
              if (_collection.page > 1 || _collection.hasNext)
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    TextButton(
                      onPressed: _collection.page > 1 && !_loading
                          ? () => _movePage(_collection.page - 1)
                          : null,
                      child: const Text('Précédent'),
                    ),
                    Text('Page ${_collection.page}'),
                    TextButton(
                      onPressed: _collection.hasNext && !_loading
                          ? () => _movePage(_collection.page + 1)
                          : null,
                      child: const Text('Suivant'),
                    ),
                  ],
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class _PublicPossibilityCard extends StatelessWidget {
  const _PublicPossibilityCard({
    required this.item,
    required this.onTap,
  });

  final DiscoveryItemPresentation item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final media = item.imageUrl == null ? null : Uri.tryParse(item.imageUrl!);
    return Padding(
      padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (media != null && (media.scheme == 'https' || media.scheme == 'http'))
                AspectRatio(
                  aspectRatio: 4 / 3,
                  child: Image.network(
                    item.imageUrl!,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.all(MakoloSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (item.eyebrow != null)
                      Text(
                        item.eyebrow!,
                        style: theme.textTheme.labelMedium?.copyWith(
                          color: theme.colorScheme.primary,
                        ),
                      ),
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(item.title, style: theme.textTheme.titleMedium),
                    if (item.summary.isNotEmpty) ...[
                      const SizedBox(height: MakoloSpacing.sm),
                      Text(item.summary, maxLines: 3, overflow: TextOverflow.ellipsis),
                    ],
                    if (item.routeLabel != null)
                      Text(item.routeLabel!, style: theme.textTheme.labelMedium),
                    if (item.owner != null)
                      Text(item.owner!, style: theme.textTheme.bodySmall),
                    if (item.place != null)
                      Text(item.place!, style: theme.textTheme.bodySmall),
                    if (item.timing != null)
                      Text(item.timing!, style: theme.textTheme.bodySmall),
                    if (item.price != null)
                      Text(item.price!, style: theme.textTheme.bodySmall),
                    const SizedBox(height: MakoloSpacing.sm),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        Text('Voir le détail', style: TextStyle(
                          color: theme.colorScheme.primary,
                        )),
                        const SizedBox(width: 4),
                        const Icon(Icons.arrow_forward, size: 18),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
