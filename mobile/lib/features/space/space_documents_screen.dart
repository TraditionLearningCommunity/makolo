import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';
import '../../network/makolo_api_client.dart';
import '../../platform/media/native_media_picker.dart';
import '../../sync/owner_source_state.dart';
import '../resources/resource_presentation.dart';

/// Nous · Documents.
///
/// The collection is read local-first through the Space repository. Cached
/// rows remain observations only: owner actions are exposed only after a fresh
/// owner-confirmed collection and every mutation is still validated server-side.
class SpaceDocumentsScreen extends StatefulWidget {
  const SpaceDocumentsScreen({
    super.key,
    required this.runtime,
    required this.slug,
  });

  final AppRuntime runtime;
  final String slug;

  @override
  State<SpaceDocumentsScreen> createState() => _SpaceDocumentsScreenState();
}

class _SpaceDocumentsScreenState extends State<SpaceDocumentsScreen> {
  final _search = TextEditingController();
  Timer? _searchDebounce;

  String _query = '';
  bool _searching = false;
  bool _initializing = true;
  bool _refreshing = false;
  bool _loadingMore = false;
  bool _loadFailed = false;
  bool _busy = false;
  bool _canManage = false;
  String? _completedRequest;

  SpaceActorContext? get _actor {
    final current = widget.runtime.actorContext?.value;
    return current is SpaceActorContext && current.space.slug == widget.slug
        ? current
        : null;
  }

