import 'dart:async';

import '../../platform/media/native_media_picker.dart';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../resources/resource_presentation.dart';
import '../../network/makolo_api_client.dart';
import '../../network/api_error.dart';

/// Nous · Documents. No private document contents are cached in the UI.
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
  List<Map<String, dynamic>> _documents = [];
  int? _count;
  bool _searching = false;
  bool _loading = true;
  bool _more = false;
  bool _canManage = false;
  bool _busy = false;
  int _offset = 0;
  int _request = 0;
  String? _message;

  SpaceActorContext? get _actor {
    final current = widget.runtime.actorContext?.value;
    return current is SpaceActorContext && current.space.slug == widget.slug
        ? current
        : null;
  }

  String get _base =>
      'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.slug)}/documents/';

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_actorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
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
    _request++;
    widget.runtime.actorContext?.removeListener(_actorChanged);
    _searchDebounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _actorChanged() {
    _request++;
    if (!mounted) return;
    setState(() {
      _documents = [];
      _count = null;
      _searching = false;
      _search.clear();
      _canManage = false;
      _more = false;
      _offset = 0;
      _loading = _actor != null;
      _message = _actor == null ? 'Choisissez cet Espace.' : null;
    });
    if (_actor != null) _load();
  }

  Future<void> _load({bool append = false}) async {
    final actor = _actor;
    final api = widget.runtime.api;
    final ticket = ++_request;
    if (actor == null || api == null) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _documents = [];
        _message = actor == null
            ? 'Cet Espace n’est plus actif.'
            : 'Connexion nécessaire.';
      });
      return;
    }
    final spaceId = actor.space.id;
    final offset = append ? _offset : 0;
    setState(() {
      _loading = true;
      // Existing owner-observed private list remains visible while a
      // refresh is in flight. It is not a grant to upload or share.
      if (!append && _documents.isEmpty) _more = false;
      _message = null;
    });
    try {
      final response = await api.get(
        '$_base?q=${Uri.encodeQueryComponent(_search.text.trim())}'
        '&offset=$offset',
      );
      final payload = response.jsonObject();
      final current = _actor;
      if (!mounted || ticket != _request || current?.space.id != spaceId) {
        return;
      }
      if (payload['space_id'] != spaceId || payload['items'] is! List) {
        throw const FormatException('Documents incohérents');
      }
      final items = <Map<String, dynamic>>[
        for (final item in payload['items'] as List)
          if (item is Map<String, dynamic>) item,
      ];
      setState(() {
        _documents = append ? [..._documents, ...items] : items;
        _count = payload['count'] is num
            ? (payload['count'] as num).toInt()
            : int.tryParse('${payload['count'] ?? ''}');
        _more = payload['has_more'] == true;
        _offset = payload['next_offset'] is int
            ? payload['next_offset'] as int
            : _documents.length;
        _canManage = payload['can_manage'] == true;
        _loading = false;
      });
    } on Object catch (error) {
      if (!mounted || ticket != _request || _actor?.space.id != spaceId) {
        return;
      }
      final withdrawn =
          error is MakoloApiError &&
          const {401, 403, 404}.contains(error.statusCode);
      setState(() {
        _loading = false;
        // A definitive owner refusal withdraws even transient knowledge.
        // A transport outage keeps the already acquired list in memory only,
        // but never leaves management rights enabled without revalidation.
        if (withdrawn) {
          _documents = [];
          _count = null;
          _more = false;
        }
        _canManage = false;
        _message = withdrawn
            ? 'Documents non accessibles dans ce contexte.'
            : _documents.isEmpty
            ? 'Documents indisponibles.'
            : 'Actualisation indisponible. Les documents affichés '
                  'proviennent de votre dernière consultation.';
      });
    }
  }

  void _openSearch() {
    if (_searching) return;
    setState(() => _searching = true);
  }

  void _closeSearch() {
    _searchDebounce?.cancel();
    final hadQuery = _search.text.trim().isNotEmpty;
    _search.clear();
    setState(() => _searching = false);
    if (hadQuery) unawaited(_load());
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) unawaited(_load());
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
    if (chosen == null || !mounted) return;
    if (chosen.path == null) return;
    final controller = TextEditingController(
      text: chosen.name.replaceFirst(RegExp(r'\.[^.]+$'), ''),
    );
    var visibility = 'restricted';
    final metadata = await showDialog<Map<String, String>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Ajouter un document'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: controller,
                maxLength: 220,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Titre'),
              ),
              DropdownButtonFormField<String>(
                initialValue: visibility,
                decoration: const InputDecoration(labelText: 'Accès'),
                items: const [
                  DropdownMenuItem(
                    value: 'restricted',
                    child: Text('Confidentiel'),
                  ),
                  DropdownMenuItem(
                    value: 'internal',
                    child: Text('Équipe autorisée'),
                  ),
                ],
                onChanged: (value) =>
                    update(() => visibility = value ?? 'restricted'),
              ),
            ],
          ),
          actions: [
            MakoloActionButton(
              label: 'Annuler',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => Navigator.pop(dialogContext),
            ),
            MakoloActionButton(
              label: 'Déposer',
              appearance: MakoloActionAppearance.primary,
              onPressed: () {
                if (controller.text.trim().isNotEmpty) {
                  Navigator.pop(dialogContext, {
                    'title': controller.text.trim(),
                    'visibility': visibility,
                  });
                }
              },
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (metadata == null || !mounted) return;
    final id = _actor?.space.id;
    final api = widget.runtime.api;
    if (id == null || api == null) return;
    setState(() => _busy = true);
    try {
      await api.upload(
        _base,
        fields: {...metadata, 'kind': 'other'},
        files: [
          MakoloUploadFile(
            fieldName: 'file',
            path: chosen.path!,
            filename: chosen.name,
          ),
        ],
      );
      if (!mounted || _actor?.space.id != id) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Document ajouté.')));
      await _load();
    } on Object {
      if (mounted && _actor?.space.id == id) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Dépôt impossible.')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final body = <Widget>[
      if (_message != null) ...[
        Text(_message!),
        const SizedBox(height: MakoloSpacing.sm),
        MakoloActionButton(
          label: 'Réessayer',
          appearance: MakoloActionAppearance.quiet,
          onPressed: () => _load(),
          icon: Icons.refresh_rounded,
        ),
      ] else if (_loading && _documents.isEmpty)
        const Padding(
          padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
          child: Center(child: CircularProgressIndicator.adaptive()),
        )
      else if (_documents.isEmpty)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
          child: Center(
            child: Text(
              _search.text.trim().isEmpty
                  ? 'Aucun document pour le moment.'
                  : 'Aucun résultat',
            ),
          ),
        )
      else
        for (final doc in _documents)
          Padding(
            padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
            child: Card(
              child: ListTile(
                leading: Icon(
                  Icons.description_outlined,
                  color: colors.primary,
                ),
                title: Text(doc['title']?.toString() ?? 'Document'),
                subtitle: Text(
                  doc['visibility'] == 'restricted'
                      ? 'Confidentiel · v${doc['latest_version'] ?? '1'}'
                      : 'Équipe · v${doc['latest_version'] ?? '1'}',
                ),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () {
                  final id = doc['id']?.toString();
                  if (id != null &&
                      RegExp(r'^[0-9a-fA-F-]{36}$').hasMatch(id)) {
                    context.push('/space/${widget.slug}/us/documents/$id');
                  }
                },
              ),
            ),
          ),
      if (_loading && _documents.isNotEmpty)
        const Center(
          child: Padding(
            padding: EdgeInsets.all(MakoloSpacing.md),
            child: CircularProgressIndicator.adaptive(),
          ),
        ),
      if (_more && !_loading)
        Center(
          child: MakoloActionButton(
            label: 'Voir plus',
            appearance: MakoloActionAppearance.quiet,
            onPressed: () => _load(append: true),
            icon: Icons.expand_more_rounded,
          ),
        ),
    ];

    return ResourceCollectionScaffold(
      title: 'Nos documents',
      count: _count,
      searching: _searching,
      searchController: _search,
      searchHint: 'Rechercher dans nos documents',
      onSearchChanged: _onSearchChanged,
      onOpenSearch: _openSearch,
      onCloseSearch: _closeSearch,
      onRefresh: () => _load(),
      refreshing: _loading && _documents.isNotEmpty,
      actions: [
        if (_canManage)
          MakoloIconActionButton(
            tooltip: 'Ajouter',
            icon: Icons.add_rounded,
            onPressed: _busy ? null : _add,
          ),
      ],
      storageKey: PageStorageKey<String>(
        'space-documents:${widget.slug}:${_search.text.trim()}',
      ),
      children: body,
    );
  }
}
