import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class GuestDiscoverScreen extends StatefulWidget {
  const GuestDiscoverScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<GuestDiscoverScreen> createState() => _GuestDiscoverScreenState();
}

class _GuestDiscoverScreenState extends State<GuestDiscoverScreen> {
  static const _interactionId = 'public-discover';

  final _search = TextEditingController();
  Future<List<Map<String, dynamic>>>? _results;
  List<Map<String, dynamic>> _allItems = const [];
  String? _error;
  Timer? _queryDraftTimer;

  @override
  void initState() {
    super.initState();
    unawaited(_restoreAndLoad());
  }

  void _persistQueryDraft() {
    _queryDraftTimer?.cancel();
    _queryDraftTimer = Timer(const Duration(milliseconds: 250), () {
      unawaited(
        widget.runtime.interactions?.save(_interactionId, {
              'query': _search.text.trim(),
            }) ??
            Future<void>.value(),
      );
    });
  }

  void _onQueryChanged(String value) {
    _persistQueryDraft();
    _applyLocalFilter();
  }

  bool _matchesQuery(Map<String, dynamic> item, String query) {
    final raw = item['representation'];
    if (raw is! Map) return false;
    final representation = Map<String, dynamic>.from(raw);
    final values = <Object?>[
      representation['title'],
      representation['summary'],
      representation['eyebrow'],
    ];
    for (final value in values) {
      if (value != null && value.toString().toLowerCase().contains(query)) {
        return true;
      }
    }
    return false;
  }

  List<Map<String, dynamic>> _filteredItems() {
    final query = _search.text.trim().toLowerCase();
    if (query.isEmpty) return _allItems;
    return _allItems
        .where((item) => _matchesQuery(item, query))
        .toList(growable: false);
  }

  void _applyLocalFilter() {
    if (!mounted) return;
    setState(() {
      _results = Future.value(_filteredItems());
    });
  }

  @override
  void dispose() {
    _queryDraftTimer?.cancel();
    _search.dispose();
    super.dispose();
  }

  Future<void> _restoreAndLoad() async {
    final draft = await widget.runtime.interactions?.read(_interactionId);
    if (!mounted) return;
    final query = draft?['query'];
    if (query is String) _search.text = query;
    await _load();
  }

  Future<void> _load() async {
    final api = widget.runtime.api;
    if (api == null) {
      _allItems = const [];
      if (mounted) {
        setState(() {
          _results = Future.value(const <Map<String, dynamic>>[]);
          _error = null;
        });
      }
      return;
    }

    final query = _search.text.trim();
    await widget.runtime.interactions?.save(_interactionId, {'query': query});

    setState(() {
      _error = null;
      _results = () async {
        try {
          final response = await api.publicGet(
            'api/v1/discovery/items/?page_size=20',
          );
          final payload = response.jsonObject();
          final data = payload['data'];
          final rawResults = data is Map ? data['results'] : null;
          if (rawResults is! List) {
            _allItems = const [];
            return const <Map<String, dynamic>>[];
          }
          _allItems = rawResults
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList(growable: false);

          return _filteredItems();
        } on Object {
          if (mounted) {
            setState(
              () => _error =
                  'Impossible d’actualiser les possibilités publiques.',
            );
          }
          return const <Map<String, dynamic>>[];
        }
      }();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            key: const Key('guest-public-landing'),
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.lg,
              MakoloSpacing.md,
              MakoloSpacing.lg,
              MakoloSpacing.xl,
            ),
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: MakoloSpacing.xs),
                    child: MakoloMark(size: 38),
                  ),
                  const SizedBox(width: MakoloSpacing.sm),
                  Expanded(
                    child: Wrap(
                      alignment: WrapAlignment.end,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: MakoloSpacing.xs,
                      runSpacing: MakoloSpacing.xs,
                      children: [
                        TextButton(
                          onPressed: () => context.push('/login'),
                          child: const Text('Se connecter'),
                        ),
                        OutlinedButton(
                          onPressed: () => context.push('/create-account'),
                          child: const Text('Créer un compte'),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: MakoloSpacing.xl),
              Text(
                'Qu’est-ce que vous pourriez avoir envie de vivre, faire ou obtenir ?',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: MakoloSpacing.lg),
              SearchBar(
                controller: _search,
                hintText: 'Rechercher',
                leading: const Icon(Icons.search),
                onChanged: _onQueryChanged,
                onSubmitted: (_) => _applyLocalFilter(),
                trailing: [
                  if (_search.text.isNotEmpty)
                    IconButton(
                      tooltip: 'Effacer',
                      onPressed: () {
                        _search.clear();
                        _onQueryChanged('');
                      },
                      icon: const Icon(Icons.close),
                    ),
                ],
              ),
              const SizedBox(height: MakoloSpacing.xl),
              if (_error != null) ...[
                Text(_error!, style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: MakoloSpacing.md),
              ],
              FutureBuilder<List<Map<String, dynamic>>>(
                future: _results,
                builder: (context, snapshot) {
                  if (_results == null ||
                      snapshot.connectionState == ConnectionState.waiting) {
                    return const Padding(
                      padding: EdgeInsets.only(top: MakoloSpacing.md),
                      child: MakoloLoadingState(
                        label: 'Chargement des possibilités',
                      ),
                    );
                  }
                  final items = snapshot.data ?? const <Map<String, dynamic>>[];
                  if (items.isEmpty) {
                    return const MakoloEmptyState(
                      title: 'Aucune possibilité publique à afficher pour le moment.',
                      icon: Icons.explore_outlined,
                    );
                  }
                  return Column(
                    children: items
                        .map((item) => _PublicPossibilityCard(item: item))
                        .toList(growable: false),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PublicPossibilityCard extends StatelessWidget {
  const _PublicPossibilityCard({required this.item});

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final raw = item['representation'];
    final representation = raw is Map
        ? Map<String, dynamic>.from(raw)
        : const <String, dynamic>{};
    final title = representation['title']?.toString().trim() ?? '';
    final summary = representation['summary']?.toString().trim() ?? '';
    final eyebrow = representation['eyebrow']?.toString().trim() ?? '';

    if (title.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(MakoloSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (eyebrow.isNotEmpty) ...[
                Text(
                  eyebrow,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: Theme.of(context).colorScheme.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: MakoloSpacing.xs),
              ],
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              if (summary.isNotEmpty) ...[
                const SizedBox(height: MakoloSpacing.sm),
                Text(summary, maxLines: 3, overflow: TextOverflow.ellipsis),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