  String get _base =>
      'api/v1/organizations/workspaces/'
      '${Uri.encodeComponent(widget.slug)}/documents/';

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_actorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_ensureFirstPage());
    });
  }

  @override
  void didUpdateWidget(covariant SpaceDocumentsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime != widget.runtime || oldWidget.slug != widget.slug) {
      oldWidget.runtime.actorContext?.removeListener(_actorChanged);
      widget.runtime.actorContext?.addListener(_actorChanged);
      _actorChanged();
    }
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_actorChanged);
    _searchDebounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _actorChanged() {
    if (!mounted) return;
    _searchDebounce?.cancel();
    _search.clear();
    setState(() {
      _query = '';
      _searching = false;
      _initializing = _actor != null;
      _refreshing = false;
      _loadingMore = false;
      _loadFailed = false;
      _canManage = false;
      _completedRequest = null;
    });
    if (_actor != null) unawaited(_ensureFirstPage());
  }

  Future<OwnerSourceState?> _sourceState({int offset = 0}) async {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null) return null;
    return repository.readSource(
      repository.documentsSource(actor.space, query: _query, offset: offset),
    );
  }

  Future<void> _ensureFirstPage() async {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) {
      if (mounted) setState(() => _initializing = false);
      return;
    }
    final expectedId = actor.space.id;
    if (mounted) {
      setState(() {
        _initializing = true;
        _loadFailed = false;
      });
    }
    try {
      await repository.ensureDocumentPage(
        actor.space,
        query: _query,
        offset: 0,
      );
      final state = await _sourceState();
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _loadFailed = state?.lastErrorCode != null);
      }
    } on Object {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _loadFailed = true);
      }
    } finally {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _initializing = false);
      }
    }
  }

  Future<void> _refreshFirst() async {
    if (_refreshing) return;
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) return;
    final expectedId = actor.space.id;
    setState(() {
      _refreshing = true;
      _loadFailed = false;
      _completedRequest = null;
    });
    try {
      await repository.refreshDocumentPage(
        actor.space,
        query: _query,
        offset: 0,
      );
      final state = await _sourceState();
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _loadFailed = state?.lastErrorCode != null);
      }
    } on Object {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _loadFailed = true);
      }
    } finally {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _refreshing = false);
      }
    }
  }

  Future<void> _loadMore(_SpaceDocumentsView view) async {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null ||
        repository == null ||
        repository.sync == null ||
        _loadingMore ||
        _loadFailed ||
        !view.hasMore) {
      return;
    }
    final requestKey = '${actor.space.id}|$_query|${view.nextOffset}';
    if (_completedRequest == requestKey) return;
    final expectedId = actor.space.id;
    setState(() => _loadingMore = true);
    try {
      await repository.refreshDocumentPage(
        actor.space,
        query: _query,
        offset: view.nextOffset,
      );
      final state = await _sourceState(offset: view.nextOffset);
      if (state?.lastErrorCode != null || state?.invalidated == true) {
        throw StateError('Space document continuation unavailable');
      }
      if (mounted && _actor?.space.id == expectedId) {
        _completedRequest = requestKey;
      }
    } on Object {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _loadFailed = true);
      }
    } finally {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _loadingMore = false);
      }
    }
  }

  void _openSearch() {
    if (_searching) return;
    setState(() => _searching = true);
  }

  void _closeSearch() {
    _searchDebounce?.cancel();
    final hadQuery = _query.isNotEmpty || _search.text.trim().isNotEmpty;
    _search.clear();
    setState(() {
      _searching = false;
      if (hadQuery) {
        _query = '';
        _initializing = true;
        _loadFailed = false;
        _completedRequest = null;
      }
    });
    if (hadQuery) unawaited(_ensureFirstPage());
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 350), () {
      if (!mounted) return;
      final next = value.trim();
      if (next == _query) return;
      setState(() {
        _query = next;
        _initializing = true;
        _loadFailed = false;
        _completedRequest = null;
      });
      unawaited(_ensureFirstPage());
    });
  }

  Future<void> _add() async {
    if (_busy || !_canManage || _actor == null) return;
    final chosen = await NativeMediaPicker.pickDocument([
      'pdf',
      'doc',
      'docx',
      'txt',
      'png',
      'jpg',
      'jpeg',
    ]);
    if (chosen == null || !mounted || chosen.path == null) return;

    final controller = TextEditingController(
      text: chosen.name.replaceFirst(RegExp(r'\.[^.]+$'), ''),
    );
    var visibility = 'restricted';
    var kind = 'other';
    final metadata = await showModalBottomSheet<Map<String, String>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, update) {
          final keyboard = MediaQuery.viewInsetsOf(context).bottom;
          return SingleChildScrollView(
            padding: EdgeInsets.fromLTRB(
              MakoloSpacing.lg,
              MakoloSpacing.sm,
              MakoloSpacing.lg,
              MakoloSpacing.lg + keyboard,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Ajouter un document',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: MakoloSpacing.md),
                Container(
                  padding: const EdgeInsets.all(MakoloSpacing.md),
                  decoration: BoxDecoration(
                    color: Theme.of(context)
                        .colorScheme
                        .surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.insert_drive_file_outlined,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: MakoloSpacing.sm),
                      Expanded(
                        child: Text(
                          chosen.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: MakoloSpacing.md),
                TextField(
                  controller: controller,
                  maxLength: 220,
                  autofocus: true,
                  decoration: const InputDecoration(
                    labelText: 'Titre',
                    hintText: 'Nom utile pour votre équipe',
                  ),
                ),
                const SizedBox(height: MakoloSpacing.sm),
                Text(
                  'Type',
                  style: Theme.of(context).textTheme.labelLarge,
                ),
                const SizedBox(height: MakoloSpacing.xs),
                Wrap(
                  spacing: MakoloSpacing.sm,
                  runSpacing: MakoloSpacing.xs,
                  children: [
                    ChoiceChip(
                      label: const Text('Document'),
                      selected: kind == 'other',
                      onSelected: (_) => update(() => kind = 'other'),
                    ),
                    ChoiceChip(
                      label: const Text('Certificat / attestation'),
                      selected: kind == 'certificate',
                      onSelected: (_) => update(() => kind = 'certificate'),
                    ),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.md),
                Text(
                  'Accès',
                  style: Theme.of(context).textTheme.labelLarge,
                ),
                const SizedBox(height: MakoloSpacing.xs),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(
                      value: 'restricted',
                      label: Text('Confidentiel'),
                      icon: Icon(Icons.lock_outline_rounded),
                    ),
                    ButtonSegment(
                      value: 'internal',
                      label: Text('Équipe'),
                      icon: Icon(Icons.group_outlined),
                    ),
                  ],
                  selected: {visibility},
                  onSelectionChanged: (value) {
                    if (value.isNotEmpty) {
                      update(() => visibility = value.first);
                    }
                  },
                ),
                const SizedBox(height: MakoloSpacing.lg),
                Row(
                  children: [
                    Expanded(
                      child: MakoloActionButton(
                        label: 'Annuler',
                        appearance: MakoloActionAppearance.quiet,
                        onPressed: () => Navigator.pop(sheetContext),
                      ),
                    ),
                    const SizedBox(width: MakoloSpacing.sm),
                    Expanded(
                      child: MakoloActionButton(
                        label: 'Ajouter',
                        appearance: MakoloActionAppearance.primary,
                        onPressed: () {
                          final title = controller.text.trim();
                          if (title.isEmpty) return;
                          Navigator.pop(sheetContext, {
                            'title': title,
                            'visibility': visibility,
                            'kind': kind,
                          });
                        },
                      ),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
    controller.dispose();
    if (metadata == null || !mounted) return;

    final actor = _actor;
    final api = widget.runtime.api;
    if (actor == null || api == null) return;
    final expectedId = actor.space.id;
    setState(() => _busy = true);
    try {
      await api.upload(
        _base,
        fields: metadata,
        files: [
          MakoloUploadFile(
            fieldName: 'file',
            path: chosen.path!,
            filename: chosen.name,
            contentType: _contentTypeFor(chosen.name),
          ),
        ],
      );
      if (!mounted || _actor?.space.id != expectedId) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Document ajouté.')));
      await _refreshFirst();
      try {
        await widget.runtime.space?.refreshUs(actor.space);
        await widget.runtime.space?.refreshResources(actor.space);
        if (metadata['kind'] == 'certificate') {
          await widget.runtime.space?.refreshResourceFamily(
            actor.space,
            'received_title',
          );
        }
      } on Object {
        // The owner mutation is confirmed; other projections reconcile later.
      }
    } on MakoloApiError catch (error) {
      if (mounted && _actor?.space.id == expectedId) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } on Object {
      if (mounted && _actor?.space.id == expectedId) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Ce document n’a pas pu être ajouté. Réessayez.'),
          ),
        );
      }
    } finally {
      if (mounted && _actor?.space.id == expectedId) {
        setState(() => _busy = false);
      }
    }
  }

  String _contentTypeFor(String filename) {
    final name = filename.toLowerCase();
    if (name.endsWith('.pdf')) return 'application/pdf';
    if (name.endsWith('.docx')) {
      return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    }
    if (name.endsWith('.doc')) return 'application/msword';
    if (name.endsWith('.txt')) return 'text/plain';
    if (name.endsWith('.png')) return 'image/png';
    if (name.endsWith('.jpg') || name.endsWith('.jpeg')) return 'image/jpeg';
    return 'application/octet-stream';
  }

  @override
  Widget build(BuildContext context) {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null) {
      return ResourceCollectionScaffold(
        title: 'Nos documents',
        count: null,
        searching: _searching,
        searchController: _search,
        searchHint: 'Rechercher dans nos documents',
        onSearchChanged: _onSearchChanged,
        onOpenSearch: _openSearch,
        onCloseSearch: _closeSearch,
        onRefresh: _refreshFirst,
        refreshing: false,
        children: const [
          Padding(
            padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
            child: Center(child: Text('Cet Espace n’est plus actif.')),
          ),
        ],
      );
    }

    final firstSource = repository.documentsSource(
      actor.space,
      query: _query,
      offset: 0,
    );
    return StreamBuilder<List<StoredProjection>>(
      stream: repository.watchDocumentPages(actor.space, query: _query),
      initialData: const [],
      builder: (context, pagesSnapshot) {
        final view = _SpaceDocumentsView.fromPages(
          pagesSnapshot.data ?? const [],
        );
        return StreamBuilder<OwnerSourceState>(
          stream: repository.watchSource(firstSource),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final freshAuthority =
                view.canManage &&
                !_initializing &&
                !_refreshing &&
                source.lastSuccessAt != null &&
                source.lastErrorCode == null &&
                !source.invalidated;
            _canManage = freshAuthority;

            final completeEmpty =
                view.hasSnapshot &&
                view.count == 0 &&
                !view.hasMore &&
                source.lastSuccessAt != null &&
                source.lastErrorCode == null &&
                !source.invalidated;

            final children = <Widget>[
              if (source.invalidated)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
                  child: Center(
                    child: Text('Documents non accessibles dans ce contexte.'),
                  ),
                )
              else if (!view.hasSnapshot && _initializing)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
                  child: Center(child: CircularProgressIndicator.adaptive()),
                )
              else if (!view.hasSnapshot)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: MakoloSpacing.xl,
                  ),
                  child: Column(
                    children: [
                      const Text('Documents indisponibles.'),
                      const SizedBox(height: MakoloSpacing.md),
                      MakoloActionButton(
                        label: 'Réessayer',
                        appearance: MakoloActionAppearance.quiet,
                        onPressed: _refreshFirst,
                        icon: Icons.refresh_rounded,
                      ),
                    ],
                  ),
                )
              else if (view.items.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: MakoloSpacing.xl,
                  ),
                  child: Center(
                    child: Text(
                      _query.isNotEmpty
                          ? completeEmpty
                                ? 'Aucun résultat'
                                : 'Aucun résultat parmi les documents disponibles.'
                          : completeEmpty
                          ? 'Aucun document pour le moment.'
                          : 'Aucun document à afficher.',
                    ),
                  ),
                )
              else
                for (final doc in view.items)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                    child: Card(
                      child: ListTile(
                        leading: Icon(
                          Icons.description_outlined,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        title: Text(doc['title']?.toString() ?? 'Document'),
                        subtitle: Text(
                          doc['visibility'] == 'restricted'
                              ? 'Confidentiel · '
                                    'v${doc['latest_version'] ?? '1'}'
                              : 'Équipe · '
                                    'v${doc['latest_version'] ?? '1'}',
                        ),
                        trailing: const Icon(Icons.chevron_right_rounded),
                        onTap: () {
                          final id = doc['id']?.toString();
                          if (id != null &&
                              RegExp(r'^[0-9a-fA-F-]{36}$').hasMatch(id)) {
                            context.push(
                              '/space/${widget.slug}/us/documents/$id',
                            );
                          }
                        },
                      ),
                    ),
                  ),
              if (!source.invalidated && _loadingMore && view.hasMore)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(MakoloSpacing.md),
                    child: CircularProgressIndicator.adaptive(),
                  ),
                ),
              if (!source.invalidated && _loadFailed && view.hasMore)
                Center(
                  child: MakoloActionButton(
                    label: 'Réessayer la suite',
                    appearance: MakoloActionAppearance.quiet,
                    onPressed: () {
                      setState(() => _loadFailed = false);
                      unawaited(_loadMore(view));
                    },
                  ),
                )
              else if (!source.invalidated && view.hasMore && !_loadingMore)
                Center(
                  child: MakoloActionButton(
                    label: 'Voir plus',
                    appearance: MakoloActionAppearance.quiet,
                    onPressed: () => _loadMore(view),
                    icon: Icons.expand_more_rounded,
                  ),
                ),
            ];

            return ResourceCollectionScaffold(
              title: 'Nos documents',
              count:
                  view.hasSnapshot &&
                      source.lastSuccessAt != null &&
                      source.lastErrorCode == null &&
                      !source.invalidated
                  ? view.count
                  : null,
              searching: _searching,
              searchEnabled: !source.invalidated,
              searchController: _search,
              searchHint: 'Rechercher dans nos documents',
              onSearchChanged: _onSearchChanged,
              onOpenSearch: _openSearch,
              onCloseSearch: _closeSearch,
              onRefresh: _refreshFirst,
              refreshing: _refreshing,
              actions: [
                if (freshAuthority)
                  MakoloIconActionButton(
                    tooltip: 'Ajouter',
                    icon: Icons.add_rounded,
                    onPressed: _busy ? null : _add,
                  ),
              ],
              storageKey: PageStorageKey<String>(
                'space-documents:${actor.space.id}:$_query',
              ),
              children: children,
            );
          },
        );
      },
    );
  }
}

