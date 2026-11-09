import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';

/// Nous N2: real institutional assets belonging to the active Space.
///
/// Resource metadata stays in its owner (Sharing or Presentation). The client
/// never treats a member's PersonalAsset or an ActivityResource as Space owned.
class SpaceUsResourcesScreen extends StatefulWidget {
  const SpaceUsResourcesScreen({
    super.key,
    required this.runtime,
    required this.slug,
  });

  final AppRuntime runtime;
  final String slug;

  @override
  State<SpaceUsResourcesScreen> createState() => _SpaceUsResourcesScreenState();
}

class _SpaceUsResourcesScreenState extends State<SpaceUsResourcesScreen> {
  static const _families = <String, String>{
    'document': 'Documents',
    'passport': 'Passeports émis',
    'template': 'Modèles',
    'theme': 'Thèmes',
  };

  String _family = 'document';
  List<Map<String, dynamic>> _items = [];
  Map<String, dynamic> _counts = {};
  bool _loading = true;
  bool _more = false;
  bool _denied = false;
  bool _accessConfirmed = false;
  String? _error;
  int _nextOffset = 0;
  int _requestVersion = 0;

  bool get _authorized {
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext && actor.space.slug == widget.slug;
  }

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load(reset: true));
  }

  @override
  void didUpdateWidget(covariant SpaceUsResourcesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime != widget.runtime || oldWidget.slug != widget.slug) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
      _requestVersion++;
      _items = [];
      _counts = {};
      _denied = false;
      _accessConfirmed = false;
      WidgetsBinding.instance.addPostFrameCallback((_) => _load(reset: true));
    }
  }

  @override
  void dispose() {
    _requestVersion++;
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  void _onActorChanged() {
    _requestVersion++;
    if (!mounted) return;
    setState(() {
      _items = [];
      _counts = {};
      _more = false;
      _nextOffset = 0;
      _denied = !_authorized;
      _accessConfirmed = false;
      _error = null;
      _loading = _authorized;
    });
    if (_authorized) _load(reset: true);
  }

  Future<void> _load({required bool reset}) async {
    final current = widget.runtime.actorContext?.value;
    final api = widget.runtime.api;
    final ticket = ++_requestVersion;
    if (current is! SpaceActorContext ||
        current.space.slug != widget.slug ||
        api == null) {
      if (!mounted) return;
      setState(() {
        _items = [];
        _more = false;
        _loading = false;
        _denied =
            current is! SpaceActorContext || current.space.slug != widget.slug;
        _error = _denied
            ? null
            : 'Connexion nécessaire pour consulter ces ressources.';
      });
      return;
    }
    final expectedId = current.space.id;
    final kind = _family;
    final offset = reset ? 0 : _nextOffset;
    setState(() {
      _loading = true;
      _error = null;
      if (reset) {
        _items = [];
        _more = false;
        _nextOffset = 0;
      }
    });
    try {
      final result = await api.get(
        'api/v1/organizations/workspaces/'
        '${Uri.encodeComponent(widget.slug)}/us/resources/'
        '?kind=$kind&offset=$offset',
      );
      final data = result.jsonObject();
      final active = widget.runtime.actorContext?.value;
      if (!mounted ||
          ticket != _requestVersion ||
          active is! SpaceActorContext ||
          active.space.id != expectedId ||
          active.space.slug != widget.slug) {
        return;
      }
      if (data['space_id'] != expectedId ||
          data['kind'] != kind ||
          data['items'] is! List) {
        throw const FormatException('Incohérence de la projection Ressources.');
      }
      final rows = <Map<String, dynamic>>[
        for (final item in data['items'] as List)
          if (item is Map<String, dynamic>) item,
      ];
      setState(() {
        _accessConfirmed = true;
        _counts = data['counts'] is Map<String, dynamic>
            ? data['counts'] as Map<String, dynamic>
            : {};
        _items = reset ? rows : [..._items, ...rows];
        _more = data['has_more'] == true;
        _nextOffset = data['next_offset'] is int
            ? data['next_offset'] as int
            : _items.length;
        _loading = false;
      });
    } on MakoloApiError catch (error) {
      if (!mounted || ticket != _requestVersion || !_authorized) return;
      setState(() {
        _loading = false;
        _accessConfirmed = false;
        _denied =
            error.statusCode == 401 ||
            error.statusCode == 403 ||
            error.statusCode == 404;
        _items = [];
        _more = false;
        _error = _denied
            ? 'Vos droits ont changé. Ressources indisponibles.'
            : 'Impossible de charger les ressources.';
      });
    } on Object {
      if (!mounted || ticket != _requestVersion || !_authorized) return;
      setState(() {
        _loading = false;
        _items = [];
        _more = false;
        _accessConfirmed = false;
        _error = 'Impossible de charger les ressources.';
      });
    }
  }

  String? _resourceTarget(Map<String, dynamic> item) {
    final expected = '/space/${widget.slug}/us/passport';
    // A route must come from the current Space owner projection and match
    // this Space; item kind or an old local URL never grants navigation.
    if (item['kind'] == 'passport' && item['handoff'] == expected) {
      return expected;
    }
    if (item['kind'] == 'document') {
      final id = item['id']?.toString();
      if (id == null || !RegExp(r'^[0-9a-fA-F-]{36}$').hasMatch(id)) {
        return null;
      }
      final documentRoute = '/space/${widget.slug}/us/documents/$id';
      return item['handoff'] == documentRoute ? documentRoute : null;
    }
    return null;
  }

  void _select(String family) {
    if (family == _family) return;
    setState(() {
      _family = family;
      _error = null;
    });
    _load(reset: true);
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Nos ressources')),
      body: ListView(
        padding: const EdgeInsets.all(MakoloSpacing.lg),
        children: [
          Text(
            'Ressources de cet Espace',
            style: text.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: MakoloSpacing.sm),
          const Text('Les ressources de notre collectif.'),
          const SizedBox(height: MakoloSpacing.lg),
          if (_authorized && !_denied && _accessConfirmed)
            Padding(
              padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
              child: MakoloActionButton(
                label: 'Documents de l’Espace',
                appearance: MakoloActionAppearance.secondary,
                onPressed: () =>
                    context.push('/space/${widget.slug}/us/documents'),
                icon: Icons.folder_open_outlined,
              ),
            ),
          Wrap(
            spacing: MakoloSpacing.sm,
            runSpacing: MakoloSpacing.sm,
            children: [
              for (final entry in _families.entries)
                ChoiceChip(
                  label: Text('${entry.value} (${_counts[entry.key] ?? 0})'),
                  selected: _family == entry.key,
                  onSelected: _denied || !_authorized
                      ? null
                      : (_) => _select(entry.key),
                ),
            ],
          ),
          const SizedBox(height: MakoloSpacing.lg),
          if (_denied)
            const Text('Vous n’avez pas accès à ces ressources.')
          else if (_error != null) ...[
            Text(_error!),
            MakoloActionButton(
              label: 'Réessayer',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => _load(reset: true),
              icon: Icons.refresh_rounded,
            ),
          ] else if (_loading && _items.isEmpty)
            const Center(child: CircularProgressIndicator())
          else if (_items.isEmpty)
            const Text('Aucune ressource dans cette catégorie.')
          else
            for (final item in _items)
              Card(
                child: ListTile(
                  leading: Icon(
                    item['kind'] == 'document'
                        ? Icons.description_outlined
                        : item['kind'] == 'passport'
                        ? Icons.badge_outlined
                        : Icons.layers_outlined,
                    color: colors.primary,
                  ),
                  title: Text(item['title']?.toString() ?? 'Ressource'),
                  subtitle: Text(item['detail']?.toString() ?? ''),
                  trailing: _resourceTarget(item) != null
                      ? const Icon(Icons.chevron_right_rounded)
                      : null,
                  onTap: _resourceTarget(item) != null
                      ? () => context.push(_resourceTarget(item)!)
                      : null,
                ),
              ),
          if (_loading && _items.isNotEmpty)
            const Center(child: CircularProgressIndicator()),
          if (_more && !_loading)
            MakoloActionButton(
              label: 'Voir les ressources suivantes',
              appearance: MakoloActionAppearance.quiet,
              onPressed: () => _load(reset: false),
              icon: Icons.expand_more_rounded,
            ),
        ],
      ),
    );
  }
}