class _SpaceDocumentsView {
  const _SpaceDocumentsView({
    required this.hasSnapshot,
    required this.items,
    required this.count,
    required this.canManage,
    required this.hasMore,
    required this.nextOffset,
  });

  final bool hasSnapshot;
  final List<Map<String, dynamic>> items;
  final int? count;
  final bool canManage;
  final bool hasMore;
  final int nextOffset;

  factory _SpaceDocumentsView.fromPages(List<StoredProjection> pages) {
    if (pages.isEmpty) {
      return const _SpaceDocumentsView(
        hasSnapshot: false,
        items: [],
        count: null,
        canManage: false,
        hasMore: false,
        nextOffset: 0,
      );
    }

    final items = <Map<String, dynamic>>[];
    final seen = <String>{};
    for (final page in pages) {
      final rows = page.payload['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        if (raw is! Map) continue;
        final row = raw.map((key, value) => MapEntry(key.toString(), value));
        final id = row['id']?.toString();
        if (id == null || !seen.add(id)) continue;
        items.add(row);
      }
    }

    final first = pages.first.payload;
    final last = pages.last.payload;
    final countValue = first['count'];
    final nextValue = last['next_offset'];
    return _SpaceDocumentsView(
      hasSnapshot: true,
      items: List.unmodifiable(items),
      count: countValue is num ? countValue.toInt() : null,
      canManage: first['can_manage'] == true,
      hasMore: last['has_more'] == true,
      nextOffset: nextValue is num ? nextValue.toInt() : items.length,
    );
  }
}
